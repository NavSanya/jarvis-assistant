import asyncio
import json
from typing import Any

from app.config import Settings
from app.schemas import SimulatedWellnessSignal

try:
    from groq import AsyncGroq
except ImportError:  # pragma: no cover - optional dependency
    AsyncGroq = None

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:  # pragma: no cover - optional dependency
    boto3 = None
    BotoCoreError = ClientError = Exception


class LLMService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.bedrock_error: str | None = None
        self.groq_client = (
            AsyncGroq(api_key=settings.groq_api_key)
            if settings.groq_api_key and AsyncGroq is not None
            else None
        )
        self.bedrock_client = self._create_bedrock_client()

    @property
    def provider_status(self) -> str:
        provider = self.settings.llm_provider

        if provider == "groq" and self.groq_client is not None:
            return "configured"
        if provider == "groq" and self.settings.groq_api_key:
            return "missing groq sdk"
        if provider == "groq":
            return "missing groq api key"
        if provider == "bedrock" and self.bedrock_client is not None:
            return f"configured ({self.settings.bedrock_model_id})"
        if provider == "bedrock" and self.bedrock_error is not None:
            return self.bedrock_error
        if provider == "bedrock" and boto3 is None:
            return "missing boto3"
        return f"unsupported llm provider: {provider}"

    def _create_bedrock_client(self):
        if self.settings.llm_provider != "bedrock" or boto3 is None:
            return None

        session_kwargs: dict[str, str] = {}
        if self.settings.aws_profile_name:
            session_kwargs["profile_name"] = self.settings.aws_profile_name

        try:
            session = boto3.Session(**session_kwargs)
            return session.client(
                "bedrock-runtime",
                region_name=self.settings.bedrock_region,
            )
        except Exception as exc:  # pragma: no cover - depends on local AWS config
            self.bedrock_error = f"bedrock init failed: {exc}"
            return None

    def _build_prompt(
        self,
        *,
        user_message: str,
        emotion: str,
        conversation_context: list[dict[str, Any]],
        tool_outputs: list[dict[str, Any]],
        wellness_signal: SimulatedWellnessSignal | None,
    ) -> str:
        prompt_parts = [
            (
                "You are Jarvis, a calm and concise AI voice assistant. "
                f"Adapt your tone to the user's detected emotion: {emotion}."
            ),
            "Use any supplied tool output when it is relevant to answering the user.",
            self._emotion_guidance(emotion, wellness_signal=wellness_signal),
            (
                "Offer supportive, practical help when the user sounds distressed, but do not "
                "claim to diagnose medical or mental health conditions."
            ),
        ]

        if wellness_signal is not None:
            prompt_parts.append(
                "Simulated wellness signal available: "
                f"heart_rate={wellness_signal.heart_rate}, "
                f"stress_level={wellness_signal.stress_level}, "
                f"source={wellness_signal.source}."
            )

        if conversation_context:
            prompt_parts.append("Conversation so far:")
            for item in conversation_context:
                role = str(item["role"]).capitalize()
                prompt_parts.append(f"{role}: {item['content']}")

        if tool_outputs:
            prompt_parts.append(f"Tool output available: {tool_outputs}")

        prompt_parts.append(f"User: {user_message}")
        prompt_parts.append("Assistant:")
        return "\n\n".join(prompt_parts)

    def _emotion_guidance(
        self,
        emotion: str,
        *,
        wellness_signal: SimulatedWellnessSignal | None,
    ) -> str:
        normalized_emotion = emotion.lower().strip()
        stress_level = (wellness_signal.stress_level or "").lower().strip() if wellness_signal else ""
        elevated_heart_rate = bool(
            wellness_signal is not None
            and wellness_signal.heart_rate is not None
            and wellness_signal.heart_rate >= 105
        )
        high_distress = normalized_emotion in {"fear", "sad", "angry"} or stress_level in {
            "high",
            "elevated",
        }

        if normalized_emotion == "fear" or high_distress or elevated_heart_rate:
            return (
                "Response style: grounded and reassuring. Keep the reply short, lower the energy, "
                "acknowledge stress, and offer one or two stabilizing next steps."
            )
        if normalized_emotion == "sad":
            return (
                "Response style: warm and gentle. Validate the feeling without sounding clinical, "
                "then offer a small practical action or encouragement."
            )
        if normalized_emotion == "angry":
            return (
                "Response style: calm and de-escalating. Do not mirror intensity. Keep phrasing "
                "steady, respectful, and solution-oriented."
            )
        if normalized_emotion in {"happy", "excited", "surprised"}:
            return (
                "Response style: upbeat and clear. Match the positive energy while staying concise "
                "and helpful."
            )
        if normalized_emotion == "calm":
            return (
                "Response style: relaxed and confident. Keep the pacing smooth and the answer clean."
            )
        return "Response style: concise, helpful, and emotionally steady."

    def _extract_bedrock_text(self, response_body: dict[str, Any]) -> str:
        if "content" in response_body and response_body["content"]:
            first_content = response_body["content"][0]
            if isinstance(first_content, dict) and "text" in first_content:
                return str(first_content["text"])

        if "choices" in response_body and response_body["choices"]:
            content = response_body["choices"][0].get("message", {}).get("content", "")
            if isinstance(content, list):
                texts = [
                    part.get("text", "")
                    for part in content
                    if isinstance(part, dict) and part.get("text")
                ]
                return "\n".join(texts).strip()
            return str(content)

        if "output" in response_body and isinstance(response_body["output"], dict):
            message = response_body["output"].get("message", {})
            content = message.get("content", [])
            texts = [
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("text")
            ]
            if texts:
                return "\n".join(texts).strip()

        raise ValueError(f"Unsupported Bedrock response format: {response_body}")

    async def _generate_with_groq(self, messages: list[dict[str, str]]) -> str:
        if self.groq_client is None:
            raise RuntimeError(
                "Groq is not configured. Add GROQ_API_KEY and install requirements."
            )

        completion = await self.groq_client.chat.completions.create(
            model=self.settings.groq_model,
            messages=messages,
            temperature=self.settings.llm_temperature,
            max_tokens=self.settings.llm_max_tokens,
        )
        return completion.choices[0].message.content or "I could not generate a reply."

    async def _generate_with_bedrock(
        self,
        *,
        user_message: str,
        emotion: str,
        conversation_context: list[dict[str, Any]],
        tool_outputs: list[dict[str, Any]],
        wellness_signal: SimulatedWellnessSignal | None,
    ) -> str:
        if self.bedrock_client is None:
            raise RuntimeError(
                "Bedrock is not configured. Install boto3 and provide Bedrock settings."
            )

        payload = {
            "max_tokens": self.settings.llm_max_tokens,
            "temperature": self.settings.llm_temperature,
            "messages": [
                {
                    "role": "user",
                    "content": self._build_prompt(
                        user_message=user_message,
                        emotion=emotion,
                        conversation_context=conversation_context,
                        tool_outputs=tool_outputs,
                        wellness_signal=wellness_signal,
                    ),
                }
            ],
        }

        def invoke() -> dict[str, Any]:
            try:
                response = self.bedrock_client.invoke_model(
                    modelId=self.settings.bedrock_model_id,
                    body=json.dumps(payload),
                )
            except (ClientError, BotoCoreError) as exc:
                message = str(exc)
                if isinstance(exc, ClientError):
                    message = exc.response.get("Error", {}).get("Message", str(exc))
                raise RuntimeError(f"Bedrock invocation failed: {message}") from exc

            return json.loads(response["body"].read())

        response_body = await asyncio.to_thread(invoke)
        text = self._extract_bedrock_text(response_body).strip()
        return text or "I could not generate a reply."

    async def generate_response(
        self,
        *,
        user_message: str,
        emotion: str,
        conversation_context: list[dict[str, Any]],
        tool_outputs: list[dict[str, Any]],
        wellness_signal: SimulatedWellnessSignal | None = None,
    ) -> str:
        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "You are Jarvis, a calm and concise AI voice assistant. "
                    "Use any supplied tool output when relevant, adapt tone "
                    f"to the user's detected emotion: {emotion}, and stay supportive "
                    "without making medical or mental health diagnoses."
                ),
            }
        ]
        messages.append(
            {
                "role": "system",
                "content": self._emotion_guidance(
                    emotion,
                    wellness_signal=wellness_signal,
                ),
            }
        )
        for item in conversation_context:
            messages.append({"role": item["role"], "content": item["content"]})

        if tool_outputs:
            messages.append(
                {
                    "role": "system",
                    "content": f"Tool output available: {tool_outputs}",
                }
            )

        if wellness_signal is not None:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "Simulated wellness signal available for this turn: "
                        f"heart_rate={wellness_signal.heart_rate}, "
                        f"stress_level={wellness_signal.stress_level}, "
                        f"source={wellness_signal.source}."
                    ),
                }
            )

        messages.append({"role": "user", "content": user_message})

        if self.settings.llm_provider == "groq":
            return await self._generate_with_groq(messages)
        if self.settings.llm_provider == "bedrock":
            return await self._generate_with_bedrock(
                user_message=user_message,
                emotion=emotion,
                conversation_context=conversation_context,
                tool_outputs=tool_outputs,
                wellness_signal=wellness_signal,
            )
        raise RuntimeError(f"Unsupported llm provider: {self.settings.llm_provider}")
