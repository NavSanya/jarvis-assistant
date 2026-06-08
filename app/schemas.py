from datetime import datetime

from pydantic import AliasChoices, BaseModel, Field, field_validator


class SimulatedWellnessSignal(BaseModel):
    timestamp: datetime | None = None
    heart_rate: int | None = Field(
        default=None,
        ge=40,
        le=180,
        validation_alias=AliasChoices("heart_rate", "heart_rate_bpm"),
    )
    hrv_rmssd_ms: int | None = Field(
        default=None,
        ge=0,
        le=300,
        validation_alias=AliasChoices(
            "hrv_rmssd_ms",
            "heart_rate_variability_ms",
            "hrv_ms",
        ),
    )
    skin_temperature_c: float | None = Field(
        default=None,
        ge=30,
        le=45,
        validation_alias=AliasChoices(
            "skin_temperature_c",
            "skin_temperature_C",
            "skin_temperature",
        ),
    )
    stress_level: str | None = None
    source: str = "manual_demo"

    @field_validator("stress_level", mode="before")
    @classmethod
    def normalize_stress_level(cls, value: str | None):
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        normalized = value.strip().lower()
        return normalized or None


class WellnessSampleOut(SimulatedWellnessSignal):
    suggested_emotion: str | None = None


class ChatRequest(BaseModel):
    session_id: str = Field(default="default-session", min_length=1, max_length=100)
    persona_id: str | None = "default_danny"
    message: str = Field(min_length=1)
    wellness_signal: SimulatedWellnessSignal | None = None


class VoiceRequest(BaseModel):
    session_id: str = Field(default="default-session", min_length=1, max_length=100)
    persona_id: str | None = "default_danny"
    transcript_override: str | None = None
    wellness_signal: SimulatedWellnessSignal | None = None


class EmotionDebug(BaseModel):
    final_emotion: str
    audio_emotion: str | None = None
    audio_score: float | None = None
    text_emotion: str | None = None
    text_score: float | None = None
    wellness_emotion: str | None = None
    wellness_score: float | None = None
    decision_source: str
    provider: str | None = None
    language: str | None = None
    audio_event: str | None = None
    raw_output: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    persona_id: str = "default_danny"
    user_message: str
    assistant_message: str
    detected_emotion: str
    emotion_debug: EmotionDebug | None = None
    transcript: str | None = None
    audio_path: str | None = None
    wellness_signal: SimulatedWellnessSignal | None = None


class ConversationTurnOut(BaseModel):
    role: str
    content: str
    emotion: str | None = None
    created_at: datetime


class ConversationHistoryResponse(BaseModel):
    session_id: str
    turns: list[ConversationTurnOut] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    app_name: str
    environment: str
    providers: dict[str, str]
