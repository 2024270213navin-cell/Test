"""
core/prompt_generator.py — Builds structured prompts for NVIDIA LLM.

Responsibilities:
  • Format retrieved context chunks into a readable block
  • Incorporate conversation history (last N turns)
  • Produce a final prompt string ready for the LLM
"""
from __future__ import annotations

from backend.models.schemas import ContextChunk, ConversationTurn
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Maximum number of history turns to include
MAX_HISTORY_TURNS = 3


class PromptGenerator:
    """
    Generates structured prompts for the NVIDIA LLM.

    The prompt follows this pattern:
      [System role + instructions]
      [Knowledge context]
      [Conversation history]
      [Current question]
    """

    SYSTEM_PROMPT = """You are an expert IT Service Desk AI assistant.
Your role is to provide accurate, concise, and actionable resolutions to IT support tickets.

Guidelines:
- Base your answer ONLY on the provided knowledge base context.
- If the context does not contain enough information, clearly state that and suggest escalation.
- Be professional, empathetic, and solution-oriented.
- If steps are required, number them clearly.
- Reference the source from context when relevant.
- Keep responses focused and avoid unnecessary filler text.
- Do NOT hallucinate information not present in the context."""

    def build_prompt(
        self,
        question: str,
        context_chunks: list[ContextChunk],
        history: list[ConversationTurn] | None = None,
    ) -> str:
        """
        Assemble the full prompt string.

        Args:
            question:       The user's current question.
            context_chunks: Retrieved knowledge-base chunks.
            history:        Conversation history (will be trimmed to last N turns).

        Returns:
            A fully formatted prompt string.
        """
        parts: list[str] = []

        # 1. System instructions
        parts.append(self.SYSTEM_PROMPT)
        parts.append("")

        # 2. Knowledge context
        parts.append("=== KNOWLEDGE BASE CONTEXT ===")
        if context_chunks:
            for i, chunk in enumerate(context_chunks, start=1):
                parts.append(self._format_chunk(i, chunk))
        else:
            parts.append("No relevant context found in the knowledge base.")
        parts.append("=== END CONTEXT ===")
        parts.append("")

        # 3. Conversation history
        history = (history or [])[-MAX_HISTORY_TURNS * 2:]  # last N user+assistant pairs
        if history:
            parts.append("=== CONVERSATION HISTORY ===")
            for turn in history:
                label = "User" if turn.role == "user" else "Assistant"
                parts.append(f"{label}: {turn.content}")
            parts.append("=== END HISTORY ===")
            parts.append("")

        # 4. Current question
        parts.append(f"User Question: {question}")
        parts.append("")
        parts.append("Please provide a comprehensive, step-by-step resolution based on the context above.")
        parts.append("Assistant:")

        prompt = "\n".join(parts)
        logger.debug(
            "Prompt built: {} chars, {} context chunks, {} history turns",
            len(prompt),
            len(context_chunks),
            len(history),
        )
        return prompt

    # ─────────────────────────────────────────
    #  Private helpers
    # ─────────────────────────────────────────

    @staticmethod
    def _format_chunk(index: int, chunk: ContextChunk) -> str:
        lines = [
            f"[Context {index}]",
            f"  Category : {chunk.category or 'N/A'}",
            f"  Question : {chunk.question}",
            f"  Response : {chunk.response}",
        ]
        if chunk.reference_information:
            lines.append(f"  Reference: {chunk.reference_information}")
        lines.append(f"  Relevance: {chunk.similarity_score:.2%}")
        return "\n".join(lines)
