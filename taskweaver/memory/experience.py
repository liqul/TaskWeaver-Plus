import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from injector import inject

from taskweaver.config.module_config import ModuleConfig
from taskweaver.llm import LLMApi, format_chat_message
from taskweaver.logging import TelemetryLogger
from taskweaver.module.tracing import Tracing, tracing_decorator
from taskweaver.utils import read_yaml, write_yaml


@dataclass
class Experience:
    """Experience with separated selection criteria and instructions.

    Attributes:
        exp_id: Unique identifier for the experience
        who: List of role aliases this experience applies to. Empty list means all roles.
        when: Conditions/scenarios when this experience should be used (for selection)
        what: Detailed instructions on what to do (injected into prompts)
    """
    exp_id: str
    who: List[str]
    when: str
    what: str

    def to_dict(self):
        return {
            "exp_id": self.exp_id,
            "who": self.who,
            "when": self.when,
            "what": self.what,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]):
        who = d.get("who", [])
        if isinstance(who, str):
            who = [who]
        # Support legacy format for backward compatibility
        if "experience_text" in d and "when" not in d:
            return Experience(
                exp_id=d["exp_id"],
                who=who,
                when=d["experience_text"],
                what=d["experience_text"],
            )
        return Experience(
            exp_id=d["exp_id"],
            who=who,
            when=d["when"],
            what=d["what"],
        )


class ExperienceConfig(ModuleConfig):
    def _configure(self) -> None:
        self._set_name("experience")

        self.selection_prompt_path = self._get_path(
            "selection_prompt_path",
            os.path.join(
                os.path.dirname(__file__),
                "experience_selection_prompt.yaml",
            ),
        )

        self.llm_alias = self._get_str("llm_alias", default="", required=False)


class ExperienceGenerator:
    @inject
    def __init__(
        self,
        llm_api: LLMApi,
        config: ExperienceConfig,
        logger: TelemetryLogger,
        tracing: Tracing,
    ):
        self.config = config
        self.llm_api = llm_api
        self.logger = logger
        self.tracing = tracing

        self.selection_prompt_template = read_yaml(self.config.selection_prompt_path)["content"]

        self.experience_list: List[Experience] = []

        self.experience_dir = None
        self.sub_path = None

    def set_experience_dir(self, experience_dir: str):
        self.experience_dir = experience_dir

    def set_sub_path(self, sub_path: str):
        self.sub_path = sub_path

    @tracing_decorator
    def refresh(self):
        """Load handcrafted experiences from the experience directory."""
        exp_dir = self.get_experience_dir()

        if not os.path.exists(exp_dir):
            self.logger.warning(f"Experience directory {exp_dir} does not exist. No experiences loaded.")
            return

        handcrafted_exp_files = [
            exp_file
            for exp_file in os.listdir(exp_dir)
            if exp_file.startswith("handcrafted_exp_") and exp_file.endswith(".yaml")
        ]

        if len(handcrafted_exp_files) == 0:
            self.logger.warning(
                "No handcrafted experience found. "
                "Please create handcrafted_exp_{id}.yaml files in the experience directory.",
            )
            return

        self.logger.info(f"Found {len(handcrafted_exp_files)} handcrafted experience file(s) in {exp_dir}.")

    @tracing_decorator
    def load_experience(self):
        """Load handcrafted experiences into memory."""
        exp_dir = self.get_experience_dir()

        if not os.path.exists(exp_dir):
            self.logger.warning(f"Experience directory {exp_dir} does not exist.")
            return

        handcrafted_exp_files = [
            exp_file
            for exp_file in os.listdir(exp_dir)
            if exp_file.startswith("handcrafted_exp_") and exp_file.endswith(".yaml")
        ]

        if len(handcrafted_exp_files) == 0:
            self.logger.warning("No handcrafted experience files found.")
            return

        loaded_ids = {exp.exp_id for exp in self.experience_list}

        for exp_file in handcrafted_exp_files:
            exp_file_path = os.path.join(exp_dir, exp_file)
            experience_data = read_yaml(exp_file_path)
            experience_obj = Experience.from_dict(experience_data)

            if experience_obj.exp_id in loaded_ids:
                continue

            self.experience_list.append(experience_obj)
            loaded_ids.add(experience_obj.exp_id)
            self.logger.info(
                f"Loaded experience [{experience_obj.exp_id}] from {exp_file} "
                f"targeting {experience_obj.who or 'all roles'}",
            )

        self.logger.info(f"Loaded {len(self.experience_list)} experience(s) in total.")

    @tracing_decorator
    def retrieve_experience(
        self,
        user_query: str,
        role: Optional[str] = None,
        conversation_context: Optional[str] = None,
        prompt_log_path: Optional[str] = None,
    ) -> List[Experience]:
        """Use LLM to select relevant experiences based on user query and conversation context.

        Args:
            user_query: The current user query
            role: Role alias to filter experiences by their "who" field.
                  Only experiences targeting this role (or all roles) are considered.
            conversation_context: Optional conversation history for better context
            prompt_log_path: Optional path to dump the selection prompt for debugging

        Returns:
            List of selected Experience objects
        """
        role_tag = f"[{role}] " if role else ""

        # Filter by role: include experiences that target this role or target all roles (empty who)
        candidates = [
            exp for exp in self.experience_list
            if len(exp.who) == 0 or role is None or role in exp.who
        ]
        skipped = len(self.experience_list) - len(candidates)
        if skipped > 0:
            self.logger.info(
                f"{role_tag}Filtered {skipped} experience(s) not targeting role, "
                f"{len(candidates)} candidate(s) remaining",
            )

        if len(candidates) == 0:
            self.logger.info(f"{role_tag}No experiences available.")
            return []

        self.logger.info(
            f"{role_tag}Selecting from {len(candidates)} experience(s) "
            f"[{', '.join(e.exp_id for e in candidates)}]",
        )

        if conversation_context:
            self.logger.debug(f"{role_tag}Conversation context for selection:\n{conversation_context}")

        # Format experiences for the LLM prompt (only show "when" sections for selection)
        experiences_text = ""
        for idx, exp in enumerate(candidates):
            experiences_text += f"\n--- Experience {idx + 1} (ID: {exp.exp_id}) ---\n{exp.when}\n"

        # Build the selection prompt
        context_section = f"\n\nConversation Context:\n{conversation_context}" if conversation_context else ""

        prompt = self.selection_prompt_template.format(
            experiences=experiences_text,
            user_query=user_query,
            context=context_section,
        )

        messages = [
            format_chat_message("system", prompt),
            format_chat_message("user", f"Select relevant experiences for: {user_query}"),
        ]

        self.tracing.set_span_attribute("prompt", json.dumps(messages, indent=2))
        prompt_size = self.tracing.count_tokens(json.dumps(messages))
        self.tracing.set_span_attribute("prompt_size", prompt_size)
        self.tracing.add_prompt_size(
            size=prompt_size,
            labels={"direction": "input"},
        )

        if prompt_log_path is not None:
            self.logger.dump_prompt_file(messages, prompt_log_path)

        self.logger.info(f"{role_tag}Sending experience selection request to LLM (prompt_size={prompt_size})")

        # Get LLM response
        response = self.llm_api.chat_completion(messages, llm_alias=self.config.llm_alias)
        selected_ids_text = response["content"]

        output_size = self.tracing.count_tokens(selected_ids_text)
        self.tracing.set_span_attribute("output_size", output_size)
        self.tracing.add_prompt_size(
            size=output_size,
            labels={"direction": "output"},
        )

        self.logger.info(f"{role_tag}LLM selection response: {selected_ids_text}")

        # Parse the response to extract experience IDs
        selected_experiences = self._parse_selected_experience_ids(selected_ids_text)

        self.logger.info(
            f"{role_tag}Selected {len(selected_experiences)}/{len(candidates)} experience(s): "
            f"[{', '.join(e.exp_id for e in selected_experiences)}]",
        )

        return selected_experiences

    def _parse_selected_experience_ids(self, llm_response: str) -> List[Experience]:
        """Parse LLM response to extract selected experience IDs.

        Expected formats:
        - JSON array: ["exp-1", "exp-2"]
        - JSON object with boolean values: {"exp-1": true, "exp-2": false}
        """
        try:
            # Try to parse as JSON
            parsed = json.loads(llm_response)
            if isinstance(parsed, list):
                selected_ids = parsed
            elif isinstance(parsed, dict):
                # Handle {"exp-id": true/false} format (e.g. when response_format=json_object)
                selected_ids = [k for k, v in parsed.items() if v]
            else:
                self.logger.warning(f"Unexpected LLM response type: {llm_response}")
                return []
        except json.JSONDecodeError:
            # Fallback: extract IDs from text
            self.logger.warning(f"Failed to parse LLM response as JSON, trying text extraction: {llm_response}")
            import re
            selected_ids = re.findall(r'["\']([^"\']+)["\']', llm_response)

        # Match IDs to experiences
        selected_experiences = []
        for exp_id in selected_ids:
            matching_exps = [exp for exp in self.experience_list if exp.exp_id == exp_id]
            if matching_exps:
                selected_experiences.append(matching_exps[0])
            else:
                self.logger.warning(f"Experience ID {exp_id} not found in experience list.")

        return selected_experiences

    def _delete_exp_file(self, exp_file_name: str):
        exp_dir = self.get_experience_dir()

        if exp_file_name in os.listdir(exp_dir):
            os.remove(os.path.join(exp_dir, exp_file_name))
            self.logger.info(f"Experience {exp_file_name} deleted.")
        else:
            self.logger.info(f"Experience {exp_file_name} not found.")

    def get_experience_dir(self):
        assert self.experience_dir is not None, "Experience directory is not set. Call set_experience_dir() first."
        return os.path.join(self.experience_dir, self.sub_path) if self.sub_path else self.experience_dir

    def delete_handcrafted_experience(self, exp_id: str):
        """Delete a handcrafted experience file."""
        exp_file_name = f"handcrafted_exp_{exp_id}.yaml"
        self._delete_exp_file(exp_file_name)

    @staticmethod
    def format_experience_in_prompt(
        prompt_template: str,
        selected_experiences: Optional[List[Experience,]] = None,
    ):
        """Format selected experiences for injection into prompts.

        Only injects the 'what' sections (detailed instructions) into the prompt.
        The 'when' sections were already used for selection.
        """
        if selected_experiences is not None and len(selected_experiences) > 0:
            return prompt_template.format(
                experiences="===================\n"
                + "\n===================\n".join(
                    [exp.what for exp in selected_experiences],
                ),
            )
        else:
            return ""
