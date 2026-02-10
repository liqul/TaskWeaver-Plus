import json
from dataclasses import dataclass
from typing import List, Tuple, Union

from openai import AzureOpenAI, OpenAI

from prompts import JUDGE_PROMPT


@dataclass
class ScoringPoint:
    score_point: str
    weight: float


@dataclass
class JudgmentResult:
    score_point: str
    weight: float
    is_hit: bool
    reason: str


class Judge:
    """Evaluates conversation against scoring points using LLM."""

    def __init__(
        self,
        llm_client: Union[OpenAI, AzureOpenAI],
        model_name: str,
    ):
        self.llm_client = llm_client
        self.model_name = model_name

    def evaluate(
        self,
        task_description: str,
        conversation: list,
        scoring_points: List[ScoringPoint],
    ) -> Tuple[float, float, List[JudgmentResult]]:
        """Evaluate conversation against all scoring points.

        Returns:
            (raw_score, normalized_score, list_of_judgment_results)
        """
        max_score = sum(sp.weight for sp in scoring_points)
        total_score = 0.0
        results: List[JudgmentResult] = []

        conversation_text = self._format_conversation(conversation)

        for idx, sp in enumerate(scoring_points):
            is_hit, reason = self._judge_single(task_description, conversation_text, sp)
            result = JudgmentResult(
                score_point=sp.score_point,
                weight=sp.weight,
                is_hit=is_hit,
                reason=reason,
            )
            results.append(result)

            single_score = sp.weight if is_hit else 0
            total_score += single_score
            status = "PASS" if is_hit else "FAIL"
            print(
                f"  [{idx + 1}/{len(scoring_points)}] {status} "
                f"(weight={sp.weight}): {sp.score_point}",
            )
            if reason:
                print(f"    Reason: {reason}")

        normalized_score = total_score / max_score if max_score > 0 else 0
        return total_score, normalized_score, results

    @staticmethod
    def _format_conversation(conversation: list) -> str:
        """Format conversation turns into readable text."""
        lines = []
        for turn in conversation:
            if turn.role == "user":
                lines.append(f"User: {turn.message}")
            elif turn.posts:
                lines.append(Judge._format_agent_posts(turn.posts))
            else:
                lines.append(f"Agent: {turn.message}")
        return "\n\n".join(lines)

    @staticmethod
    def _format_agent_posts(posts: list) -> str:
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
                    "thought",
                    "function",
                ):
                    post_lines.append(f"<{att_type}>\n{att.content}\n</{att_type}>")
            parts.append("\n".join(post_lines))
        return "\n\n".join(parts)

    def _judge_single(
        self,
        task_description: str,
        conversation_text: str,
        scoring_point: ScoringPoint,
    ) -> Tuple[bool, str]:
        """Judge a single scoring point. Returns (is_hit, reason)."""
        user_content = (
            f"## Task Description\n{task_description}\n\n"
            f"## Conversation\n{conversation_text}\n\n"
            f"## Scoring Criterion\n{scoring_point.score_point}"
        )

        messages = [
            {"role": "system", "content": JUDGE_PROMPT},
            {"role": "user", "content": user_content},
        ]

        response = (
            self.llm_client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0,
            )
            .choices[0]
            .message.content
        )

        return self._parse_judgment(response)

    @staticmethod
    def _parse_judgment(response: str) -> Tuple[bool, str]:
        """Parse LLM judgment response into (is_hit, reason)."""
        try:
            result = json.loads(response)
            is_hit = result["is_hit"].strip().lower() == "yes"
            reason = result.get("reason", "")
            return is_hit, reason
        except (json.JSONDecodeError, KeyError):
            response_lower = response.lower()
            if "yes" in response_lower:
                return True, response
            elif "no" in response_lower:
                return False, response
            else:
                return False, f"Could not parse judgment: {response}"
