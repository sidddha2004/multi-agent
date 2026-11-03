# SecureAI Lite API (serverless)

Free-tier deployment of the SecureAI gateway for Vercel: FastAPI + Neon Postgres + Gemini 2.5 Flash.
The full Kafka/Redis/Qdrant architecture in the repo root is unchanged; this is a single-function
version with the same REST contract (`/auth/*`, `/api/jobs`) so the React frontend works against either.

Flow: `POST /api/jobs` -> planner call (Gemini) splits the prompt into 1-3 subtasks -> each subtask is run by a
research/analysis/writing agent call -> results stored in Postgres (`users`, `jobs`, `tasks`).
Rate limiting is kept in Postgres (`rate_limits`), so no Redis is needed.

Env vars: `DATABASE_URL` (Neon), `JWT_SECRET` (32+ chars), `GEMINI_API_KEY`, `CORS_ORIGINS` (comma list),
optional `LLM_MODEL`, `JOBS_PER_MINUTE`.
