from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.schemas import ChatResponse, EmotionDebug, ToolCallResult
from app.services.emotion import EmotionService
from app.services.llm import LLMService
from app.services.memory import MemoryService
from app.services.sensevoice import SenseVoiceService
from app.services.stt import SpeechToTextService
from app.services.tools import MCPToolService
from app.services.tts import TextToSpeechService


class AssistantOrchestrator:
    def __init__(self, settings: Settings, llm_service: LLMService) -> None:
        self.settings = settings
        self.llm_service = llm_service
        self.memory_service = MemoryService()
        self.emotion_service = EmotionService(settings)
        self.sensevoice_service = SenseVoiceService(settings)
        self.stt_service = SpeechToTextService(settings)
        self.tool_service = MCPToolService(settings)
        self.tts_service = TextToSpeechService(settings, Path(settings.audio_output_dir))

    @property
    def stt_provider_status(self) -> str:
        if self.sensevoice_service.enabled:
            return self.sensevoice_service.provider_status
        return self.stt_service.provider_status

    @property
    def emotion_provider_status(self) -> str:
        if self.sensevoice_service.enabled:
            return self.sensevoice_service.provider_status
        return self.emotion_service.provider_status

    async def handle_chat(
        self,
        *,
        db: AsyncSession,
        session_id: str,
        message: str,
        detected_emotion: str = "neutral",
        emotion_debug: EmotionDebug | None = None,
    ) -> ChatResponse:
        history = await self.memory_service.get_recent_turns(
            db, session_id=session_id, limit=8
        )
        session_summary = " | ".join(f"{turn.role}: {turn.content}" for turn in history[-4:])

        tool_calls = []
        for tool_name in self.tool_service.discover_tool_calls(message):
            arguments = (
                {"timezone": "America/Los_Angeles"}
                if tool_name == "get_time"
                else {"summary": session_summary}
            )
            output = await self.tool_service.run_tool(tool_name, arguments=arguments)
            tool_calls.append(ToolCallResult(tool_name=tool_name, output=output))

        reply = await self.llm_service.generate_response(
            user_message=message,
            emotion=detected_emotion,
            conversation_context=[
                {"role": turn.role, "content": turn.content} for turn in history
            ],
            tool_outputs=[tool.model_dump() for tool in tool_calls],
        )

        audio_path = await self.tts_service.synthesize(session_id, reply)

        await self.memory_service.add_turn(
            db,
            session_id=session_id,
            role="user",
            content=message,
            emotion=detected_emotion,
        )
        await self.memory_service.add_turn(
            db,
            session_id=session_id,
            role="assistant",
            content=reply,
            emotion=detected_emotion,
        )

        return ChatResponse(
            session_id=session_id,
            user_message=message,
            assistant_message=reply,
            detected_emotion=detected_emotion,
            emotion_debug=emotion_debug,
            tools_used=tool_calls,
            audio_path=audio_path,
        )

    async def handle_voice(
        self,
        *,
        db: AsyncSession,
        session_id: str,
        audio_path: Path,
        transcript_override: str | None = None,
    ) -> ChatResponse:
        if self.sensevoice_service.enabled:
            try:
                sensevoice_result = await self.sensevoice_service.process(audio_path)
                detected_emotion = str(sensevoice_result["final_emotion"])
                transcript = transcript_override or str(sensevoice_result["transcript"])
                emotion_debug = EmotionDebug(**sensevoice_result)
                response = await self.handle_chat(
                    db=db,
                    session_id=session_id,
                    message=transcript,
                    detected_emotion=detected_emotion,
                    emotion_debug=emotion_debug,
                )
                response.transcript = transcript
                return response
            except Exception:
                pass

        transcript = await self.stt_service.transcribe(
            audio_path,
            transcript_override=transcript_override,
        )
        emotion_debug = None
        try:
            emotion_result = await self.emotion_service.detect_hybrid(
                audio_path,
                transcript,
            )
            detected_emotion = str(emotion_result["final_emotion"])
            emotion_debug = EmotionDebug(**emotion_result)
        except Exception:
            detected_emotion = "neutral"
        response = await self.handle_chat(
            db=db,
            session_id=session_id,
            message=transcript,
            detected_emotion=detected_emotion,
            emotion_debug=emotion_debug,
        )
        response.transcript = transcript
        return response
