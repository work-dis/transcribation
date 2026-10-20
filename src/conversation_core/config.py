from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_env: str = "development"
    telegram_bot_token: str | None = None
    telegram_api_id: int | None = None
    telegram_api_hash: str | None = None
    telegram_recorder_session: str | None = None
    telegram_recorder_display_name: str = "Conversation Assistant"
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    transcription_model: str = "openai/whisper-large-v3-turbo"
    analysis_model: str = "deepseek/deepseek-v4.1-flash"
    openrouter_require_zdr: bool = False
    openrouter_allow_training: bool = False
    database_url: str = "sqlite+aiosqlite:///./conversation_ai.db"
    redis_url: str = "redis://localhost:6379/0"
    temp_dir: str = "/tmp/conversation-ai"
    max_upload_size_mb: int = 500
    max_audio_duration_minutes: int = 180
    max_call_duration_minutes: int = 240
    web_base_url: str = "http://localhost:3000"
    api_base_url: str = "http://localhost:8000"
    log_level: str = "INFO"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

settings = Settings()
