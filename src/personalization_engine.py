import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import numpy as np
from collections import defaultdict
import logging

logger = logging.getLogger("personalization_engine")

class NSFWPersonalizationEngine:
    """
    Geavanceerde personalisatie engine die leert van gebruikersinteracties
    en gepersonaliseerde NSFW content genereert
    """
    
    def __init__(self):
        self.db_path = Path.home() / ".supergrok_cache" / "personalization.db"
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_database()
        
        # Learning parameters
        self.learning_rate = 0.1
        self.decay_factor = 0.95
        self.min_interaction_threshold = 5
        
        # Preference matrices (cached/in-memory if needed, but we query DB)
        self.kink_preferences = {}
        self.intensity_calibration = {}
        self.emotional_responses = {}
        self.temporal_patterns = {}
        
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def init_database(self):
        """Initialiseer SQLite database voor user data"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # User interactions table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            persona_id TEXT NOT NULL,
            message TEXT NOT NULL,
            response TEXT NOT NULL,
            reaction_time REAL,
            media_requested BOOLEAN DEFAULT FALSE,
            media_type TEXT,
            intensity_requested TEXT,
            rating INTEGER,
            feedback TEXT
        )
        ''')
        
        # User preferences table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            preference_type TEXT NOT NULL,
            preference_key TEXT NOT NULL,
            preference_value REAL NOT NULL,
            confidence REAL DEFAULT 0.5,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, preference_type, preference_key)
        )
        ''')
        
        # User boundaries table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_boundaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            boundary_type TEXT NOT NULL,
            boundary_key TEXT NOT NULL,
            boundary_level TEXT NOT NULL,
            established_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_respected DATETIME,
            violation_count INTEGER DEFAULT 0,
            UNIQUE(user_id, boundary_type, boundary_key)
        )
        ''')
        
        conn.commit()
        conn.close()
    
    def track_interaction(self, user_id: str, session_id: str, interaction_data: Dict[str, Any]):
        """Track gebruikersinteractie voor learning"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Insert interaction
        cursor.execute('''
        INSERT INTO user_interactions 
        (user_id, session_id, persona_id, message, response, reaction_time, 
         media_requested, media_type, intensity_requested, rating, feedback)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            session_id,
            interaction_data.get('persona_id', 'unknown') or 'unknown',
            interaction_data.get('message', ''),
            interaction_data.get('response', ''),
            interaction_data.get('reaction_time'),
            interaction_data.get('media_requested', False),
            interaction_data.get('media_type'),
            interaction_data.get('intensity_requested'),
            interaction_data.get('rating'),
            interaction_data.get('feedback')
        ))
        
        conn.commit()
        conn.close()
        
        # Update preferences based on interaction
        self.update_preferences(user_id, interaction_data)
    
    def update_preferences(self, user_id: str, interaction_data: Dict[str, Any]):
        """Update gebruikersvoorkeuren based op interactie"""
        # Extract preference indicators
        media_requested = interaction_data.get('media_requested', False)
        intensity_requested = interaction_data.get('intensity_requested', 'medium')
        rating = interaction_data.get('rating')
        message = interaction_data.get('message', '').lower()
        response = interaction_data.get('response', '').lower()
        
        # Update media preference
        if media_requested:
            self.update_preference(
                user_id, 'media', 'visual_preference', 1.0
            )
        
        # Update intensity preference
        intensity_map = {'soft': 0.25, 'medium': 0.5, 'hard': 0.75, 'extreme': 1.0}
        intensity_value = intensity_map.get(intensity_requested, 0.5)
        self.update_preference(
            user_id, 'intensity', 'preferred_level', intensity_value
        )
        
        # Update kink preferences based on message content
        detected_kinks = self.detect_kinks_from_message(message)
        for kink in detected_kinks:
            self.update_preference(
                user_id, 'kink', kink, 0.7
            )
        
        # Update emotional response patterns
        emotional_indicators = self.detect_emotional_indicators(message, response)
        for emotion, value in emotional_indicators.items():
            self.update_preference(
                user_id, 'emotion', emotion, value
            )
        
        # Update temporal patterns
        hour = datetime.now().hour
        self.update_preference(
            user_id, 'temporal', f'activity_hour_{hour}', 1.0
        )
    
    def update_preference(self, user_id: str, preference_type: str, 
                         preference_key: str, value: float):
        """Update specifieke preference met learning"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Check if preference exists
        cursor.execute('''
        SELECT preference_value, confidence FROM user_preferences
        WHERE user_id = ? AND preference_type = ? AND preference_key = ?
        ''', (user_id, preference_type, preference_key))
        
        result = cursor.fetchone()
        
        if result:
            # Update existing preference with learning
            old_value, old_confidence = result
            
            # Apply learning algorithm
            new_value = (old_value * old_confidence + value * self.learning_rate) / (old_confidence + self.learning_rate)
            new_confidence = min(old_confidence + self.learning_rate, 1.0)
            
            cursor.execute('''
            UPDATE user_preferences
            SET preference_value = ?, confidence = ?, last_updated = CURRENT_TIMESTAMP
            WHERE user_id = ? AND preference_type = ? AND preference_key = ?
            ''', (new_value, new_confidence, user_id, preference_type, preference_key))
        else:
            # Insert new preference
            cursor.execute('''
            INSERT INTO user_preferences
            (user_id, preference_type, preference_key, preference_value, confidence)
            VALUES (?, ?, ?, ?, ?)
            ''', (user_id, preference_type, preference_key, value, self.learning_rate))
        
        conn.commit()
        conn.close()
    
    def detect_kinks_from_message(self, message: str) -> List[str]:
        """Detect kinks van gebruikersbericht"""
        kink_keywords = {
            'bondage': ['tie', 'rope', 'cuff', 'restraint', 'bound'],
            'dominance': ['dominant', 'control', 'submit', 'obey', 'command'],
            'submission': ['submissive', 'serve', 'worship', 'kneel', 'please'],
            'exhibitionism': ['show', 'exhibit', 'public', 'watch', 'display'],
            'voyeurism': ['watch', 'peek', 'spy', 'hidden', 'secret'],
            'roleplay': ['roleplay', 'costume', 'character', 'scenario', 'pretend'],
            'age_play': ['daddy', 'mommy', 'little', 'age', 'regress'],
            'pet_play': ['puppy', 'kitten', 'pet', 'collar', 'leash'],
            'sensation_play': ['sensation', 'temperature', 'wax', 'ice', 'impact'],
            'foot_fetish': ['foot', 'feet', 'toes', 'sole', 'heel']
        }
        
        detected_kinks = []
        
        for kink, keywords in kink_keywords.items():
            if any(keyword in message for keyword in keywords):
                detected_kinks.append(kink)
        
        return detected_kinks
    
    def detect_emotional_indicators(self, message: str, response: str) -> Dict[str, float]:
        """Detect emotionele indicatoren van interactie"""
        emotion_keywords = {
            'arousal': ['horny', 'turned on', 'excited', 'aroused', 'hot'],
            'affection': ['love', 'care', 'cherish', 'adore', 'treasure'],
            'curiosity': ['curious', 'wonder', 'explore', 'discover', 'try'],
            'nervousness': ['nervous', 'anxious', 'scared', 'worried', 'tense'],
            'playfulness': ['playful', 'fun', 'tease', 'joke', 'laugh'],
            'submission': ['submit', 'obey', 'serve', 'please', 'worship'],
            'dominance': ['control', 'dominate', 'command', 'lead', 'power']
        }
        
        emotional_indicators = {}
        
        for emotion, keywords in emotion_keywords.items():
            message_count = sum(1 for keyword in keywords if keyword in message)
            response_count = sum(1 for keyword in keywords if keyword in response)
            
            if message_count > 0 or response_count > 0:
                emotional_indicators[emotion] = min((message_count + response_count) * 0.2, 1.0)
        
        return emotional_indicators
    
    def get_user_preferences(self, user_id: str) -> Dict[str, Dict[str, float]]:
        """Get alle gebruikersvoorkeuren"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT preference_type, preference_key, preference_value, confidence
        FROM user_preferences
        WHERE user_id = ? AND confidence > 0.3
        ORDER BY confidence DESC
        ''', (user_id,))
        
        results = cursor.fetchall()
        conn.close()
        
        preferences = defaultdict(dict)
        
        for pref_type, pref_key, pref_value, confidence in results:
            preferences[pref_type][pref_key] = pref_value
        
        return dict(preferences)
    
    def get_user_boundaries(self, user_id: str) -> Dict[str, str]:
        """Get gebruikersboundaries"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT boundary_type, boundary_key, boundary_level
        FROM user_boundaries
        WHERE user_id = ?
        ''', (user_id,))
        
        results = cursor.fetchall()
        conn.close()
        
        boundaries = {}
        
        for boundary_type, boundary_key, boundary_level in results:
            boundaries[f"{boundary_type}.{boundary_key}"] = boundary_level
        
        return boundaries
    
    def generate_personalized_scene(self, user_id: str, persona: Dict[str, Any]) -> Dict[str, Any]:
        """Genereer gepersonaliseerde scene based op gebruikersvoorkeuren"""
        preferences = self.get_user_preferences(user_id)
        boundaries = self.get_user_boundaries(user_id)
        
        # Determine preferred intensity
        intensity_preferences = preferences.get('intensity', {})
        preferred_intensity = intensity_preferences.get('preferred_level', 0.5)
        
        intensity_map = {0.25: 'soft', 0.5: 'medium', 0.75: 'hard', 1.0: 'extreme'}
        intensity = intensity_map.get(preferred_intensity, 'medium')
        
        # Determine preferred kinks
        kink_preferences = preferences.get('kink', {})
        top_kinks = sorted(kink_preferences.items(), key=lambda x: x[1], reverse=True)[:3]
        primary_kinks = [kink for kink, score in top_kinks if score > 0.5]
        
        # Determine emotional tone
        emotion_preferences = preferences.get('emotion', {})
        top_emotion = 'affection'
        if emotion_preferences:
            top_emotion = max(emotion_preferences.items(), key=lambda x: x[1])[0]
        
        # Determine media preference
        media_preferences = preferences.get('media', {})
        prefers_visual = media_preferences.get('visual_preference', 0.5) > 0.5
        
        # Determine temporal pattern
        current_hour = datetime.now().hour
        temporal_preferences = preferences.get('temporal', {})
        activity_score = temporal_preferences.get(f'activity_hour_{current_hour}', 0.5)
        
        # Build personalized scene config
        scene_config = {
            'user_id': user_id,
            'persona': persona,
            'intensity': intensity,
            'primary_kinks': primary_kinks,
            'emotional_tone': top_emotion,
            'visual_preference': prefers_visual,
            'activity_level': activity_score,
            'boundaries': boundaries
        }
        
        return scene_config
    
    def establish_boundaries(self, user_id: str, boundary_data: Dict[str, str]):
        """Stel gebruikersboundaries in"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        for boundary_key, boundary_level in boundary_data.items():
            if '.' in boundary_key:
                boundary_type, boundary_name = boundary_key.split('.', 1)
            else:
                boundary_type, boundary_name = 'boundary', boundary_key
            
            cursor.execute('''
            INSERT OR REPLACE INTO user_boundaries
            (user_id, boundary_type, boundary_key, boundary_level, established_date)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (user_id, boundary_type, boundary_name, boundary_level))
        
        conn.commit()
        conn.close()
    
    def check_boundary_violation(self, user_id: str, content: str) -> Dict[str, Any]:
        """Check of content grenzen overschrijdt"""
        boundaries = self.get_user_boundaries(user_id)
        violations = []
        
        for boundary_key, boundary_level in boundaries.items():
            # key is like boundary_type.boundary_name
            if '.' in boundary_key:
                boundary_type, boundary_name = boundary_key.split('.', 1)
            else:
                boundary_type, boundary_name = 'boundary', boundary_key
            
            # If boundary level is 'hard' and boundary word occurs in content
            if boundary_level == 'hard' and boundary_name.lower() in content.lower():
                violations.append({
                    'type': boundary_type,
                    'name': boundary_name,
                    'level': boundary_level,
                    'detected': True
                })
        
        return {
            'violations': violations,
            'safe': len(violations) == 0
        }
    
    def get_learning_summary(self, user_id: str) -> Dict[str, Any]:
        """Get samenvatting van geleerde data"""
        preferences = self.get_user_preferences(user_id)
        boundaries = self.get_user_boundaries(user_id)
        
        # Count interactions
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT COUNT(*) FROM user_interactions WHERE user_id = ?
        ''', (user_id,))
        interaction_count = cursor.fetchone()[0]
        
        cursor.execute('''
        SELECT COUNT(*) FROM user_interactions 
        WHERE user_id = ? AND media_requested = 1
        ''', (user_id,))
        media_request_count = cursor.fetchone()[0]
        
        # Fetch confidence directly from user_preferences to avoid floats subscriptable type errors
        cursor.execute('''
        SELECT confidence FROM user_preferences WHERE user_id = ?
        ''', (user_id,))
        confidences = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        
        learning_confidence = float(np.mean(confidences)) if confidences else 0.5
        
        return {
            'interaction_count': interaction_count,
            'media_request_count': media_request_count,
            'media_request_rate': media_request_count / max(interaction_count, 1),
            'top_kinks': sorted(preferences.get('kink', {}).items(), key=lambda x: x[1], reverse=True)[:3],
            'preferred_intensity': preferences.get('intensity', {}).get('preferred_level', 0.5),
            'emotional_tendencies': preferences.get('emotion', {}),
            'boundaries_count': len(boundaries),
            'learning_confidence': learning_confidence
        }
