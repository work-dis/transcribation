import json
from typing import Any
import httpx
from .config import settings
from .domain import *
from .prompts import prompt_for

class OpenRouterClient:
    def __init__(self, api_key: str | None = None): self.api_key = api_key or settings.openrouter_api_key
    async def _chat(self, prompt: str, *, json_mode: bool = False) -> str:
        if not self.api_key: raise RuntimeError("OPENROUTER_API_KEY is required for AI processing")
        headers = {"Authorization": f"Bearer {self.api_key}", "HTTP-Referer": settings.web_base_url, "X-Title": "Conversation Assistant"}
        body: dict[str, Any] = {"model": settings.analysis_model, "messages": [{"role":"user","content":prompt}], "temperature": 0.1}
        if json_mode: body["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.post(f"{settings.openrouter_base_url}/chat/completions", headers=headers, json=body); r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

class OpenRouterTranscriptionProvider:
    async def transcribe(self, audio_path, *, language=None):
        if not settings.openrouter_api_key: raise RuntimeError("OPENROUTER_API_KEY is required for transcription")
        headers = {"Authorization": f"Bearer {settings.openrouter_api_key}"}
        data = {"model": settings.transcription_model}
        if language: data["language"] = language
        async with httpx.AsyncClient(timeout=300) as client:
            with open(audio_path, "rb") as audio:
                r = await client.post(f"{settings.openrouter_base_url}/audio/transcriptions", headers=headers, data=data, files={"file": (audio_path.name, audio, "application/octet-stream")})
            r.raise_for_status(); payload = r.json()
        return TranscriptionResult(text=payload.get("text", ""), language=payload.get("language"), duration_seconds=payload.get("duration"))

class OpenRouterConversationProcessingProvider:
    async def process(self, *, transcript: TranscriptInput, mode: ProcessingMode, participants: list[ParticipantInput], segments: list[SegmentInput]) -> ProcessingResult:
        if mode == ProcessingMode.TRANSCRIPTION: return ProcessingResult(mode=mode, data={"text": transcript.raw_text})
        raw = await OpenRouterClient()._chat(prompt_for(mode, transcript.raw_text), json_mode=mode != ProcessingMode.CLEAN_TRANSCRIPT)
        try: data = json.loads(raw) if mode != ProcessingMode.CLEAN_TRANSCRIPT else {"clean_text": raw}
        except json.JSONDecodeError as e: raise ValueError(f"Provider returned invalid JSON: {e}") from e
        return ProcessingResult(mode=mode, data=data)

def chunk_text(text: str, max_chars: int = 12000) -> list[str]:
    return [text[i:i+max_chars] for i in range(0, len(text), max_chars)] or [""]
def dedupe_items(items: list[Any]) -> list[Any]:
    seen: set[str] = set(); out=[]
    for item in items:
        key=json.dumps(item, sort_keys=True, ensure_ascii=False) if isinstance(item,(dict,list)) else str(item)
        if key not in seen: seen.add(key); out.append(item)
    return out
