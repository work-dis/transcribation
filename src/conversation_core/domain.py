from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

class ProcessingMode(str, Enum):
    TRANSCRIPTION = "transcription"
    CLEAN_TRANSCRIPT = "clean_transcript"
    SUMMARY = "summary"
    MEETING_PROTOCOL = "meeting_protocol"
    CONVERSATION_ANALYSIS = "conversation_analysis"

class ConversationStatus(str, Enum):
    CREATED="created"; MEDIA_ATTACHED="media_attached"; QUEUED="queued"; DOWNLOADING="downloading"
    RECORDING="recording"; PREPROCESSING="preprocessing"; TRANSCRIBING="transcribing"; TRANSCRIBED="transcribed"
    DIARIZING="diarizing"; MAPPING_SPEAKERS="mapping_speakers"; PROCESSING="processing"; COMPLETED="completed"; FAILED="failed"

class SourceType(str, Enum):
    TELEGRAM_UPLOAD="telegram_upload"; TELEGRAM_GROUP_CALL="telegram_group_call"; WEB_RECORDING="web_recording"
    ZOOM="zoom"; GOOGLE_MEET="google_meet"; TEAMS="teams"; PHONE="phone"; API="api"; UNKNOWN="unknown"

class TaskItem(BaseModel):
    task: str; assignee: str | None = None; deadline: str | None = None; context: str | None = None
class TranscriptInput(BaseModel):
    raw_text: str
class ParticipantInput(BaseModel):
    display_name: str | None = None; speaker_label: str | None = None
class SegmentInput(BaseModel):
    start_seconds: float | None = None; end_seconds: float | None = None; text: str; speaker_label: str | None = None
class TranscriptionResult(BaseModel):
    text: str; language: str | None = None; duration_seconds: float | None = None; segments: list[SegmentInput] = Field(default_factory=list)
class ProcessingResult(BaseModel):
    mode: ProcessingMode; data: dict[str, Any]
