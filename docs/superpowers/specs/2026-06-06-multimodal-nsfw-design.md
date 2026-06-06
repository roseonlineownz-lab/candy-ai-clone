---
title: Multimodal NSFW Experience Integration (SuperGrok Multi-Modal Engine)
date: 2026-06-06
status: Approved
---

# Multimodal NSFW Experience Integration Spec

This specification defines the implementation and integration of the **SuperGrok Multi-Modal Engine** (Phase 1) within the Candy AI Clone repository.

---

## 1. Architecture

We created a shared, independent orchestrator module [src/multimodal_engine.py](file:///home/faramix/candy-ai-clone/src/multimodal_engine.py). This module acts as the centralized coordinator for generating the text narrative, neural voice audio, and visual outputs:

```
                      +-------------------+
                      |   Client browser  |
                      +---------+---------+
                                |
                                | (Chat / Media Request)
                                v
                      +-------------------+
                      |   Chat App (8069) |
                      +---------+---------+
                                |
                                | (Triggers Multimodal)
                                v
               +---------------------------------+
               |   SuperGrokMultiModalEngine     |
               +----+-----------+-----------+----+
                    |           |           |
                    | (Text)    | (Voice)   | (Visuals POST)
                    v           v           v
             +----------+   +----------+  +-------------+
             |Model     |   |Edge TTS  |  |NSFW API     |
             |Router    |   |Engine    |  |(Port 9500)  |
             +----------+   +----------+  +-------------+
```

### Components
1. **`SuperGrokMultiModalEngine`**: The core controller orchestrating text, audio, and visual generations.
2. **`Model Router` (`route_chat`)**: Generates uncensored text responses simulating character dialogues.
3. **`Edge TTS`**: Converts the generated text response into high-fidelity neural audio formats (speech voice).
4. **`NSFW API /generate`**: Port 9500 endpoint executing the Playwright-based `nova_supergrok_auto.py` or Venice AI-based `grok-imagine.py` in the background.

---

## 2. Implementation details

### Backend (`src/multimodal_engine.py`)
- Defines `SuperGrokMultiModalEngine` exposing `async def create_full_experience(self, request: dict) -> dict`.
- Generates the immersive dialogue narrative by constructing a detailed scene prompt tailored to the active companion's persona name, traits, and scenario.
- Generates corresponding audio files asynchronously via `edge_tts` and returns them as a base64 encoded string.
- Fires a POST request to the local `/generate` endpoint on port 9500 to render the image or video on the GPU, returning the static url `/output/{images|videos}/{filename}` to the client immediately.

### Chat Integration (`src/nova_candy_app.py`)
- Monitors incoming NSFW chat messages for media requests using keywords: `"show me", "picture", "photo", "video", "let me see", "visualize", "send pic", "send photo"`.
- If triggered:
  - Dynamically categorizes the desired NSFW scene from the context keywords (e.g. `spanking`, `kutje`, `bj`, `doggy`, `squirt`, etc.).
  - Executes the multimodal engine asynchronously.
  - Returns a response payload with type `"multimodal"`, containing the text response, base64 audio stream, and visual metadata (URL, visual type, status).

### Frontend UI (`frontend/main.js`)
- Detects the `"multimodal"` response type in chat message returns.
- Appends the text response and plays the audio narration.
- Renders an inline visual placeholder containing an animated loading spinner (e.g., "Generating Image...") directly inside the chat thread.
- Polls the proxied `/output/...` URL on port 9500 until the file is ready, then swaps the spinner with the fully rendered image/video bubble.

---

## 3. Testing Plan
1. **Compilation Check**: Verify syntax of `src/multimodal_engine.py` and `src/nova_candy_app.py` compiles without errors.
2. **Endpoint Smoke Test**: Send a trigger phrase like *"show me a picture of you in bed"* to `/api/chat/nsfw` and verify that the API returns a JSON response containing `type: "multimodal"` and the appropriate media url.
