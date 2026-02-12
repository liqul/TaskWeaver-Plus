import json
import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from openai import AzureOpenAI, OpenAI

from prompts import NEEDS_RESPONSE_PROMPT, TASK_COMPLETION_CHECK_PROMPT, TESTER_FOLLOW_UP_PROMPT

from taskweaver.app.app import TaskWeaverApp
from taskweaver.llm import LLMApi
from taskweaver.memory.attachment import AttachmentType


@dataclass
class ConversationTurn:
    """A single turn in the conversation."""

    role: str  # "user" or "agent"
    message: str
    posts: Optional[List] = None


class Tester:
    """Drives a test conversation with a TaskWeaver agent.

    Flow:
    1. Send task_description directly as the first user message.
    2. If the agent asks a follow-up question, use LLM to answer
       based on the task_description context.
    3. Loop until the agent reports completion or max_rounds is reached.
    """

    def __init__(
        self,
        task_description: str,
        app_dir: str,
        config_var: Optional[Dict] = None,
        max_rounds: int = 10,
        app: Optional[TaskWeaverApp] = None,
        llm_client: Optional[Union[OpenAI, AzureOpenAI]] = None,
        model_name: Optional[str] = None,
        files: Optional[List[Dict]] = None,
    ):
        self.task_description = task_description
        self.max_rounds = max_rounds
        self.files = files

        if app is not None:
            self.app = app
            self._owns_app = False
        else:
            self.app = TaskWeaverApp(app_dir=app_dir, config=config_var)
            self._owns_app = True

        self.session = self.app.get_session()
        self.session_id = self.session.session_id

        if llm_client is not None and model_name is not None:
            self.llm_client: Union[OpenAI, AzureOpenAI] = llm_client
            self.model_name: str = model_name
        else:
            llm_api = self.app.app_injector.get(LLMApi)
            service = llm_api.completion_service
            self.llm_client = service.client
            self.model_name = service.config.model

        self.conversation: List[ConversationTurn] = []

    _TERMINAL_STOP_REASONS = {"SecurityRisks", "UserCancelled"}
    _INTERACTIVE_STOP_REASONS = {"Clarification", "AdditionalInformation", "TaskFailure"}

    def run(self) -> List[ConversationTurn]:
        """Run the full test conversation. Returns conversation history."""
        print("-" * 80)
        print(f"Task: {self.task_description}")
        print("-" * 80)

        user_message = self.task_description
        round_num = 0

        while round_num < self.max_rounds:
            round_num += 1
            print(f"\n{'=' * 60}")
            print(f"[Round {round_num}]")
            print(f"{'=' * 60}")

            agent_response, round_posts = self._send_to_agent(
                user_message,
                files=self.files if round_num == 1 else None,
            )

            self.conversation.append(ConversationTurn(role="user", message=user_message))
            self.conversation.append(
                ConversationTurn(role="agent", message=agent_response, posts=round_posts),
            )

            if round_num >= self.max_rounds:
                print("Max rounds reached.")
                break

            should_continue, user_message = self._decide_continuation(
                agent_response,
                round_posts,
            )
            if not should_continue:
                print("Agent appears to have completed the task.")
                break

        return self.conversation

    def _decide_continuation(
        self,
        agent_response: str,
        round_posts: list,
    ) -> Tuple[bool, str]:
        """Decide whether to continue the conversation and what to send next.

        Returns (should_continue, next_user_message).
        """
        stop_reason = self._get_stop_reason(round_posts)

        if stop_reason is None:
            needs_response = self._agent_needs_response(agent_response)
            if not needs_response:
                return False, ""
            return True, self._generate_follow_up(agent_response)

        if stop_reason in self._TERMINAL_STOP_REASONS:
            print(f"  [Stop: {stop_reason}] — terminating.")
            return False, ""

        if stop_reason in self._INTERACTIVE_STOP_REASONS:
            print(f"  [Stop: {stop_reason}] — generating follow-up.")
            return True, self._generate_follow_up(agent_response)

        if stop_reason == "Completed":
            if self._is_task_complete(agent_response, round_posts):
                return False, ""
            print("  [Stop: Completed] but task is incomplete — requesting continuation.")
            return True, (
                "You indicated the task is done, but not all steps have been completed. "
                "Please continue with the remaining steps."
            )

        needs_response = self._agent_needs_response(agent_response)
        if not needs_response:
            return False, ""
        return True, self._generate_follow_up(agent_response)

    def _send_to_agent(self, message: str, files: Optional[List[Dict]] = None) -> Tuple[str, list]:
        """Send a message to the TaskWeaver agent and return (response, posts)."""
        response_round = self.session.send_message(message, event_handler=None, files=files)

        if response_round.state == "failed":
            print("  [Round FAILED]")
            return "[Agent failed to respond. An error occurred during processing.]", []

        self._display_round(response_round)

        return response_round.post_list[-1].message, response_round.post_list

    def _display_round(self, response_round) -> None:
        """Display all posts and their attachments in a round."""
        for post in response_round.post_list:
            print(f"  {post.send_from} -> {post.send_to}:")
            if post.message:
                print(f"    {post.message}")
            for att in post.attachment_list:
                label = att.type.value.upper()
                content = att.content
                if att.type.value in ("reply_content", "plan"):
                    # Show code and plans in full with indent
                    lines = content.splitlines()
                    print(f"    [{label}]")
                    for line in lines:
                        print(f"      {line}")
                elif att.type.value == "execution_result":
                    print(f"    [{label}] {content}")
                elif att.type.value == "execution_status":
                    print(f"    [{label}] {content}")
                elif att.type.value == "code_error":
                    print(f"    [{label}] {content}")
            print()

    @staticmethod
    def _get_stop_reason(posts: list) -> Optional[str]:
        """Extract the 'stop' attachment value from the Planner->User post."""
        for post in reversed(posts):
            if post.send_to == "User":
                stop_attachments = post.get_attachment(AttachmentType.stop)
                if stop_attachments:
                    return stop_attachments[0].content.strip()
        return None

    def _is_task_complete(self, agent_response: str, posts: list) -> bool:
        """Use LLM to check whether ALL parts of the task were completed."""
        all_posts_text = self._format_full_conversation_posts()
        system_prompt = TASK_COMPLETION_CHECK_PROMPT.format(
            task_description=self.task_description,
            agent_response=agent_response,
            agent_posts=all_posts_text,
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Is the task fully complete?"},
        ]

        response = (
            self.llm_client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0,
            )
            .choices[0]
            .message.content
        ) or ""

        try:
            result = json.loads(response)
            return result.get("is_complete", "no").strip().lower() == "yes"
        except (json.JSONDecodeError, AttributeError):
            return "yes" in response.lower()

    @staticmethod
    def _format_posts_for_completion_check(posts: list) -> str:
        parts = []
        for post in posts:
            header = f"[{post.send_from} -> {post.send_to}]"
            post_lines = [header]
            if post.message:
                post_lines.append(post.message)
            for att in post.attachment_list:
                att_type = att.type.value
                if att_type in (
                    "reply_content",
                    "execution_result",
                    "execution_status",
                    "code_error",
                    "plan",
                    "current_plan_step",
                    "thought",
                    "function",
                    "stop",
                ):
                    post_lines.append(f"<{att_type}>\n{att.content}\n</{att_type}>")
            parts.append("\n".join(post_lines))
        return "\n\n".join(parts)

    def _format_full_conversation_posts(self) -> str:
        round_sections = []
        for i, turn in enumerate(self.conversation):
            if turn.role == "agent" and turn.posts:
                round_sections.append(
                    f"--- Round {(i // 2) + 1} ---\n"
                    + self._format_posts_for_completion_check(turn.posts),
                )
        return "\n\n".join(round_sections)

    def _agent_needs_response(self, agent_response: str) -> bool:
        """Use LLM to determine if the agent is asking a follow-up question.
        Fallback for non-planner scenarios."""
        system_prompt = NEEDS_RESPONSE_PROMPT.format(
            task_description=self.task_description,
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": agent_response},
        ]

        response = (
            self.llm_client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0,
                max_tokens=10,
            )
            .choices[0]
            .message.content.strip()
            .lower()
        )

        return "yes" in response

    def _generate_follow_up(self, agent_response: str) -> str:
        """Use LLM to generate a follow-up answer based on task_description context."""
        system_prompt = TESTER_FOLLOW_UP_PROMPT.format(
            task_description=self.task_description,
        )

        # Build conversation context: tester is "assistant", agent is "user"
        messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for turn in self.conversation:
            role = "assistant" if turn.role == "user" else "user"
            messages.append({"role": role, "content": turn.message})
        messages.append({"role": "user", "content": agent_response})

        response = (
            self.llm_client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0,
            )
            .choices[0]
            .message.content
        )

        return response

    def close(self):
        """Clean up resources. Only stops the app if this Tester created it."""
        if self._owns_app:
            self.app.stop()
        else:
            self.app.session_manager.stop_session(self.session_id)
