from typing import Any

from app.config import Settings

try:
    from groq import AsyncGroq
except ImportError:  # pragma: no cover - optional dependency
    AsyncGroq = None


class LLMService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = (
            AsyncGroq(api_key=settings.groq_api_key)
            if settings.groq_api_key and AsyncGroq is not None
            else None
        )

    @property
    def provider_status(self) -> str:
        if self.client is not None:
            return "configured"
        if self.settings.groq_api_key:
            return "missing groq sdk"
        return "missing groq api key"

    async def generate_response(
        self,
        *,
        user_message: str,
        emotion: str,
        conversation_context: list[dict[str, Any]],
        tool_outputs: list[dict[str, Any]],
    ) -> str:
        if self.client is None:
            raise RuntimeError(
                "Groq is not configured. Add GROQ_API_KEY and install requirements."
            )

        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "You are Jarvis, a calm and concise AI voice assistant. "
                    "Use any supplied tool output when relevant, and adapt tone "
                    f"to the user's detected emotion: {emotion}."
                ),
            }
        ]
        for item in conversation_context:
            messages.append({"role": item["role"], "content": item["content"]})

        if tool_outputs:
            messages.append(
                {
                    "role": "system",
                    "content": f"Tool output available: {tool_outputs}",
                }
            )

        messages.append({"role": "user", "content": user_message})

        completion = await self.client.chat.completions.create(
            model=self.settings.groq_model,
            messages=messages,
            temperature=0.4,
        )
        return completion.choices[0].message.content or "I could not generate a reply."
