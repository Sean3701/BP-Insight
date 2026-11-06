from typing import Protocol

class LLMAdapter(Protocol):
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Model-independent generation interface. No external calls in M01."""
        ...
