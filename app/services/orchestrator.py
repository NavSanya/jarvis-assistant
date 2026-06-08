from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.schemas import ChatResponse, EmotionDebug, SimulatedWellnessSignal
from app.services.emotion import EmotionService
from app.services.llm import LLMService
from app.services.memory import MemoryService
from app.services.rag import DEFAULT_PERSONA, get_persona_metadata
from app.services.sensevoice import SenseVoiceService
from app.services.stt import SpeechToTextService
from app.services.tts import TextToSpeechService


class AssistantOrchestrator:
    def __init__(self, settings: Settings, llm_service: LLMService) -> None:
        self.settings = settings
        self.llm_service = llm_service
        self.memory_service = MemoryService()
        self.emotion_service = EmotionService(settings)
        self.sensevoice_service = SenseVoiceService(settings)
        self.stt_service = SpeechToTextService(settings)
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

    def _apply_wellness_emotion_hint(
        self,
        *,
        detected_emotion: str,
        emotion_debug: EmotionDebug | None,
        wellness_signal: SimulatedWellnessSignal | None,
    ) -> tuple[str, EmotionDebug | None]:
        wellness_emotion, wellness_score = self.emotion_service.detect_from_wellness(
            wellness_signal
        )
        if wellness_score == 0.0:
            return (detected_emotion, emotion_debug)

        base_debug = emotion_debug or EmotionDebug(
            final_emotion=detected_emotion,
            text_emotion=detected_emotion,
            text_score=0.0,
            decision_source="fallback",
        )
        base_debug.wellness_emotion = wellness_emotion
        base_debug.wellness_score = round(wellness_score, 3)

        text_score = base_debug.text_score or 0.0
        audio_score = base_debug.audio_score or 0.0
        has_stronger_language_signal = max(text_score, audio_score) >= 0.55
        if (
            detected_emotion in {"neutral", "calm"}
            and wellness_emotion != "neutral"
            and wellness_score >= 0.55
            and not has_stronger_language_signal
        ):
            base_debug.final_emotion = wellness_emotion
            base_debug.decision_source = "wellness_signal"
            return (wellness_emotion, base_debug)

        if (
            detected_emotion == "neutral"
            and wellness_emotion == "calm"
            and wellness_score >= 0.55
        ):
            base_debug.final_emotion = "calm"
            base_debug.decision_source = "wellness_signal"
            return ("calm", base_debug)

        return (detected_emotion, base_debug)

    async def handle_chat(
        self,
        *,
        db: AsyncSession,
        session_id: str,
        message: str,
        persona_id: str | None = DEFAULT_PERSONA,
        detected_emotion: str = "neutral",
        emotion_debug: EmotionDebug | None = None,
        wellness_signal: SimulatedWellnessSignal | None = None,
    ) -> ChatResponse:
        persona_metadata = get_persona_metadata(persona_id)
        resolved_persona_id = str(persona_metadata.get("persona_id", DEFAULT_PERSONA))

        if emotion_debug is None and detected_emotion == "neutral":
            try:
                text_emotion_result = await self.emotion_service.detect_from_text(message)
                detected_emotion = str(text_emotion_result["final_emotion"])
                emotion_debug = EmotionDebug(**text_emotion_result)
            except Exception:
                detected_emotion = "neutral"

        detected_emotion, emotion_debug = self._apply_wellness_emotion_hint(
            detected_emotion=detected_emotion,
            emotion_debug=emotion_debug,
            wellness_signal=wellness_signal,
        )

        history = await self.memory_service.get_recent_turns(
            db, session_id=session_id, limit=12
        )

        reply = await self.llm_service.generate_response(
            user_message=message,
            emotion=detected_emotion,
            conversation_context=[
                {"role": turn.role, "content": turn.content} for turn in history
            ],
            persona_id=resolved_persona_id,
            wellness_signal=wellness_signal,
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
            persona_id=resolved_persona_id,
            user_message=message,
            assistant_message=reply,
            detected_emotion=detected_emotion,
            emotion_debug=emotion_debug,
            audio_path=audio_path,
            wellness_signal=wellness_signal,
        )

    async def handle_voice(
        self,
        *,
        db: AsyncSession,
        session_id: str,
        audio_path: Path,
        persona_id: str | None = DEFAULT_PERSONA,
        transcript_override: str | None = None,
        wellness_signal: SimulatedWellnessSignal | None = None,
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
                    persona_id=persona_id,
                    detected_emotion=detected_emotion,
                    emotion_debug=emotion_debug,
                    wellness_signal=wellness_signal,
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
            persona_id=persona_id,
            detected_emotion=detected_emotion,
            emotion_debug=emotion_debug,
            wellness_signal=wellness_signal,
        )
        response.transcript = transcript
        return response
