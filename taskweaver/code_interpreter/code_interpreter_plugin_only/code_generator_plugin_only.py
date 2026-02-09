import json
import os
from typing import List, Optional

from injector import inject

from taskweaver.llm import LLMApi, format_chat_message
from taskweaver.llm.util import PromptTypeWithTools
from taskweaver.logging import TelemetryLogger
from taskweaver.memory import CompactedMessage, CompactorConfig, ContextCompactor, Memory, Post, Round
from taskweaver.memory.attachment import AttachmentType
from taskweaver.memory.plugin import PluginEntry, PluginRegistry
from taskweaver.module.event_emitter import PostEventProxy, SessionEventEmitter
from taskweaver.module.tracing import Tracing, tracing_decorator
from taskweaver.role import Role
from taskweaver.role.role import RoleConfig
from taskweaver.utils import read_yaml


class CodeGeneratorPluginOnlyConfig(RoleConfig):
    def _configure(self) -> None:
        self._set_name("code_generator")
        self.role_name = self._get_str("role_name", "ProgramApe")

        self.prompt_file_path = self._get_path(
            "prompt_file_path",
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "code_generator_prompt_plugin_only.yaml",
            ),
        )
        self.prompt_compression = self._get_bool("prompt_compression", False)
        self.compression_prompt_path = self._get_path(
            "compaction_prompt_path",
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "..",
                "code_interpreter",
                "compaction_prompt.yaml",
            ),
        )
        self.compaction_threshold = self._get_int("compaction_threshold", 10)
        self.compaction_retain_recent = self._get_int("compaction_retain_recent", 3)
        self.compaction_llm_alias = self._get_str("compaction_llm_alias", default="", required=False)
        self.llm_alias = self._get_str("llm_alias", default="", required=False)


class CodeGeneratorPluginOnly(Role):
    @inject
    def __init__(
        self,
        config: CodeGeneratorPluginOnlyConfig,
        plugin_registry: PluginRegistry,
        logger: TelemetryLogger,
        tracing: Tracing,
        event_emitter: SessionEventEmitter,
        llm_api: LLMApi,
    ):
        super().__init__(config, logger, tracing, event_emitter)
        self.config = config
        self.llm_api = llm_api

        self.role_name = self.config.role_name

        self.prompt_data = read_yaml(self.config.prompt_file_path)
        self.plugin_pool = [p for p in plugin_registry.get_list() if p.plugin_only is True]
        self.instruction_template = self.prompt_data["content"]

        self.compactor: Optional[ContextCompactor] = None
        if self.config.prompt_compression:
            compactor_config = CompactorConfig(
                threshold=self.config.compaction_threshold,
                retain_recent=self.config.compaction_retain_recent,
                prompt_template_path=self.config.compression_prompt_path,
                enabled=True,
            )
            self.compactor = ContextCompactor(
                config=compactor_config,
                llm_api=llm_api,
                rounds_getter=lambda: [],
                logger=lambda msg: self.logger.info(msg),
                llm_alias=self.config.compaction_llm_alias,
            )

    @tracing_decorator
    def reply(
        self,
        memory: Memory,
        post_proxy: Optional[PostEventProxy] = None,
        prompt_log_path: Optional[str] = None,
        **kwargs: ...,
    ) -> Post:
        assert post_proxy is not None, "Post proxy is not provided."

        if self.compactor:
            memory.register_compaction_provider(
                self.alias,
                self.compactor,
                rounds_getter=lambda: memory.get_role_rounds(role=self.alias),
            )
            self.compactor.start()

        rounds, compaction = memory.get_role_rounds_with_compaction(
            role=self.alias,
            include_failure_rounds=False,
        )

        if compaction:
            rounds = rounds[compaction.end_index :]

        user_query = rounds[-1].user_query
        self.tracing.set_span_attribute("user_query", user_query)

        # obtain the user query from the last round
        prompt_with_tools = self._compose_prompt(
            system_instructions=self.instruction_template.format(
                ROLE_NAME=self.role_name,
            ),
            rounds=rounds,
            plugin_pool=self.plugin_pool,
        )
        post_proxy.update_send_to("Planner")

        if prompt_log_path is not None:
            self.logger.dump_prompt_file(prompt_with_tools, prompt_log_path)

        prompt_size = self.tracing.count_tokens(
            json.dumps(prompt_with_tools["prompt"]),
        ) + self.tracing.count_tokens(json.dumps(prompt_with_tools["tools"]))
        self.tracing.set_span_attribute("prompt_size", prompt_size)
        self.tracing.add_prompt_size(
            size=prompt_size,
            labels={
                "direction": "input",
            },
        )

        self.tracing.set_span_attribute(
            "prompt",
            json.dumps(prompt_with_tools["prompt"], indent=2),
        )

        llm_response = self.llm_api.chat_completion(
            messages=prompt_with_tools["prompt"],
            tools=prompt_with_tools["tools"],
            tool_choice="auto",
            response_format=None,
            stream=False,
            llm_alias=self.config.llm_alias,
        )

        output_size = self.tracing.count_tokens(llm_response["content"])
        self.tracing.set_span_attribute("output_size", output_size)
        self.tracing.add_prompt_size(
            size=output_size,
            labels={
                "direction": "output",
            },
        )

        if llm_response["role"] == "assistant":
            post_proxy.update_message(llm_response["content"])
            return post_proxy.end()
        elif llm_response["role"] == "function":
            post_proxy.update_attachment(
                llm_response["content"],
                AttachmentType.function,
            )
            self.tracing.set_span_attribute("functions", llm_response["content"])

            return post_proxy.end()
        else:
            self.tracing.set_span_status(
                "ERROR",
                f"Unexpected response from LLM {llm_response}",
            )
            raise ValueError(f"Unexpected response from LLM: {llm_response}")

    def _compose_prompt(
        self,
        system_instructions: str,
        rounds: List[Round],
        plugin_pool: List[PluginEntry],
    ) -> PromptTypeWithTools:
        functions = [plugin.format_function_calling() for plugin in plugin_pool]
        prompt = [format_chat_message(role="system", message=system_instructions)]
        for _round in rounds:
            for post in _round.post_list:
                if post.send_from == "Planner" and post.send_to == self.alias:
                    prompt.append(
                        format_chat_message(role="user", message=post.message),
                    )
                elif post.send_from == self.alias and post.send_to == "Planner":
                    prompt.append(
                        format_chat_message(role="assistant", message=post.message),
                    )

        return {
            "prompt": prompt,
            "tools": functions,
        }
