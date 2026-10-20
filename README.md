# Conversation Intelligence Platform

Runnable MVP monorepo for a Telegram-first conversation assistant. `src/conversation_core` contains the reusable, Telegram-independent domain, media validation, prompt selection and OpenRouter processing adapter. Telegram, API, worker, recorder and web UI live under `apps/`.

## Run

```bash
cp .env.example .env
make install
make verify
make dev
```

Or start infrastructure and services with `docker compose up --build` after setting `.env`. API health is `GET http://localhost:8000/health`; web dashboard is `http://localhost:3000`.

## GitHub + Vercel workflow

The web UI is a Vite app in `apps/web` and is ready for Vercel:

1. Push the repository to GitHub.
2. Import it in Vercel.
3. Set **Root Directory** to `apps/web`.
4. Keep the default build command `npm run build` and output directory `dist`.
5. Add `VITE_API_BASE_URL` for the deployed API URL when the API is available.

The Settings screen provides a guided setup for OpenRouter, Telegram Bot API, Telegram recorder credentials, privacy defaults, and the recommended deployment split. Secrets entered there are stored only in the current browser as a convenience for local setup; production secrets must be stored as server-side Vercel Environment Variables or in the backend host, never in GitHub or client-side code.

Required for paid AI calls: `OPENROUTER_API_KEY`. Configure `TRANSCRIPTION_MODEL` and `ANALYSIS_MODEL` without changing business code. Database, Redis, Telegram bot token/API ID/API hash, recorder session, limits, and privacy flags are documented in `.env.example`.

## Processing and privacy

The five modes are transcription, clean transcript, summary, meeting protocol and conversation analysis. A transcript is stored once and processing results are cached per mode. The provider does not log transcript content. Temporary media uses a per-conversation directory and is designed to be removed in the worker `finally` path. No secrets or Telegram sessions are returned by API schemas. `OPENROUTER_REQUIRE_ZDR` and `OPENROUTER_ALLOW_TRAINING` are retained as policy configuration for the production provider routing implementation.

## Telegram

The bot adapter accepts the configured token and is the place for upload handlers, mode keyboards, transcript splitting and result delivery. A managed recorder account must be provisioned separately with MTProto credentials/session; the recorder adapter intentionally raises a clear error until a maintained Telegram call-media backend (for example a compatible Telethon/PyTgCalls setup) is installed and wired. It never pretends that a joined call produced audio. Visible start/stop disclosure messages must be emitted by that adapter.

## Limitations and next step

The Core now includes its application service layer, guarded status transitions, idempotent transcript/result persistence, segment/participant/usage models, ARQ task entry points, retry helper, and migration bootstrap. Telegram media handlers, Mini App auth, and real MTProto capture remain adapter work. The next recommended step is to select and validate one maintained MTProto call-media backend on the target deployment, then connect its PCM sink to `finalize_recorded_call`.
