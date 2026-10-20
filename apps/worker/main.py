"""ARQ entry point."""
from arq.connections import RedisSettings
from conversation_core.config import settings
from conversation_core.application import ConversationService
from conversation_core.domain import ProcessingMode
async def transcribe_conversation(ctx, conversation_id: str): return await ConversationService().transcribe(conversation_id)
async def process_conversation_mode(ctx, conversation_id: str, mode: str): return await ConversationService().process(conversation_id, ProcessingMode(mode))
async def cleanup_conversation_media(ctx, conversation_id: str): return await ConversationService().cleanup_media(conversation_id)
class WorkerSettings:
    functions=[transcribe_conversation, process_conversation_mode, cleanup_conversation_media]
    redis_settings=RedisSettings.from_dsn(settings.redis_url)
