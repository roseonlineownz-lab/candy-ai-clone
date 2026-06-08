# LemonSlice LiveKit Avatar Layer

This app uses LemonSlice as an optional self-managed avatar video layer.
NovaMaster keeps ownership of chat, persona selection, LiveKit room creation,
and UI state. LemonSlice only joins the LiveKit room as the avatar renderer.

## Required Environment

Keep these values server-side in `.env`, `/home/faramix/.env`,
`/home/faramix/.config/novamaster/livekit.env`, or `/home/faramix/.hermes/livekit.env`.

```env
LEMONSLICE_API_KEY=
LIVEKIT_URL=
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=
```

Set one avatar source globally:

```env
LEMONSLICE_AGENT_ID=
LEMONSLICE_AGENT_IMAGE_URL=
```

Or override per persona key:

```env
LEMONSLICE_AGENT_ID_NOVA=
LEMONSLICE_AGENT_IMAGE_URL_NOVA=
```

Do not expose `LEMONSLICE_API_KEY` or `LIVEKIT_API_SECRET` to the browser.

## Runtime Flow

1. The frontend calls `POST /api/avatar/lemonslice/session`.
2. The backend mints a short-lived LiveKit browser token and a separate
   LemonSlice participant token.
3. The backend calls LemonSlice `POST /api/liveai/sessions` with
   `transport_type=livekit`.
4. The browser joins the room with `livekit-client`.
5. The UI stays in a ringing state until the LiveKit data channel receives
   topic `lemonslice` with message type `bot_ready`.
6. `End` calls `POST /api/avatar/lemonslice/session/{session_id}/control`
   with `event=terminate`.

## Local Checks

```bash
pytest tests/test_lemonslice_livekit.py
cd frontend && npm run build
```
