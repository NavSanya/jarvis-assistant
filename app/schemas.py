from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str = Field(default="default-session", min_length=1, max_length=100)
    message: str = Field(min_length=1)


class VoiceRequest(BaseModel):
    session_id: str = Field(default="default-session", min_length=1, max_length=100)
    transcript_override: str | None = None


class ToolCallResult(BaseModel):
    tool_name: str
    output: dict[str, Any]


class EmotionDebug(BaseModel):
    final_emotion: str
    audio_emotion: str
    audio_score: float
    text_emotion: str
    text_score: float
    decision_source: str


class ChatResponse(BaseModel):
    session_id: str
    user_message: str
    assistant_message: str
    detected_emotion: str
    emotion_debug: EmotionDebug | None = None
    transcript: str | None = None
    tools_used: list[ToolCallResult] = Field(default_factory=list)
    audio_path: str | None = None


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
