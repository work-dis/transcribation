from pathlib import Path
from .db import Session, ConversationModel, MediaAssetModel, TranscriptModel, TranscriptSegmentModel, ProcessingResultModel, AIUsageModel, get_transcript, get_result
from .domain import ConversationStatus, ProcessingMode, SourceType, TranscriptInput
from .config import settings
from .processing import OpenRouterTranscriptionProvider, OpenRouterConversationProcessingProvider
from .media import LocalMediaStorage

ALLOWED = {
    ConversationStatus.CREATED: {ConversationStatus.MEDIA_ATTACHED, ConversationStatus.RECORDING, ConversationStatus.QUEUED},
    ConversationStatus.MEDIA_ATTACHED: {ConversationStatus.QUEUED, ConversationStatus.DOWNLOADING, ConversationStatus.TRANSCRIBING},
    ConversationStatus.QUEUED: {ConversationStatus.DOWNLOADING, ConversationStatus.TRANSCRIBING, ConversationStatus.FAILED},
    ConversationStatus.DOWNLOADING: {ConversationStatus.PREPROCESSING, ConversationStatus.FAILED},
    ConversationStatus.RECORDING: {ConversationStatus.QUEUED, ConversationStatus.FAILED},
    ConversationStatus.PREPROCESSING: {ConversationStatus.TRANSCRIBING, ConversationStatus.FAILED},
    ConversationStatus.TRANSCRIBING: {ConversationStatus.TRANSCRIBED, ConversationStatus.FAILED},
    ConversationStatus.TRANSCRIBED: {ConversationStatus.DIARIZING, ConversationStatus.PROCESSING, ConversationStatus.COMPLETED},
    ConversationStatus.DIARIZING: {ConversationStatus.MAPPING_SPEAKERS, ConversationStatus.PROCESSING, ConversationStatus.FAILED},
    ConversationStatus.MAPPING_SPEAKERS: {ConversationStatus.PROCESSING, ConversationStatus.FAILED},
    ConversationStatus.PROCESSING: {ConversationStatus.COMPLETED, ConversationStatus.FAILED},
    ConversationStatus.COMPLETED: {ConversationStatus.PROCESSING},
    ConversationStatus.FAILED: {ConversationStatus.QUEUED},
}
def transition(current: ConversationStatus, target: ConversationStatus) -> ConversationStatus:
    if target not in ALLOWED.get(current, set()): raise ValueError(f"invalid conversation transition: {current} -> {target}")
    return target

class ConversationService:
    async def transcribe(self, conversation_id: str, *, provider=None):
        provider = provider or OpenRouterTranscriptionProvider()
        async with Session() as s:
            conversation=await s.get(ConversationModel,conversation_id)
            if not conversation: raise ValueError("conversation not found")
            cached=await get_transcript(s,conversation_id)
            if cached: return cached, True
            asset=(await s.execute(__import__('sqlalchemy').select(MediaAssetModel).where(MediaAssetModel.conversation_id==conversation_id).order_by(MediaAssetModel.created_at.desc()))).scalars().first()
            if not asset or not asset.temporary_path: raise ValueError("media not found")
            conversation.status=transition(conversation.status,ConversationStatus.TRANSCRIBING)
            try:
                result=await provider.transcribe(Path(asset.temporary_path),language=conversation.language)
                transcript=TranscriptModel(conversation_id=conversation_id,provider=provider.__class__.__name__,model=settings.transcription_model,language=result.language,raw_text=result.text)
                s.add(transcript); await s.flush()
                for segment in result.segments: s.add(TranscriptSegmentModel(transcript_id=transcript.id,start_seconds=segment.start_seconds,end_seconds=segment.end_seconds,text=segment.text,speaker_label=segment.speaker_label))
                conversation.status=ConversationStatus.TRANSCRIBED; conversation.language=result.language; conversation.duration_seconds=result.duration_seconds
                s.add(AIUsageModel(conversation_id=conversation_id,operation="transcription",provider=provider.__class__.__name__,model=settings.transcription_model,duration_seconds=result.duration_seconds)); await s.commit(); return transcript, False
            except Exception:
                conversation.status=ConversationStatus.FAILED; await s.commit(); raise
    async def process(self, conversation_id: str, mode: ProcessingMode, *, provider=None, force=False):
        provider=provider or OpenRouterConversationProcessingProvider()
        async with Session() as s:
            conversation=await s.get(ConversationModel,conversation_id); transcript=await get_transcript(s,conversation_id)
            if not conversation or not transcript: raise ValueError("conversation or transcript not found")
            cached=await get_result(s,conversation_id,mode)
            if cached and not force: return cached, True
            conversation.status=transition(conversation.status,ConversationStatus.PROCESSING)
            try:
                result=await provider.process(transcript=TranscriptInput(raw_text=transcript.raw_text),mode=mode,participants=[],segments=[])
                if cached: cached.result_json=result.data; row=cached
                else: row=ProcessingResultModel(conversation_id=conversation_id,mode=mode,provider=provider.__class__.__name__,model=settings.analysis_model,result_json=result.data); s.add(row)
                await s.flush(); s.add(AIUsageModel(conversation_id=conversation_id,processing_result_id=row.id,operation=mode.value,provider=provider.__class__.__name__,model=settings.analysis_model)); conversation.status=ConversationStatus.COMPLETED; await s.commit(); return row, False
            except Exception:
                conversation.status=ConversationStatus.FAILED; await s.commit(); raise
    async def cleanup_media(self, conversation_id: str): LocalMediaStorage().cleanup(conversation_id)
