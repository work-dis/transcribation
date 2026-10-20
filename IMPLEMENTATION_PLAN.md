# Implementation plan

1. Build a typed, Telegram-independent conversation domain and persistence layer.
2. Add provider interfaces, OpenRouter adapters, prompt schemas, idempotent processing, and long-transcript chunk/reduce helpers.
3. Expose FastAPI endpoints and background-task entry points.
4. Add Telegram Bot API, recorder, and responsive web adapters with clear production boundaries.
5. Add migrations, Compose, tests, verification commands, and documentation.

The MVP uses SQLAlchemy async repositories, local temporary media storage, OpenRouter-compatible HTTP, and a safe recorder abstraction. The call provider is intentionally explicit about the need for a maintained MTProto media backend rather than pretending to capture audio.
