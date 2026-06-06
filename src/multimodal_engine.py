import os
import sys
import uuid
import asyncio
import logging
import httpx
from pathlib import Path
import edge_tts
from config import VOICE_CACHE_DIR, OUTPUT_DIR, NSFW_API_PORT
from src.personalization_engine import NSFWPersonalizationEngine

# Harden import paths for core modules
if "/home/faramix" not in sys.path:
    sys.path.insert(0, "/home/faramix")
if "/home/faramix/core" not in sys.path:
    sys.path.insert(0, "/home/faramix/core")


# Set up logging
logger = logging.getLogger("multimodal_engine")

class SuperGrokMultiModalEngine:
    """
    Central engine for multi-modal NSFW content generation.
    Coordinates text, audio, and visual generation.
    """
    def __init__(self):
        self.cache_dir = VOICE_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.active_experiences = {}
        self.personalization_engine = NSFWPersonalizationEngine()

    async def create_personalized_experience(self, request: dict) -> dict:
        """
        Creër gepersonaliseerde multi-modale ervaring
        """
        user_id = request.get("user_id", "anonymous")
        persona = request.get("persona", {})
        
        # Get personalized scene config
        scene_config = self.personalization_engine.generate_personalized_scene(user_id, persona)
        
        # Check boundaries on the user message
        boundary_check = self.personalization_engine.check_boundary_violation(
            user_id, request.get("message", "")
        )
        
        if not boundary_check["safe"]:
            logger.warning(f"Boundary violation detected for user {user_id}: {boundary_check['violations']}")
            return {
                "status": "boundary_violation",
                "violations": boundary_check["violations"],
                "message": "Content exceeds established boundaries",
                "text": "Ik voel me hier niet comfortabel bij. Laten we over iets anders praten.",
                "visuals": {"type": "image", "url": "", "status": "failed", "error": "Boundary violation"}
            }
        
        # Merge scene_config with original request
        # scene_config overrides intensity, primary_kinks, emotional_tone, etc.
        personalized_request = {
            **request,
            **scene_config
        }
        
        # Create experience with personalization
        experience = await self.create_full_experience(personalized_request)
        
        # Track interaction for learning
        self.personalization_engine.track_interaction(
            user_id,
            request.get("session_id", "unknown"),
            {
                "persona_id": persona.get("key", "unknown"),
                "message": request.get("message"),
                "response": experience.get("text", ""),
                "media_requested": request.get("media_requested", False),
                "media_type": experience.get("visuals", {}).get("type") if isinstance(experience.get("visuals"), dict) else None,
                "intensity_requested": scene_config.get("intensity")
            }
        )
        
        return experience


    async def create_full_experience(self, request: dict) -> dict:
        experience_id = str(uuid.uuid4())
        
        persona = request.get("persona", {})
        user_message = request.get("message", "")
        context = request.get("context", {})
        intensity = request.get("intensity", "medium")
        visual_type = request.get("visual_type", "image")
        
        self.active_experiences[experience_id] = {
            "status": "generating_text",
            "components": {}
        }
        
        try:
            # 1. Generate Narrative Text
            prompt = self.build_scene_prompt(persona, context, user_message, intensity)
            
            # route_chat is sync, run in threadpool to prevent blocking FastAPI event loop
            from core.model_router import route_chat
            response_text, model_used = await asyncio.to_thread(
                route_chat, prompt, None, True  # voice_uncensored=True
            )
            
            narrative = response_text.strip()
            # Strip out any character prefixing
            if narrative.startswith(f"{persona.get('name', '')}:"):
                narrative = narrative[len(persona.get('name', '')) + 1:].strip()
                
            self.active_experiences[experience_id]["components"]["text"] = narrative
            self.active_experiences[experience_id]["status"] = "generating_audio"
            
            # 2. Generate Audio (Parallel)
            voice = persona.get("voice", "nl-BE-DenaNeural")
            audio_task = asyncio.create_task(self.generate_audio(narrative, voice))
            
            # 3. Generate Visuals (Parallel via NSFW API on port 9500)
            visual_task = asyncio.create_task(
                self.trigger_visual_generation(persona, context, visual_type)
            )
            
            audio_path, visual_res = await asyncio.gather(audio_task, visual_task)
            
            self.active_experiences[experience_id].update({
                "status": "completed",
                "components": {
                    "text": narrative,
                    "audio": audio_path,
                    "visuals": visual_res
                }
            })
            
            # Read audio to base64
            import base64
            audio_base64 = ""
            if audio_path and os.path.exists(audio_path):
                with open(audio_path, "rb") as f:
                    audio_base64 = base64.b64encode(f.read()).decode()
            
            return {
                "experience_id": experience_id,
                "status": "completed",
                "text": narrative,
                "audio_base64": audio_base64,
                "visuals": visual_res
            }
            
        except Exception as e:
            logger.error("Error creating full experience: %s", e)
            self.active_experiences[experience_id]["status"] = "failed"
            self.active_experiences[experience_id]["error"] = str(e)
            return {
                "experience_id": experience_id,
                "status": "failed",
                "error": str(e)
            }
            
    def build_scene_prompt(self, persona: dict, context: dict, user_message: str, intensity: str) -> str:
        persona_name = persona.get("name", "Companion")
        system_prompt = persona.get("system_prompt", "Uncensored companion roleplay.")
        scenario = context.get("scenario", "sensual moment")
        
        prompt = (
            f"{system_prompt}\n\n"
            f"[Scenario: {scenario}, Intensity: {intensity}]\n"
            f"User: {user_message}\n\n"
            f"Write a detailed, immersive NSFW response describing your actions and feelings in 1-2 paragraphs.\n"
            f"{persona_name}:"
        )
        return prompt

    async def generate_audio(self, text: str, voice: str) -> str:
        try:
            filename = f"audio_{uuid.uuid4().hex[:8]}.mp3"
            output_path = self.cache_dir / filename
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(output_path))
            return str(output_path)
        except Exception as e:
            logger.error("Error generating audio: %s", e)
            return ""

    async def trigger_visual_generation(self, persona: dict, context: dict, visual_type: str) -> dict:
        url = f"http://127.0.0.1:{NSFW_API_PORT}/generate"
        
        # Determine scene category based on request content
        scene_id = context.get("scene_id", "strip")
        
        # If we have persona avatar path, pass its local path so the backend can undress them
        image_path = None
        if persona.get("avatar"):
            avatar_filename = persona["avatar"].split("/")[-1]
            image_path = f"/home/faramix/avatar_engine/identities/{avatar_filename}"
            
        payload = {
            "scene_id": scene_id,
            "mode": "video" if visual_type == "video" else "image_undress",
            "parameters": {
                "image_path": image_path
            }
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    filename = data.get("image_file", data.get("video_file", "")).split("/")[-1]
                    output_type = "video" if visual_type == "video" else "image"
                    url_path = f"/output/{'videos' if visual_type == 'video' else 'images'}/{filename}"
                    
                    return {
                        "type": output_type,
                        "filename": filename,
                        "url": url_path,
                        "status": "processing"
                    }
                else:
                    return {"type": "image", "url": "", "status": "failed", "error": f"API error {response.status_code}"}
            except Exception as e:
                logger.error("Failed to trigger visual generation: %s", e)
                return {"type": "image", "url": "", "status": "failed", "error": str(e)}

    def get_experience_status(self, experience_id: str) -> dict:
        return self.active_experiences.get(experience_id, {"status": "not_found"})
