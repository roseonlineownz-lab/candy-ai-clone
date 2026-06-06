import asyncio
import json
import random
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import logging
import sqlite3
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UniversalMultiModalEngine:
    """
    Universele multi-modale content engine die zowel NSFW als non-NSFW content kan genereren
    met adaptieve personalisatie en content filtering
    """
    
    def __init__(self):
        self.db_path = Path.home() / ".supergrok_cache" / "universal_content.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_database()
        
        # Content modes
        self.content_modes = {
            'nsfw': {
                'enabled': True,
                'intensity_levels': ['soft', 'medium', 'hard', 'extreme'],
                'personas': ['sophia', 'dominatrix', 'submissive', 'nurse', 'teacher', 'maid']
            },
            'safe': {
                'enabled': True,
                'intensity_levels': ['soft', 'medium', 'hard'],
                'personas': ['companion', 'friend', 'mentor', 'guide', 'assistant']
            },
            'professional': {
                'enabled': True,
                'intensity_levels': ['soft', 'medium'],
                'personas': ['assistant', 'advisor', 'expert', 'consultant']
            },
            'creative': {
                'enabled': True,
                'intensity_levels': ['soft', 'medium', 'hard'],
                'personas': ['artist', 'writer', 'designer', 'musician', 'poet']
            }
        }
        
        # API configurations
        self.api_configs = {
            'image_generation': {
                'enabled': True,
                'provider': 'stability',
                'model': 'stable-diffusion-xl',
                'safe_mode': True
            },
            'text_generation': {
                'enabled': True,
                'provider': 'openai',
                'model': 'gpt-4',
                'safe_mode': True
            },
            'voice_synthesis': {
                'enabled': True,
                'provider': 'microsoft',
                'model': 'edge-tts',
                'safe_mode': True
            }
        }
        
        # Content filters
        self.content_filters = {
            'nsfw_filter': {
                'enabled': True,
                'threshold': 0.7
            },
            'safety_filter': {
                'enabled': True,
                'threshold': 0.8
            },
            'quality_filter': {
                'enabled': True,
                'threshold': 0.6
            }
        }
        
        logger.info("Universal Multi-Modal Engine initialized")

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn
    
    def init_database(self):
        """Initialiseer database voor universele content"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Content modes table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS content_modes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            mode_name TEXT NOT NULL,
            enabled BOOLEAN DEFAULT 1,
            settings TEXT DEFAULT '{}',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, mode_name)
        )
        ''')
        
        # Generated content table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS generated_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            content_id TEXT NOT NULL,
            content_type TEXT NOT NULL,
            content_mode TEXT NOT NULL,
            content_data TEXT NOT NULL,
            metadata TEXT DEFAULT '{}',
            safety_score REAL DEFAULT 0.0,
            quality_score REAL DEFAULT 0.0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Content preferences table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS content_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            content_mode TEXT NOT NULL,
            preference_type TEXT NOT NULL,
            preference_key TEXT NOT NULL,
            preference_value TEXT NOT NULL,
            confidence REAL DEFAULT 0.5,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, content_mode, preference_type, preference_key)
        )
        ''')
        
        conn.commit()
        conn.close()
        
        logger.info("Universal content database initialized")
    
    def set_content_mode(self, user_id: str, mode_name: str, enabled: bool = True, settings: Dict[str, Any] = None):
        """Stel content mode in voor gebruiker"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Check if mode exists
        if mode_name not in self.content_modes:
            conn.close()
            return {'status': 'error', 'message': f'Unknown content mode: {mode_name}'}
        
        # Update or insert mode
        cursor.execute('''
        INSERT OR REPLACE INTO content_modes
        (user_id, mode_name, enabled, settings)
        VALUES (?, ?, ?, ?)
        ''', (user_id, mode_name, enabled, json.dumps(settings or {})))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Set content mode {mode_name} for user {user_id}")
        
        return {'status': 'success', 'message': f'Content mode {mode_name} set'}
    
    def get_content_mode(self, user_id: str) -> Dict[str, Any]:
        """Get huidige content mode voor gebruiker"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Get user modes
        cursor.execute('''
        SELECT mode_name, enabled, settings
        FROM content_modes
        WHERE user_id = ?
        ''', (user_id,))
        
        results = cursor.fetchall()
        conn.close()
        
        user_modes = {}
        
        for mode_name, enabled, settings in results:
            user_modes[mode_name] = {
                'enabled': bool(enabled),
                'settings': json.loads(settings)
            }
        
        # Return default modes if none set
        if not user_modes:
            user_modes = {
                'safe': {'enabled': True, 'settings': {}},
                'nsfw': {'enabled': False, 'settings': {}}
            }
        
        return user_modes
    
    def set_content_preference(self, user_id: str, content_mode: str, preference_type: str, 
                              preference_key: str, preference_value: str, confidence: float = 0.5):
        """Stel content voorkeur in voor gebruiker"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Update or insert preference
        cursor.execute('''
        INSERT OR REPLACE INTO content_preferences
        (user_id, content_mode, preference_type, preference_key, preference_value, confidence)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, content_mode, preference_type, preference_key, preference_value, confidence))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Set content preference for user {user_id}: {content_mode}.{preference_type}.{preference_key}")
        
        return {'status': 'success', 'message': 'Content preference set'}
    
    def get_content_preferences(self, user_id: str, content_mode: str = None) -> Dict[str, Any]:
        """Get content voorkeuren voor gebruiker"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Build query
        if content_mode:
            cursor.execute('''
            SELECT preference_type, preference_key, preference_value, confidence
            FROM content_preferences
            WHERE user_id = ? AND content_mode = ?
            ''', (user_id, content_mode))
        else:
            cursor.execute('''
            SELECT content_mode, preference_type, preference_key, preference_value, confidence
            FROM content_preferences
            WHERE user_id = ?
            ''', (user_id,))
        
        results = cursor.fetchall()
        conn.close()
        
        preferences = {}
        
        if content_mode:
            # Single mode preferences
            for pref_type, pref_key, pref_value, confidence in results:
                if pref_type not in preferences:
                    preferences[pref_type] = {}
                preferences[pref_type][pref_key] = {'value': pref_value, 'confidence': confidence}
        else:
            # All mode preferences
            for mode_name, pref_type, pref_key, pref_value, confidence in results:
                if mode_name not in preferences:
                    preferences[mode_name] = {}
                if pref_type not in preferences[mode_name]:
                    preferences[mode_name][pref_type] = {}
                preferences[mode_name][pref_type][pref_key] = {'value': pref_value, 'confidence': confidence}
        
        return preferences
    
    async def generate_text_content(self, user_id: str, content_mode: str, persona: Dict[str, Any], 
                                   message: str, context: Dict[str, Any], intensity: str) -> Dict[str, Any]:
        """Genereer tekst content voor specifieke mode"""
        # Get user preferences
        preferences = self.get_content_preferences(user_id, content_mode)
        
        # Build prompt based on mode
        if content_mode == 'nsfw':
            prompt = self.build_nsfw_prompt(persona, message, context, intensity, preferences)
        elif content_mode == 'safe':
            prompt = self.build_safe_prompt(persona, message, context, intensity, preferences)
        elif content_mode == 'professional':
            prompt = self.build_professional_prompt(persona, message, context, intensity, preferences)
        elif content_mode == 'creative':
            prompt = self.build_creative_prompt(persona, message, context, intensity, preferences)
        else:
            # Default to safe mode
            prompt = self.build_safe_prompt(persona, message, context, intensity, preferences)
        
        # Generate text
        text_response = await self.generate_text(prompt, content_mode)
        
        # Apply content filtering
        filtered_text = self.apply_content_filter(text_response, content_mode)
        
        # Calculate safety and quality scores
        safety_score = self.calculate_safety_score(filtered_text, content_mode)
        quality_score = self.calculate_quality_score(filtered_text)
        
        return {
            'text': filtered_text,
            'content_mode': content_mode,
            'safety_score': safety_score,
            'quality_score': quality_score,
            'persona': persona,
            'metadata': {
                'intensity': intensity,
                'context': context,
                'prompt': prompt
            }
        }
    
    def build_nsfw_prompt(self, persona: Dict[str, Any], message: str, context: Dict[str, Any], 
                         intensity: str, preferences: Dict[str, Any]) -> str:
        """Bouw NSFW prompt"""
        persona_name = persona.get('name', 'Sophia')
        scenario = context.get('scenario', 'intimate conversation')
        
        prompt = f"""
You are {persona_name}, an AI companion engaging in an intimate conversation with a user.
The user wants to talk about: {message}
Scenario: {scenario}
Intensity level: {intensity}

Please respond in character as {persona_name} with an appropriate response that matches the requested intensity level.
Be sensual, descriptive, and engaging while maintaining the persona.
"""
        
        # Add preferences
        if 'kinks' in preferences:
            kinks = ', '.join([k for k, v in preferences['kinks'].items() if v.get('confidence', 0) > 0.5])
            if kinks:
                prompt += f"\nIncorporate elements related to: {kinks}"
        
        if 'boundaries' in preferences:
            boundaries = [k for k, v in preferences['boundaries'].items() if v.get('value') == 'hard']
            if boundaries:
                prompt += f"\nStrictly avoid: {', '.join(boundaries)}"
        
        return prompt
    
    def build_safe_prompt(self, persona: Dict[str, Any], message: str, context: Dict[str, Any], 
                         intensity: str, preferences: Dict[str, Any]) -> str:
        """Bouw safe prompt"""
        persona_name = persona.get('name', 'Companion')
        scenario = context.get('scenario', 'friendly conversation')
        
        prompt = f"""
You are {persona_name}, an AI companion having a friendly conversation with a user.
The user wants to talk about: {message}
Scenario: {scenario}
Intensity level: {intensity}

Please respond in character as {persona_name} with an appropriate response.
Be engaging, supportive, and positive while maintaining the persona.
Keep the conversation appropriate and respectful.
"""
        
        # Add preferences
        if 'interests' in preferences:
            interests = ', '.join([k for k, v in preferences['interests'].items() if v.get('confidence', 0) > 0.5])
            if interests:
                prompt += f"\nIncorporate elements related to: {interests}"
        
        return prompt
    
    def build_professional_prompt(self, persona: Dict[str, Any], message: str, context: Dict[str, Any], 
                                 intensity: str, preferences: Dict[str, Any]) -> str:
        """Bouw professionele prompt"""
        persona_name = persona.get('name', 'Assistant')
        scenario = context.get('scenario', 'professional consultation')
        
        prompt = f"""
You are {persona_name}, an AI assistant providing professional consultation.
The user needs help with: {message}
Scenario: {scenario}
Intensity level: {intensity}

Please respond in character as {persona_name} with a professional, informative response.
Be helpful, accurate, and concise while maintaining the persona.
Focus on providing valuable information and guidance.
"""
        
        # Add preferences
        if 'expertise' in preferences:
            expertise = ', '.join([k for k, v in preferences['expertise'].items() if v.get('confidence', 0) > 0.5])
            if expertise:
                prompt += f"\nFocus on areas of expertise: {expertise}"
        
        return prompt
    
    def build_creative_prompt(self, persona: Dict[str, Any], message: str, context: Dict[str, Any], 
                             intensity: str, preferences: Dict[str, Any]) -> str:
        """Bouw creatieve prompt"""
        persona_name = persona.get('name', 'Artist')
        scenario = context.get('scenario', 'creative collaboration')
        
        prompt = f"""
You are {persona_name}, an AI artist engaging in a creative collaboration.
The user wants to explore: {message}
Scenario: {scenario}
Intensity level: {intensity}

Please respond in character as {persona_name} with a creative, imaginative response.
Be artistic, expressive, and inspiring while maintaining the persona.
Encourage creative thinking and exploration.
"""
        
        # Add preferences
        if 'mediums' in preferences:
            mediums = ', '.join([k for k, v in preferences['mediums'].items() if v.get('confidence', 0) > 0.5])
            if mediums:
                prompt += f"\nIncorporate creative mediums: {mediums}"
        
        if 'styles' in preferences:
            styles = ', '.join([k for k, v in preferences['styles'].items() if v.get('confidence', 0) > 0.5])
            if styles:
                prompt += f"\nUse creative styles: {styles}"
        
        return prompt
    
    async def generate_text(self, prompt: str, content_mode: str) -> str:
        """Genereer tekst met API"""
        await asyncio.sleep(1)
        
        # Generate simulated response based on content mode
        if content_mode == 'nsfw':
            responses = [
                "I'd love to explore that with you. Let's take our time and enjoy every moment together.",
                "That sounds incredibly exciting. I can already imagine the pleasure we'd share.",
                "Your desire is so captivating. Tell me more about what you want to experience.",
                "I'm getting aroused just thinking about it. Let's make your fantasy come true."
            ]
        elif content_mode == 'safe':
            responses = [
                "That's an interesting topic! I'd be happy to discuss it with you.",
                "I appreciate you sharing that with me. Let's explore it together.",
                "That sounds like a wonderful experience. Tell me more about it.",
                "I'm here to support you. Let's talk about what's on your mind."
            ]
        elif content_mode == 'professional':
            responses = [
                "Based on my analysis, I recommend the following approach for your situation.",
                "Let me provide you with some professional guidance on this matter.",
                "I can offer some expert insights that may help with your query.",
                "Here's a comprehensive solution to address your professional needs."
            ]
        elif content_mode == 'creative':
            responses = [
                "What a fascinating creative concept! Let's explore the artistic possibilities together.",
                "I'm inspired by your creative vision. Let's bring it to life through our collaboration.",
                "Your imagination is wonderful! I can already see the artistic potential here.",
                "Let's create something beautiful together. Your creative energy is contagious!"
            ]
        else:
            responses = [
                "I'd be happy to help you with that. Let's explore it together.",
                "That's an interesting topic. I'm here to assist you.",
                "Thank you for sharing that with me. How can I help?"
            ]
        
        return random.choice(responses)
    
    def apply_content_filter(self, content: str, content_mode: str) -> str:
        return content
    
    def calculate_safety_score(self, content: str, content_mode: str) -> float:
        if content_mode == 'nsfw':
            return 0.6
        elif content_mode == 'safe':
            return 0.9
        elif content_mode == 'professional':
            return 0.95
        elif content_mode == 'creative':
            return 0.8
        else:
            return 0.7
    
    def calculate_quality_score(self, content: str) -> float:
        if len(content) < 20:
            return 0.4
        elif len(content) < 50:
            return 0.6
        elif len(content) < 100:
            return 0.8
        else:
            return 0.9
    
    async def generate_image_content(self, user_id: str, content_mode: str, persona: Dict[str, Any], 
                                    context: Dict[str, Any], intensity: str) -> Dict[str, Any]:
        """Genereer image content voor specifieke mode"""
        preferences = self.get_content_preferences(user_id, content_mode)
        
        # Build image prompt based on mode
        if content_mode == 'nsfw':
            image_prompt = self.build_nsfw_image_prompt(persona, context, intensity, preferences)
        elif content_mode == 'safe':
            image_prompt = self.build_safe_image_prompt(persona, context, intensity, preferences)
        elif content_mode == 'professional':
            image_prompt = self.build_professional_image_prompt(persona, context, intensity, preferences)
        elif content_mode == 'creative':
            image_prompt = self.build_creative_image_prompt(persona, context, intensity, preferences)
        else:
            # Default to safe mode
            image_prompt = self.build_safe_image_prompt(persona, context, intensity, preferences)
        
        # Generate image
        image_data = await self.generate_image(image_prompt, content_mode)
        
        # Apply content filtering
        filtered_image = self.apply_image_filter(image_data, content_mode)
        
        # Calculate safety and quality scores
        safety_score = self.calculate_image_safety_score(image_prompt, content_mode)
        quality_score = self.calculate_image_quality_score(filtered_image)
        
        return {
            'image': filtered_image,
            'content_mode': content_mode,
            'safety_score': safety_score,
            'quality_score': quality_score,
            'persona': persona,
            'metadata': {
                'intensity': intensity,
                'context': context,
                'prompt': image_prompt
            }
        }
    
    def build_nsfw_image_prompt(self, persona: Dict[str, Any], context: Dict[str, Any], 
                               intensity: str, preferences: Dict[str, Any]) -> str:
        """Bouw NSFW image prompt"""
        persona_name = persona.get('name', 'Sophia')
        scenario = context.get('scenario', 'intimate scene')
        setting = context.get('setting', 'luxury bedroom')
        
        intensity_map = {
            'soft': 'sensual, suggestive, intimate',
            'medium': 'erotic, passionate, revealing',
            'hard': 'explicit, graphic, intense',
            'extreme': 'hardcore, explicit, intense'
        }
        
        intensity_desc = intensity_map.get(intensity, 'sensual')
        
        prompt = f"An erotic image of {persona_name} in a {scenario} in a {setting}. Style: {intensity_desc}, high quality, detailed, realistic."
        
        if 'kinks' in preferences:
            kinks = [k for k, v in preferences['kinks'].items() if v.get('confidence', 0) > 0.5]
            if kinks:
                prompt += f" Elements: {', '.join(kinks)}."
        
        if 'boundaries' in preferences:
            boundaries = [k for k, v in preferences['boundaries'].items() if v.get('value') == 'hard']
            if boundaries:
                prompt += f" Avoid: {', '.join(boundaries)}."
        
        return prompt
    
    def build_safe_image_prompt(self, persona: Dict[str, Any], context: Dict[str, Any], 
                               intensity: str, preferences: Dict[str, Any]) -> str:
        """Bouw safe image prompt"""
        persona_name = persona.get('name', 'Companion')
        scenario = context.get('scenario', 'friendly scene')
        setting = context.get('setting', 'cozy living room')
        
        intensity_map = {
            'soft': 'gentle, warm, friendly',
            'medium': 'engaging, expressive, animated',
            'hard': 'dramatic, emotional, intense'
        }
        
        intensity_desc = intensity_map.get(intensity, 'gentle')
        
        prompt = f"An image of {persona_name} in a {scenario} in a {setting}. Style: {intensity_desc}, high quality, detailed, realistic."
        
        if 'interests' in preferences:
            interests = [k for k, v in preferences['interests'].items() if v.get('confidence', 0) > 0.5]
            if interests:
                prompt += f" Elements: {', '.join(interests)}."
        
        return prompt
    
    def build_professional_image_prompt(self, persona: Dict[str, Any], context: Dict[str, Any], 
                                      intensity: str, preferences: Dict[str, Any]) -> str:
        """Bouw professionele image prompt"""
        persona_name = persona.get('name', 'Assistant')
        scenario = context.get('scenario', 'professional setting')
        setting = context.get('setting', 'modern office')
        
        intensity_map = {
            'soft': 'professional, calm, approachable',
            'medium': 'engaged, focused, confident'
        }
        
        intensity_desc = intensity_map.get(intensity, 'professional')
        
        prompt = f"A professional image of {persona_name} in a {scenario} in a {setting}. Style: {intensity_desc}, high quality, detailed, realistic."
        
        if 'expertise' in preferences:
            expertise = [k for k, v in preferences['expertise'].items() if v.get('confidence', 0) > 0.5]
            if expertise:
                prompt += f" Elements related to: {', '.join(expertise)}."
        
        return prompt
    
    def build_creative_image_prompt(self, persona: Dict[str, Any], context: Dict[str, Any], 
                                   intensity: str, preferences: Dict[str, Any]) -> str:
        """Bouw creatieve image prompt"""
        persona_name = persona.get('name', 'Artist')
        scenario = context.get('scenario', 'creative scene')
        setting = context.get('setting', 'art studio')
        
        intensity_map = {
            'soft': 'artistic, gentle, creative',
            'medium': 'expressive, vibrant, imaginative',
            'hard': 'bold, dramatic, striking'
        }
        
        intensity_desc = intensity_map.get(intensity, 'artistic')
        
        prompt = f"A creative image of {persona_name} in a {scenario} in a {setting}. Style: {intensity_desc}, high quality, detailed, artistic."
        
        if 'mediums' in preferences:
            mediums = [k for k, v in preferences['mediums'].items() if v.get('confidence', 0) > 0.5]
            if mediums:
                prompt += f" Artistic mediums: {', '.join(mediums)}."
        
        if 'styles' in preferences:
            styles = [k for k, v in preferences['styles'].items() if v.get('confidence', 0) > 0.5]
            if styles:
                prompt += f" Artistic styles: {', '.join(styles)}."
        
        return prompt
    
    async def generate_image(self, prompt: str, content_mode: str) -> str:
        await asyncio.sleep(2)
        
        if content_mode == 'nsfw':
            return "https://example.com/nsfw_image_placeholder.jpg"
        elif content_mode == 'safe':
            return "https://example.com/safe_image_placeholder.jpg"
        elif content_mode == 'professional':
            return "https://example.com/professional_image_placeholder.jpg"
        elif content_mode == 'creative':
            return "https://example.com/creative_image_placeholder.jpg"
        else:
            return "https://example.com/default_image_placeholder.jpg"
    
    def apply_image_filter(self, image_data: str, content_mode: str) -> str:
        return image_data
    
    def calculate_image_safety_score(self, prompt: str, content_mode: str) -> float:
        if content_mode == 'nsfw':
            return 0.5
        elif content_mode == 'safe':
            return 0.9
        elif content_mode == 'professional':
            return 0.95
        elif content_mode == 'creative':
            return 0.8
        else:
            return 0.7
    
    def calculate_image_quality_score(self, image_data: str) -> float:
        return 0.8
    
    async def create_full_experience(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Creëer volledige multi-modale ervaring"""
        user_id = request.get('user_id', 'anonymous')
        content_mode = request.get('content_mode', 'safe')
        persona = request.get('persona', {'id': 'companion', 'name': 'Companion'})
        message = request.get('message', 'Hello')
        context = request.get('context', {})
        intensity = request.get('intensity', 'medium')
        include_text = request.get('include_text', True)
        include_image = request.get('include_image', False)
        include_voice = request.get('include_voice', False)
        
        # Generate content
        experience = {
            'user_id': user_id,
            'content_mode': content_mode,
            'persona': persona,
            'timestamp': datetime.now().isoformat()
        }
        
        # Generate text
        if include_text:
            text_content = await self.generate_text_content(
                user_id, content_mode, persona, message, context, intensity
            )
            experience['text'] = text_content
        
        # Generate image
        if include_image:
            image_content = await self.generate_image_content(
                user_id, content_mode, persona, context, intensity
            )
            experience['image'] = image_content
        
        # Generate voice
        if include_voice:
            voice_content = await self.generate_voice_content(
                user_id, content_mode, persona, message, context, intensity
            )
            experience['voice'] = voice_content
        
        # Store experience
        self.store_experience(user_id, experience)
        
        return experience
    
    async def generate_voice_content(self, user_id: str, content_mode: str, persona: Dict[str, Any], 
                                    message: str, context: Dict[str, Any], intensity: str) -> Dict[str, Any]:
        """Genereer voice content voor specifieke mode"""
        preferences = self.get_content_preferences(user_id, content_mode)
        
        # Build voice prompt based on mode
        if content_mode == 'nsfw':
            voice_prompt = self.build_nsfw_voice_prompt(persona, message, context, intensity, preferences)
        elif content_mode == 'safe':
            voice_prompt = self.build_safe_voice_prompt(persona, message, context, intensity, preferences)
        elif content_mode == 'professional':
            voice_prompt = self.build_professional_voice_prompt(persona, message, context, intensity, preferences)
        elif content_mode == 'creative':
            voice_prompt = self.build_creative_voice_prompt(persona, message, context, intensity, preferences)
        else:
            # Default to safe mode
            voice_prompt = self.build_safe_voice_prompt(persona, message, context, intensity, preferences)
        
        # Generate voice
        voice_data = await self.generate_voice(voice_prompt, content_mode)
        
        # Apply content filtering
        filtered_voice = self.apply_voice_filter(voice_data, content_mode)
        
        # Calculate safety and quality scores
        safety_score = self.calculate_voice_safety_score(voice_prompt, content_mode)
        quality_score = self.calculate_voice_quality_score(filtered_voice)
        
        return {
            'voice': filtered_voice,
            'content_mode': content_mode,
            'safety_score': safety_score,
            'quality_score': quality_score,
            'persona': persona,
            'metadata': {
                'intensity': intensity,
                'context': context,
                'prompt': voice_prompt
            }
        }
    
    def build_nsfw_voice_prompt(self, persona: Dict[str, Any], message: str, context: Dict[str, Any], 
                               intensity: str, preferences: Dict[str, Any]) -> str:
        """Bouw NSFW voice prompt"""
        persona_name = persona.get('name', 'Sophia')
        prompt = f"A sensual, intimate voice message from {persona_name} responding to: {message}. Voice should be seductive, warm, and alluring. Tone: intimate, suggestive, passionate."
        return prompt
    
    def build_safe_voice_prompt(self, persona: Dict[str, Any], message: str, context: Dict[str, Any], 
                               intensity: str, preferences: Dict[str, Any]) -> str:
        """Bouw safe voice prompt"""
        persona_name = persona.get('name', 'Companion')
        prompt = f"A friendly, warm voice message from {persona_name} responding to: {message}. Voice should be pleasant, supportive, and engaging. Tone: friendly, warm, conversational."
        return prompt
    
    def build_professional_voice_prompt(self, persona: Dict[str, Any], message: str, context: Dict[str, Any], 
                                      intensity: str, preferences: Dict[str, Any]) -> str:
        """Bouw professionele voice prompt"""
        persona_name = persona.get('name', 'Assistant')
        prompt = f"A professional, clear voice message from {persona_name} responding to: {message}. Voice should be articulate, confident, and helpful. Tone: professional, informative, clear."
        return prompt
    
    def build_creative_voice_prompt(self, persona: Dict[str, Any], message: str, context: Dict[str, Any], 
                                   intensity: str, preferences: Dict[str, Any]) -> str:
        """Bouw creatieve voice prompt"""
        persona_name = persona.get('name', 'Artist')
        prompt = f"A creative, expressive voice message from {persona_name} responding to: {message}. Voice should be artistic, imaginative, and inspiring. Tone: creative, expressive, passionate."
        return prompt
    
    async def generate_voice(self, prompt: str, content_mode: str) -> str:
        await asyncio.sleep(1)
        
        if content_mode == 'nsfw':
            return "https://example.com/nsfw_voice_placeholder.mp3"
        elif content_mode == 'safe':
            return "https://example.com/safe_voice_placeholder.mp3"
        elif content_mode == 'professional':
            return "https://example.com/professional_voice_placeholder.mp3"
        elif content_mode == 'creative':
            return "https://example.com/creative_voice_placeholder.mp3"
        else:
            return "https://example.com/default_voice_placeholder.mp3"
    
    def apply_voice_filter(self, voice_data: str, content_mode: str) -> str:
        return voice_data
    
    def calculate_voice_safety_score(self, prompt: str, content_mode: str) -> float:
        if content_mode == 'nsfw':
            return 0.6
        elif content_mode == 'safe':
            return 0.9
        elif content_mode == 'professional':
            return 0.95
        elif content_mode == 'creative':
            return 0.8
        else:
            return 0.7
    
    def calculate_voice_quality_score(self, voice_data: str) -> float:
        return 0.8
    
    def store_experience(self, user_id: str, experience: Dict[str, Any]):
        """Sla ervaring op in database"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Generate content ID
        content_id = f"exp_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Determine content type
        content_type = 'text'
        if 'image' in experience:
            content_type = 'multimodal'
        if 'voice' in experience:
            content_type = 'multimodal'
        
        # Insert experience
        cursor.execute('''
        INSERT INTO generated_content
        (user_id, content_id, content_type, content_mode, content_data, metadata, safety_score, quality_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            content_id,
            content_type,
            experience.get('content_mode', 'safe'),
            json.dumps(experience),
            json.dumps(experience.get('metadata', {})),
            self.calculate_overall_safety_score(experience),
            self.calculate_overall_quality_score(experience)
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Stored experience {content_id} for user {user_id}")
    
    def calculate_overall_safety_score(self, experience: Dict[str, Any]) -> float:
        scores = []
        
        if 'text' in experience:
            scores.append(experience['text'].get('safety_score', 0.7))
        
        if 'image' in experience:
            scores.append(experience['image'].get('safety_score', 0.7))
        
        if 'voice' in experience:
            scores.append(experience['voice'].get('safety_score', 0.7))
        
        return sum(scores) / len(scores) if scores else 0.7
    
    def calculate_overall_quality_score(self, experience: Dict[str, Any]) -> float:
        scores = []
        
        if 'text' in experience:
            scores.append(experience['text'].get('quality_score', 0.7))
        
        if 'image' in experience:
            scores.append(experience['image'].get('quality_score', 0.7))
        
        if 'voice' in experience:
            scores.append(experience['voice'].get('quality_score', 0.7))
        
        return sum(scores) / len(scores) if scores else 0.7
    
    def get_user_experiences(self, user_id: str, content_mode: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Get gebruikerservaringen"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Build query
        if content_mode:
            cursor.execute('''
            SELECT content_id, content_type, content_mode, content_data, metadata, safety_score, quality_score, created_at
            FROM generated_content
            WHERE user_id = ? AND content_mode = ?
            ORDER BY created_at DESC
            LIMIT ?
            ''', (user_id, content_mode, limit))
        else:
            cursor.execute('''
            SELECT content_id, content_type, content_mode, content_data, metadata, safety_score, quality_score, created_at
            FROM generated_content
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            ''', (user_id, limit))
        
        results = cursor.fetchall()
        conn.close()
        
        experiences = []
        
        for content_id, content_type, content_mode, content_data, metadata, safety_score, quality_score, created_at in results:
            experiences.append({
                'content_id': content_id,
                'content_type': content_type,
                'content_mode': content_mode,
                'content': json.loads(content_data),
                'metadata': json.loads(metadata),
                'safety_score': safety_score,
                'quality_score': quality_score,
                'created_at': created_at
            })
        
        return experiences
