# Studio/back-end route map

Dit project heeft twee API-processen en één frontend.

## `minimal_api.py` (standaard poort 8069)
- Persona/chat basics: `/api/personas`, `/api/switch`, `/api/chat/nsfw`, `/api/history/{session_id}`, `/api/clear/{session_id}`
- LiveKit status/control (config-only in minimal mode):
  - `GET /api/avatar/lemonslice/health`
  - `POST /api/avatar/lemonslice/session`
  - `POST /api/avatar/lemonslice/session/{session_id}/control`
- Studio routes:
  - `GET /api/studio/capabilities`
  - `POST /api/studio/jobs`
  - `GET /api/studio/jobs`
  - `GET /api/studio/jobs/{job_id}`
  - `POST /api/studio/jobs/{job_id}/cancel`
  - `GET /api/studio/gallery`

## `src/nova_candy_app.py` (volledige chat + Studio)
- Chat (normaal): `/api/chat/normal`
- Chat (persona): `/api/chat/nsfw`
- LiveKit endpoints:
  - `GET /api/avatar/lemonslice/health`
  - `POST /api/avatar/lemonslice/session`
  - `POST /api/avatar/lemonslice/session/{session_id}/control`
- Studio endpoints (zelfde contract als minimal API):
  - `GET /api/studio/capabilities`
  - `POST /api/studio/jobs`
  - `GET /api/studio/jobs`
  - `GET /api/studio/jobs/{job_id}`
  - `POST /api/studio/jobs/{job_id}/cancel`
  - `GET /api/studio/gallery`

## `candy_nsfw_plus_api.py` (standaard poort 9500)
- Media-generatie backend voor scene-jobs:
  - `GET /health`
  - `GET /scenes`
  - `GET /session`
  - `POST /generate`
  - `POST /batch`
  - `GET /avatar/{avatar_id}`
  - `POST /roleplay`

## Compose varianten
- `docker-compose.minimal.yml`: frontend + minimal API (en exposed poort 9500/8069 in dezelfde service image).
- `docker-compose.nsfw-plus.yml`: aparte NSFW+ service (`/generate` enz.) op host poort 9500 + optionele Redis.
