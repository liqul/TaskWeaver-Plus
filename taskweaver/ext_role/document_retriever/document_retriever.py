import json
import os
import pickle
from typing import Any, Dict, List

import numpy as np
from injector import inject

from taskweaver.logging import TelemetryLogger
from taskweaver.memory import Memory, Post
from taskweaver.module.event_emitter import SessionEventEmitter
from taskweaver.module.prompt_util import PromptUtil
from taskweaver.module.tracing import Tracing
from taskweaver.role import Role
from taskweaver.role.role import RoleConfig, RoleEntry


class DocumentRetrieverConfig(RoleConfig):
    def _configure(self):
        # default is the directory where this file is located
        self.index_folder = self._get_str(
            "index_folder",
            os.path.join(
                os.path.dirname(__file__),
                "knowledge_base",
            ),
        )
        self.size = self._get_int("size", 5)
        self.target_length = self._get_int("target_length", 256)


class DocumentRetriever(Role):
    @inject
    def __init__(
        self,
        config: DocumentRetrieverConfig,
        logger: TelemetryLogger,
        tracing: Tracing,
        event_emitter: SessionEventEmitter,
        role_entry: RoleEntry,
    ):
        super().__init__(config, logger, tracing, event_emitter, role_entry)
        self.enc = None
        self.chunk_id_to_index = None
        self.index = None
        self.docstore: List[Dict[str, Any]] = []
        self.model = None

    def initialize(self):
        import faiss
        import tiktoken
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.index = faiss.read_index(
            os.path.join(self.config.index_folder, "index.faiss"),
        )
        with open(
            os.path.join(self.config.index_folder, "index.pkl"),
            "rb",
        ) as f:
            self.docstore = pickle.load(f)

        with open(
            os.path.join(
                self.config.index_folder,
                "chunk_id_to_index.pkl",
            ),
            "rb",
        ) as f:
            self.chunk_id_to_index = pickle.load(f)

        self.enc = tiktoken.encoding_for_model("gpt-3.5-turbo")

    def reply(self, memory: Memory, **kwargs: ...) -> Post:
        if not self.index:
            self.initialize()

        rounds = memory.get_role_rounds(
            role=self.alias,
            include_failure_rounds=False,
        )

        # obtain the query from the last round
        last_post = rounds[-1].post_list[-1]

        post_proxy = self.event_emitter.create_post_proxy(self.alias)

        post_proxy.update_send_to(last_post.send_from)

        # Encode query and search
        query_vec = self.model.encode([last_post.message], convert_to_numpy=True)
        query_vec = np.array(query_vec, dtype=np.float32)
        _, indices = self.index.search(query_vec, self.config.size)

        # Build result list matching the old langchain format
        result = []
        for idx in indices[0]:
            if idx < 0 or idx >= len(self.docstore):
                continue
            entry = self.docstore[idx]
            result.append(entry)

        expanded_chunks = self.do_expand(result, self.config.target_length)

        post_proxy.update_message(
            f"DocumentRetriever has done searching for `{last_post.message}`.\n"
            + PromptUtil.wrap_text_with_delimiter(
                "\n```json\n" + json.dumps(expanded_chunks, indent=4) + "```\n",
                PromptUtil.DELIMITER_TEMPORAL,
            ),
        )

        return post_proxy.end()

    def do_expand(self, result: List[Dict[str, Any]], target_length: int):
        expanded_chunks = []
        # do expansion
        for r in result:
            source = r["metadata"]["source"]
            chunk_id = r["metadata"]["chunk_id"]
            content = r["text"]

            expanded_result = content
            left_chunk_id, right_chunk_id = chunk_id - 1, chunk_id + 1
            left_valid, right_valid = True, True
            chunk_ids = [chunk_id]
            while True:
                current_length = len(self.enc.encode(expanded_result))
                if f"{source}_{left_chunk_id}" in self.chunk_id_to_index:
                    chunk_ids.append(left_chunk_id)
                    left_idx = self.chunk_id_to_index[f"{source}_{left_chunk_id}"]
                    left_chunk = self.docstore[left_idx]
                    encoded_left_chunk = self.enc.encode(left_chunk["text"])
                    if len(encoded_left_chunk) + current_length < target_length:
                        expanded_result = left_chunk["text"] + expanded_result
                        left_chunk_id -= 1
                        current_length += len(encoded_left_chunk)
                    else:
                        expanded_result += self.enc.decode(
                            encoded_left_chunk[-(target_length - current_length) :],
                        )
                        current_length = target_length
                        break
                else:
                    left_valid = False

                if f"{source}_{right_chunk_id}" in self.chunk_id_to_index:
                    chunk_ids.append(right_chunk_id)
                    right_idx = self.chunk_id_to_index[f"{source}_{right_chunk_id}"]
                    right_chunk = self.docstore[right_idx]
                    encoded_right_chunk = self.enc.encode(right_chunk["text"])
                    if len(encoded_right_chunk) + current_length < target_length:
                        expanded_result += right_chunk["text"]
                        right_chunk_id += 1
                        current_length += len(encoded_right_chunk)
                    else:
                        expanded_result += self.enc.decode(
                            encoded_right_chunk[: target_length - current_length],
                        )
                        current_length = target_length
                        break
                else:
                    right_valid = False

                if not left_valid and not right_valid:
                    break

            expanded_chunks.append(
                {
                    "chunk": expanded_result,
                    "metadata": r["metadata"],
                },
            )
        return expanded_chunks
