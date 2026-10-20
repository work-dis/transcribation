# MASTER PROMPT FOR CODEX
# Conversation Intelligence Platform — Core + Telegram Recorder + Mini App + AI Processing

## 0. Mission

Build a production-ready MVP of a **Conversation Intelligence Platform**.

This is NOT merely a Telegram transcription bot.

The product consists of:

1. **Conversation Core** — reusable processing engine.
2. **Telegram Bot Adapter** — user-facing bot.
3. **Telegram Recorder Agent** — managed Telegram user-client that can join Telegram group voice/video chats and capture incoming audio.
4. **Telegram Mini App / Web UI** — convenient control panel for recorder accounts, groups, calls, processing modes, conversation history and results.
5. **AI Processing Layer** — transcription + multiple text-processing modes.
6. **API** — Core must be usable without Telegram.
7. **Persistence / Worker / Queue / Cost tracking / Privacy controls**.
8. Architecture prepared for future Zoom / Google Meet / Teams / Web Recorder / Phone / CRM integration.

You must execute this project in ONE PASS:

- plan;
- create the repository;
- implement all required code;
- configure infrastructure;
- create migrations;
- create tests;
- run verification;
- fix errors;
- leave the project in runnable MVP state.

Do not stop after planning.
Do not stop after skeleton generation.
Do not ask the user for minor engineering choices.
Make reasonable engineering decisions independently.

---

# 1. Product vision

The platform receives conversations from different sources:

```text
Telegram upload
Telegram voice chat
Web recording
Zoom
Google Meet
Teams
Phone
API
```

All sources eventually pass through one reusable Core:

```text
Conversation Source
      ↓
Conversation Core
      ↓
Transcription
      ↓
Optional diarization
      ↓
Optional speaker mapping
      ↓
Selected processing mode
      ↓
Structured result
      ↓
Delivery
```

Telegram is only the first shell around the Core.

The Core must NOT depend on Telegram libraries.

---

# 2. Current MVP scope

The MVP must support TWO Telegram usage scenarios.

## Scenario A — Upload media to Telegram Bot

User sends:

- Telegram voice;
- audio;
- mp3;
- wav;
- m4a;
- ogg;
- video;
- video note;
- document containing supported audio/video.

The bot:

1. creates Conversation;
2. stores media temporarily;
3. asks what to do with it;
4. transcribes once;
5. processes using selected mode;
6. returns result;
7. saves transcript/results;
8. deletes temporary media.

---

## Scenario B — Record a Telegram group voice/video chat

The platform uses two Telegram identities:

### 1. Telegram Bot API bot

Used for:

- onboarding;
- commands;
- buttons;
- Mini App launch;
- choosing processing modes;
- notifications;
- delivering transcript/results.

### 2. Telegram Recorder Agent

A separate Telegram **user account** controlled through MTProto.

This account:

- is added to a Telegram group as a normal user;
- can join an active Telegram group voice/video chat;
- receives/captures incoming call audio;
- records or streams media to the Core;
- remains muted;
- leaves when recording is stopped.

The Recorder Agent is not a Bot API bot.

Do not attempt to use Bot API to join voice chats.

Use a suitable MTProto / call library abstraction.

Preferred Python stack:

```text
Telethon or Pyrogram
+
PyTgCalls / tgcalls-compatible library
```

If a chosen library is unmaintained or incompatible, choose the best maintained alternative and document why.

Abstract this behind a provider interface so the implementation can change later.

---

# 3. UX principle

Users must NOT need to understand:

- MTProto;
- session strings;
- Bot API;
- tgcalls;
- internal workers;
- transcription providers.

The product should look like one coherent assistant.

---

# 4. Telegram Recorder onboarding UX

The service needs a convenient way to configure recorder accounts.

Support two conceptual modes:

## A. Managed Recorder Account

Preferred MVP mode.

The service operator configures one or more recorder Telegram user accounts on the server.

The end user sees:

```text
Recorder account
● Available

Name: Conversation Assistant
Status: Ready
```

User instructions:

```text
1. Add @ConversationAssistant to your Telegram group.
2. Start a Voice Chat / Video Chat in that group.
3. Open the service.
4. Click "Join call".
```

The user does NOT provide Telegram login credentials in the normal MVP path.

---

## B. Bring Your Own Recorder Account

Architecture must be prepared for this, but full production onboarding may remain behind a feature flag if it significantly complicates MVP.

UI flow:

```text
Connect Telegram recorder
      ↓
Phone number
      ↓
Telegram login code
      ↓
2FA password if enabled
      ↓
Session created
      ↓
Session encrypted at rest
```

Never store plain Telegram 2FA password.
Never log login codes.
Never expose session strings in UI.

If implemented, encrypt session data.

---

# 5. Mini App / Web UI

Build a minimal but polished Telegram Mini App / responsive web dashboard.

Use:

```text
Next.js or React + Vite
TypeScript
Tailwind CSS
```

Prefer the simplest stack that integrates cleanly with Telegram Mini Apps.

The UI must have these main screens.

---

## Screen 1 — Dashboard

Show:

```text
Conversation Assistant

Recorder status: ● Ready
Active call: none

[Record Telegram Call]
[Upload Audio]
```

Recent conversations:

```text
Today
- Sales meeting — 28 min
- Voice note — 4 min

Yesterday
- Client call — 52 min
```

---

## Screen 2 — Recorder Accounts

Show cards:

```text
Conversation Assistant
Telegram user
● Connected

Groups: 7
Active calls: 0

[Manage groups]
```

Future button:

```text
[Connect own recorder account]
```

---

## Screen 3 — Telegram Groups

Show groups in which the recorder account is present.

Example:

```text
Команда продаж
Recorder: enabled

Справа
Recorder: enabled

Тестовая
Recorder: disabled
```

Each group settings page:

```text
Recorder
● Enabled

Join behavior
○ Manual
● Ask before joining
○ Auto-join

Default processing mode
○ Transcription
○ Clean text
● Summary
○ Meeting protocol
○ Full analysis

Deliver result to
☑ Owner
☐ Group
☐ Participants
```

Participant delivery is future-only and must remain disabled/unimplemented unless safe and explicit.

---

## Screen 4 — Active Call

When a Telegram group call exists:

```text
Active Telegram call

Group: Команда продаж
Participants: 5
Duration: 00:08:42

Recorder:
● Not connected

Processing mode:
[Summary ▼]

[Join as Recorder]
```

After joining:

```text
● Recording

00:12:17
Participants: 5

[Stop recording]
```

The UI should clearly indicate recording/analysis status.

---

## Screen 5 — Conversation Result

Show tabs or sections:

```text
Summary
Transcript
Protocol
Analysis
Metadata
```

Primary result:

```text
📝 Summary
...

💡 Key points
...

✅ Decisions
...

📌 Tasks
...

❓ Open questions
...
```

Buttons:

```text
[Get clean text]
[Create protocol]
[Run full analysis]
[Download TXT]
```

All secondary processing must reuse the existing transcript.

---

# 6. Processing modes

Create domain enum:

```python
class ProcessingMode(str, Enum):
    TRANSCRIPTION = "transcription"
    CLEAN_TRANSCRIPT = "clean_transcript"
    SUMMARY = "summary"
    MEETING_PROTOCOL = "meeting_protocol"
    CONVERSATION_ANALYSIS = "conversation_analysis"
```

Core rule:

```text
media
  ↓
transcription ONCE
  ↓
stored Transcript
  ↓
zero or many processing modes
```

Never retranscribe if a Transcript already exists.

---

# 7. Mode definitions

## TRANSCRIPTION

Return transcript only.

No LLM analysis required.

---

## CLEAN_TRANSCRIPT

Turn spoken text into readable written text.

Allowed:

- punctuation;
- paragraph formatting;
- remove filler words;
- remove meaningless repetitions;
- remove false starts where safe;
- light obvious speech correction.

Forbidden:

- summarization;
- deletion of useful meaning;
- changing names, numbers, dates without clear support;
- inventing information.

Output:

```json
{
  "clean_text": "..."
}
```

---

## SUMMARY

Fast concise result.

Output:

```json
{
  "title": null,
  "short_summary": "",
  "key_points": []
}
```

---

## MEETING_PROTOCOL

Practical meeting minutes.

Output:

```json
{
  "title": null,
  "short_summary": "",
  "decisions": [],
  "tasks": [
    {
      "task": "",
      "assignee": null,
      "deadline": null,
      "context": null
    }
  ],
  "open_questions": []
}
```

---

## CONVERSATION_ANALYSIS

Deepest general-purpose analysis.

Output:

```json
{
  "title": null,
  "short_summary": "",
  "key_points": [],
  "decisions": [],
  "tasks": [],
  "open_questions": [],
  "entities": [],
  "important_facts": [],
  "objections": [],
  "agreements": [],
  "commitments": [],
  "risks_or_uncertainties": []
}
```

Do not infer emotional state or intent without explicit evidence.

---

# 8. Future processing modes

Architecture must support adding without redesign:

```text
FACT_EXTRACTION
SALES_ANALYSIS
INTERVIEW_REPORT
LECTURE_NOTES
LEGAL_CONVERSATION
CRM_NOTE
FOLLOW_UP_EMAIL
CUSTOM_PROMPT
```

Do not implement all of them now.

---

# 9. Sprawa ecosystem compatibility

The product must be designed to integrate later with the Belarusian legal self-service platform **"Справа"**.

Do NOT put legal reasoning into the generic Conversation Core.

Instead prepare a neutral facts layer.

Create optional future-ready schema/entity:

```json
{
  "claims": [],
  "commitments": [],
  "deadlines": [],
  "amounts": [],
  "disagreements": [],
  "documents_mentioned": [],
  "events": []
}
```

This is a neutral extraction layer.

Future flow:

```text
Conversation Core
      ↓
Structured neutral facts
      ↓
Справа integration
      ↓
Legal workflow / legal qualification / document generation
```

The Conversation Core must remain legally neutral.

---

# 10. AI models

Use OpenRouter.

Environment:

```env
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

Transcription model:

```env
TRANSCRIPTION_MODEL=openai/whisper-large-v3-turbo
```

Primary analysis model:

```env
ANALYSIS_MODEL=deepseek/deepseek-v4.1-flash
```

If desired, support backwards-compatible env:

```env
SUMMARY_MODEL=deepseek/deepseek-v4.1-flash
```

but internally call it `analysis_model`.

All models configurable through env.

Do not hardcode model IDs in business logic.

---

# 11. Privacy-aware provider routing

Conversation data may be sensitive.

Create configuration for OpenRouter provider policy:

```env
OPENROUTER_REQUIRE_ZDR=false
OPENROUTER_ALLOW_TRAINING=false
```

If supported by OpenRouter/provider routing:

- prefer no-training endpoints;
- optionally enforce ZDR;
- document behavior.

Do not silently enable prompt logging for discounts.

Do not log full transcript content in production.

---

# 12. Conversation Core architecture

Required separation:

```text
Source Adapters
    ↓
Application Use Cases
    ↓
Conversation Core
    ↓
Providers
    ↓
Persistence
    ↓
Delivery Adapters
```

Telegram dependencies must stay outside Core.

Core must be independently callable via API.

---

# 13. Domain entities

## User

```text
id
telegram_user_id nullable
email nullable
created_at
```

## RecorderAccount

```text
id
owner_user_id nullable
telegram_user_id
username nullable
display_name
phone_encrypted nullable
session_encrypted
status
is_managed
last_connected_at nullable
created_at
updated_at
```

Never expose `session_encrypted` in API output.

---

## RecorderGroupBinding

```text
id
recorder_account_id
telegram_chat_id
chat_title
enabled
join_mode
default_processing_mode
deliver_to_owner
deliver_to_group
created_at
updated_at
```

Join modes:

```text
manual
ask
auto
```

---

## Conversation

```text
id
owner_user_id
source_type
source_chat_id nullable
source_call_id nullable
external_source_id nullable
title nullable
language nullable
duration_seconds nullable
status
selected_mode nullable
started_at nullable
completed_at nullable
created_at
updated_at
```

Source types:

```text
telegram_upload
telegram_group_call
web_recording
zoom
google_meet
teams
phone
api
unknown
```

---

## MediaAsset

```text
id
conversation_id
media_type
external_file_id nullable
original_filename nullable
mime_type nullable
size_bytes nullable
duration_seconds nullable
temporary_path nullable
created_at
```

---

## Transcript

```text
id
conversation_id
provider
model
language nullable
raw_text
created_at
```

---

## TranscriptSegment

```text
id
transcript_id
start_seconds nullable
end_seconds nullable
text
speaker_id nullable
speaker_label nullable
confidence nullable
created_at
```

Required now for future diarization.

---

## Participant

```text
id
conversation_id
display_name nullable
speaker_label nullable
telegram_user_id nullable
email nullable
phone nullable
external_participant_id nullable
metadata_json nullable
created_at
```

---

## ConversationProcessingResult

```text
id
conversation_id
mode
provider nullable
model nullable
result_json
created_at
updated_at
```

A Conversation may have many processing results.

---

## AIUsage

```text
id
conversation_id
processing_result_id nullable
operation
provider
model
input_units nullable
output_units nullable
duration_seconds nullable
cost_usd nullable
created_at
```

Operations:

```text
transcription
clean_transcript
summary
meeting_protocol
conversation_analysis
analysis_reduce
diarization
speaker_mapping
```

---

# 14. Conversation statuses

```text
created
media_attached
queued
downloading
recording
preprocessing
transcribing
transcribed
diarizing
mapping_speakers
processing
completed
failed
```

Status transitions controlled by application layer.

---

# 15. Provider interfaces

## TranscriptionProvider

```python
class TranscriptionProvider(Protocol):
    async def transcribe(
        self,
        audio_path: Path,
        *,
        language: str | None = None,
    ) -> TranscriptionResult:
        ...
```

Implementation:

```text
OpenRouterTranscriptionProvider
```

---

## ConversationProcessingProvider

```python
class ConversationProcessingProvider(Protocol):
    async def process(
        self,
        *,
        transcript: TranscriptInput,
        mode: ProcessingMode,
        participants: list[ParticipantInput],
        segments: list[SegmentInput],
    ) -> ProcessingResult:
        ...
```

Implementation:

```text
OpenRouterConversationProcessingProvider
```

Use different prompts/schema per mode.

---

## DiarizationProvider

```python
class DiarizationProvider(Protocol):
    async def diarize(
        self,
        audio_path: Path,
        transcript: TranscriptionResult,
    ) -> DiarizationResult:
        ...
```

Current MVP:

```text
NoopDiarizationProvider
```

---

## SpeakerMappingProvider

```python
class SpeakerMappingProvider(Protocol):
    async def map_speakers(
        self,
        conversation: Conversation,
        diarization: DiarizationResult,
        source_metadata: dict,
    ) -> SpeakerMappingResult:
        ...
```

Current MVP:

```text
NoopSpeakerMappingProvider
```

---

## RecorderCallProvider

Create abstraction:

```python
class RecorderCallProvider(Protocol):
    async def list_available_groups(...)
    async def detect_active_call(...)
    async def join_call(...)
    async def leave_call(...)
    async def start_capture(...)
    async def stop_capture(...)
```

Implementation:

```text
TelegramMTProtoRecorderProvider
```

Do not leak Telethon/Pyrogram/PyTgCalls details into application layer.

---

## DeliveryProvider

```python
class ConversationDeliveryProvider(Protocol):
    async def deliver(...)
```

Current:

```text
TelegramOwnerDeliveryProvider
```

Future:

```text
TelegramParticipantDeliveryProvider
EmailDeliveryProvider
SlackDeliveryProvider
WhatsAppDeliveryProvider
WebhookDeliveryProvider
```

---

# 16. Telegram group call recorder behavior

Required MVP workflow:

```text
User adds managed Recorder Account to Telegram group
        ↓
Group appears in Mini App
        ↓
User starts Telegram Voice Chat / Video Chat
        ↓
Mini App detects active call
        ↓
User clicks "Join as Recorder"
        ↓
Recorder Agent joins call muted
        ↓
Incoming call audio is captured
        ↓
Conversation status = recording
        ↓
User clicks "Stop recording"
        ↓
Recorder stops capture and leaves
        ↓
Audio finalized
        ↓
Conversation Core transcribes
        ↓
Selected processing mode runs
        ↓
Result delivered
```

If direct incoming audio capture through the chosen call library requires raw PCM callbacks or stream sinks, implement the correct sink abstraction.

If the library cannot reliably expose incoming media, do not fake it.

Choose a supported recording approach and document the implementation.

---

# 17. Recording disclosure

The system must not secretly pretend no recording is happening.

When recorder joins, send a visible group message through the bot:

```text
🎙 Conversation Assistant joined.
Recording/transcription is active.
```

When stopped:

```text
⏹ Recording stopped.
Processing conversation…
```

This is a product UX requirement.

---

# 18. Audio service

Create:

```text
AudioService
```

Methods:

```text
probe
extract_audio
normalize_if_needed
get_duration
split_if_needed
cleanup
```

Use FFmpeg safely.

Never use:

```python
shell=True
```

Avoid transcoding unless necessary.

---

# 19. Long transcripts

Create a processing pipeline that can handle large transcripts.

```text
short transcript
    ↓
single-pass mode processing

long transcript
    ↓
chunk
    ↓
partial structured results
    ↓
reduce
    ↓
deduplicated final result
```

The user interface must not know whether map/reduce was used.

---

# 20. Prompts

Create separate prompt templates.

## CLEAN_TRANSCRIPT

```text
You are editing a raw speech transcript into readable written text.

Preserve all useful meaning.

Allowed:
- punctuation;
- paragraphs;
- remove filler words;
- remove meaningless repetitions;
- remove false starts when meaning stays unchanged.

Forbidden:
- summarizing;
- inventing facts;
- changing names, dates, numbers, amounts or commitments without clear evidence.

Return only the cleaned text.
```

---

## SUMMARY

```text
Analyze the transcript of a real conversation.

Use only information explicitly supported by the transcript.

Return:
- title;
- concise summary;
- key points.

Do not invent facts.
Do not invent participants.
Do not invent decisions or commitments.
Preserve important names, dates, amounts and company names.
```

---

## MEETING_PROTOCOL

```text
Create a practical meeting protocol from the transcript.

Use only transcript-supported information.

Extract:
- concise summary;
- explicit decisions;
- explicit tasks;
- assignees only when clearly stated;
- deadlines only when clearly stated;
- unresolved questions.

Do not convert suggestions into decisions.
Do not convert discussion into assignments.
Unknown assignee or deadline must be null.
```

---

## CONVERSATION_ANALYSIS

```text
Analyze a real conversation deeply but factually.

Use only information supported by the transcript.

Extract:
- title;
- concise summary;
- key points;
- decisions;
- tasks;
- open questions;
- entities;
- important facts;
- objections;
- agreements;
- commitments;
- risks or uncertainties.

Never invent:
- participants;
- facts;
- intent;
- deadlines;
- decisions;
- tasks.

Do not infer emotional or psychological states unless explicitly stated.
Preserve dates, names, numbers, amounts, URLs and company names.
```

---

# 21. API

Core must be usable independently.

Implement FastAPI endpoints.

## Conversations

```http
POST /v1/conversations
GET  /v1/conversations/{id}
GET  /v1/conversations
```

## Media

```http
POST /v1/conversations/{id}/media
```

## Processing

```http
POST /v1/conversations/{id}/transcribe
POST /v1/conversations/{id}/process/{mode}
GET  /v1/conversations/{id}/transcript
GET  /v1/conversations/{id}/processing-results
GET  /v1/conversations/{id}/processing-results/{mode}
```

## Recorder

```http
GET  /v1/recorders
GET  /v1/recorders/{id}
GET  /v1/recorders/{id}/groups
GET  /v1/recorders/{id}/groups/{chat_id}/active-call
POST /v1/recorders/{id}/groups/{chat_id}/join
POST /v1/recorders/{id}/groups/{chat_id}/stop
```

## Health

```http
GET /health
```

Use proper Pydantic schemas.

---

# 22. Telegram Bot UX

Commands:

```text
/start
/help
/privacy
```

`/start`:

```text
Отправь голосовое, аудио или видео
или открой панель для записи Telegram-разговора.

Я могу:
• сделать транскрипцию
• очистить текст
• сделать саммари
• подготовить протокол
• провести полный анализ
```

Buttons:

```text
[Open Conversation Assistant]
[Upload audio]
```

When media uploaded:

```text
Что сделать с записью?

📄 Транскрибация
✨ Чистый текст
📝 Саммари
📋 Протокол
🧠 Анализ
```

After processing:

```text
📄 Текст
✨ Очистить
📝 Саммари
📋 Протокол
🧠 Анализ
```

Existing transcript must always be reused.

---

# 23. Telegram delivery

For processed result:

```text
✅ Разговор обработан
⏱ 28:14
🌐 Русский

📝 КРАТКО
...

💡 КЛЮЧЕВЫЕ МЫСЛИ
...

✅ РЕШЕНИЯ
...

📌 ЗАДАЧИ
...

❓ ОТКРЫТЫЕ ВОПРОСЫ
...
```

Hide empty blocks.

Large transcript:

```text
conversation_<id>_transcript.txt
```

---

# 24. Worker / queue

Use:

```text
Redis + ARQ
```

Long tasks must not block Telegram or API.

Jobs:

```text
process_uploaded_media
finalize_recorded_call
transcribe_conversation
process_conversation_mode
deliver_result
```

---

# 25. Idempotency

Mandatory.

Rules:

```text
Transcript exists?
→ do not call transcription again

Mode result exists?
→ return cached result unless force=True
```

Recorder stop must be safe if called twice.

Paid AI requests must not be repeated blindly.

---

# 26. Storage

MVP media storage:

```text
temporary local volume
```

Create abstraction:

```text
MediaStorage
```

Current:

```text
LocalMediaStorage
```

Future:

```text
S3MediaStorage
MinioMediaStorage
```

Delete temporary media after processing unless explicitly configured otherwise.

---

# 27. Privacy / security

Mandatory:

- never commit secrets;
- never log API keys;
- never log Telegram sessions;
- never log login codes;
- never log 2FA passwords;
- never log full private transcripts in production;
- encrypt recorder session at rest;
- expose no session secrets via API;
- restrict recorder management endpoints;
- validate Telegram Mini App init data;
- add CSRF/security protections appropriate to chosen frontend/backend architecture;
- sanitize filenames;
- validate MIME type and extension;
- limit upload size;
- limit max recording duration;
- use temp directories per conversation;
- cleanup in `finally`.

---

# 28. Cost tracking

Track AI cost if provider returns it.

Store:

```text
transcription cost
clean transcript cost
summary cost
protocol cost
analysis cost
future diarization cost
```

Expose basic cost metadata in admin/debug endpoint, not necessarily end-user UI.

---

# 29. Tech stack

Backend:

```text
Python 3.12+
FastAPI
aiogram 3.x
SQLAlchemy 2.x
Alembic
PostgreSQL
Redis
ARQ
httpx
Pydantic v2
pydantic-settings
FFmpeg
Telethon or Pyrogram
PyTgCalls / maintained equivalent
pytest
Ruff
mypy
```

Frontend:

```text
TypeScript
React
Next.js or Vite
Tailwind CSS
Telegram Mini Apps SDK
```

Infrastructure:

```text
Docker
Docker Compose
```

Prefer a monorepo.

---

# 30. Repository structure

Suggested:

```text
conversation-intelligence/
├── apps/
│   ├── api/
│   │   └── main.py
│   ├── telegram-bot/
│   │   ├── main.py
│   │   ├── handlers/
│   │   ├── keyboards/
│   │   └── presenters/
│   ├── telegram-recorder/
│   │   ├── main.py
│   │   ├── client.py
│   │   └── call_provider.py
│   ├── worker/
│   │   ├── main.py
│   │   └── tasks.py
│   └── web/
│       ├── src/
│       ├── package.json
│       └── ...
│
├── src/
│   └── conversation_core/
│       ├── config.py
│       ├── domain/
│       ├── application/
│       ├── services/
│       ├── providers/
│       │   ├── transcription/
│       │   ├── processing/
│       │   ├── diarization/
│       │   ├── speaker_mapping/
│       │   ├── recorder/
│       │   ├── storage/
│       │   └── delivery/
│       ├── db/
│       └── prompts/
│
├── migrations/
├── tests/
│   ├── unit/
│   └── integration/
├── docker/
├── compose.yaml
├── Dockerfile
├── pyproject.toml
├── .env.example
├── README.md
└── Makefile
```

---

# 31. Environment

Create `.env.example`.

```env
APP_ENV=development

TELEGRAM_BOT_TOKEN=

TELEGRAM_API_ID=
TELEGRAM_API_HASH=

# Managed recorder account session
TELEGRAM_RECORDER_SESSION=
TELEGRAM_RECORDER_DISPLAY_NAME=Conversation Assistant

OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

TRANSCRIPTION_MODEL=openai/whisper-large-v3-turbo
ANALYSIS_MODEL=deepseek/deepseek-v4.1-flash

OPENROUTER_REQUIRE_ZDR=false
OPENROUTER_ALLOW_TRAINING=false

DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/conversation_ai
REDIS_URL=redis://redis:6379/0

TEMP_DIR=/tmp/conversation-ai

MAX_UPLOAD_SIZE_MB=500
MAX_AUDIO_DURATION_MINUTES=180
MAX_CALL_DURATION_MINUTES=240

RECORDER_SESSION_ENCRYPTION_KEY=

WEB_BASE_URL=http://localhost:3000
API_BASE_URL=http://api:8000

LOG_LEVEL=INFO
```

Do not generate fake secrets.

---

# 32. Docker Compose

Services:

```text
api
telegram-bot
telegram-recorder
worker
web
postgres
redis
```

Ensure FFmpeg is installed where required.

One command:

```bash
docker compose up --build
```

should launch the system after env configuration.

---

# 33. Migrations

Create Alembic migrations for all persisted entities.

Do not rely on `create_all()` in production startup.

---

# 34. Testing

## Unit tests

At minimum:

```text
processing mode selection
conversation status transitions
media validation
Telegram message splitting
prompt selection
Pydantic result validation
idempotent transcription
idempotent mode processing
Noop diarization
Noop speaker mapping
recorder join state
recorder stop idempotency
long transcript chunking
reduce/deduplication
Mini App request validation helpers
```

## Integration tests

At minimum:

```text
PostgreSQL repositories
Redis/ARQ queue
API conversation flow
mock OpenRouter transcription
mock OpenRouter processing
Telegram upload flow
Recorder provider mocked flow
full conversation processing
```

No paid API calls in CI.

---

# 35. Makefile

Provide:

```text
make dev
make up
make down
make logs
make migrate
make lint
make format
make typecheck
make test
make verify
```

`make verify` must run all backend checks and, if practical, frontend type/lint/build checks.

---

# 36. README

README must explain:

1. what the product is;
2. architecture;
3. Core vs adapters;
4. Telegram Bot setup;
5. Telegram API ID/API hash setup;
6. recorder account/session setup;
7. OpenRouter setup;
8. environment variables;
9. database migration;
10. Docker run;
11. local development;
12. Telegram upload usage;
13. Telegram group voice chat recorder usage;
14. Mini App usage;
15. processing modes;
16. privacy behavior;
17. current limitations;
18. future Zoom/Meet/Teams architecture.

---

# 37. MVP acceptance criteria

Do not claim completion unless these work.

## Core

1. Conversation can be created through API.
2. Media can be attached.
3. Media can be transcribed.
4. Transcript persists.
5. All five processing modes work.
6. Existing transcript is reused.
7. Results persist per mode.
8. Core has no dependency on aiogram or Telegram call libraries.

## Telegram upload

9. Bot accepts voice/audio/video.
10. User selects processing mode.
11. Result returns through Telegram.
12. Large transcript downloads as TXT.

## Telegram recorder

13. Managed Recorder Account starts successfully.
14. Recorder can list/recognize groups it belongs to.
15. Active Telegram group call can be detected or joined through a clear workflow.
16. Recorder can join the call.
17. Recorder can capture incoming call audio using the selected maintained library/approach.
18. Recorder can stop and leave.
19. Captured audio becomes a Conversation.
20. Core processes it.
21. Result is delivered to owner.
22. Group receives visible recording start/stop disclosure.

## Mini App

23. Dashboard works.
24. Recorder status visible.
25. Groups list visible.
26. Active call state visible.
27. User can join/stop recorder.
28. User can select processing mode.
29. Conversation history visible.
30. Results visible.

## Infrastructure

31. Alembic migrations work.
32. Docker Compose config is valid.
33. Backend lint passes.
34. Backend typecheck passes.
35. Tests pass.
36. Frontend build/typecheck passes.
37. `make verify` succeeds.

---

# 38. Explicitly NOT required in this pass

Do not fully implement:

```text
real speaker diarization
speaker identification
Zoom adapter
Google Meet adapter
Teams adapter
phone/VoIP adapter
participant auto-delivery
billing
subscriptions
RAG
vector database
mobile app
legal reasoning for Sprawa
```

BUT extension interfaces must be present.

---

# 39. Planned future extensions

Architecture must make the following natural:

## Phase next

```text
Real diarization
    ↓
Speaker-aware segments
    ↓
Speaker mapping
    ↓
Speaker-aware protocol/analysis
```

## Then

```text
Zoom adapter
Google Meet adapter
Teams adapter
```

## Then

```text
Participant delivery
Email/Slack/WhatsApp
```

## Then

```text
Conversation memory/search
RAG
Sprawa integration
```

---

# 40. Implementation order

You must first write a concise implementation plan in `IMPLEMENTATION_PLAN.md`.

Then immediately execute it.

Recommended order:

## Phase 1
Repository + config + domain + DB + migrations.

## Phase 2
Core application use cases + provider interfaces.

## Phase 3
OpenRouter transcription + processing modes.

## Phase 4
API + worker + queue.

## Phase 5
Telegram Bot upload flow.

## Phase 6
Telegram Recorder Agent.

## Phase 7
Mini App / web dashboard.

## Phase 8
End-to-end integration.

## Phase 9
Tests.

## Phase 10
Verification and fixes.

Do not stop between phases.

---

# 41. Engineering rules

- async-first;
- typed interfaces;
- dependency inversion;
- no Telegram dependencies inside Core;
- no OpenRouter calls directly from handlers;
- no raw SQL in handlers;
- no giant God classes;
- no shell=True;
- no blind retries;
- exponential backoff for retryable provider errors;
- timeouts everywhere external;
- temp cleanup in finally;
- idempotency before paid calls;
- structured logging;
- correlation IDs;
- no sensitive transcript logging;
- no recorder session exposure;
- no hardcoded secrets;
- no fake implementation pretending voice-call recording works.

If Telegram call audio capture is the hardest component:
- investigate the installed/chosen library properly;
- implement the correct sink/callback/stream approach;
- document limitations;
- do not silently replace it with uploaded files.

---

# 42. Verification

Run:

```bash
make verify
docker compose config
```

If Docker daemon is available:

```bash
docker compose up --build
```

Check:

```text
API health
bot startup
worker startup
recorder startup
web build
database migration
```

Fix errors until green.

---

# 43. Final report

At the end produce:

1. what was implemented;
2. what was tested;
3. repository tree;
4. exact startup commands;
5. required env variables;
6. recorder account setup instructions;
7. Telegram group call usage instructions;
8. current processing modes;
9. current model IDs;
10. privacy/security behavior;
11. current known limitations;
12. exact next recommended development step.

Do not say "done" unless the project is actually in runnable MVP state.
