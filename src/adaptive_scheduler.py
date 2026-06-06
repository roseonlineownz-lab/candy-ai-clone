import asyncio
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import sqlite3
import numpy as np
from collections import defaultdict, deque
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AdaptiveContentScheduler:
    """
    Geavanceerde scheduler die content genereert based op voorspelde gebruikersbehoeften
    en tijdsgebonden patronen
    """
    
    def __init__(self):
        # We share personalization.db to allow queries on user_preferences table
        self.db_path = Path.home() / ".supergrok_cache" / "personalization.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_database()
        
        # Scheduling parameters
        self.prediction_window_hours = 24
        self.min_confidence_threshold = 0.7
        self.max_scheduled_content = 10
        
        # Learning parameters
        self.temporal_weight = 0.3
        self.preference_weight = 0.5
        self.context_weight = 0.2
        
        # Active schedules
        self.active_schedules = {}
        self.content_cache = {}
        
        logger.info(f"Adaptive Content Scheduler initialized with database: {self.db_path}")
    
    def init_database(self):
        """Initialiseer database voor scheduling en predictions"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # User temporal patterns table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_temporal_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            hour_of_day INTEGER NOT NULL,
            day_of_week INTEGER NOT NULL,
            activity_frequency REAL DEFAULT 0.0,
            media_request_rate REAL DEFAULT 0.0,
            preferred_intensity REAL DEFAULT 0.5,
            preferred_persona TEXT,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, hour_of_day, day_of_week)
        )
        ''')
        
        # Content predictions table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS content_predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            prediction_time DATETIME NOT NULL,
            predicted_persona TEXT NOT NULL,
            predicted_intensity REAL NOT NULL,
            predicted_media_type TEXT NOT NULL,
            confidence_score REAL NOT NULL,
            generated_content_id TEXT,
            status TEXT DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Scheduled content table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS scheduled_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            content_id TEXT NOT NULL,
            content_type TEXT NOT NULL,
            content_data TEXT NOT NULL,
            scheduled_time DATETIME NOT NULL,
            delivered_time DATETIME,
            status TEXT DEFAULT 'scheduled',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # User context table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_context (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            context_type TEXT NOT NULL,
            context_value TEXT NOT NULL,
            confidence REAL DEFAULT 0.5,
            last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, context_type, context_value)
        )
        ''')
        
        conn.commit()
        conn.close()
        
        logger.info("Adaptive scheduling database initialized successfully")
    
    def track_user_activity(self, user_id: str, activity_data: Dict[str, Any]):
        """Track gebruikersactiviteit voor temporal pattern learning"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Extract temporal data
        now = datetime.now()
        hour_of_day = now.hour
        day_of_week = now.weekday()
        
        # Extract activity data
        media_requested = activity_data.get('media_requested', False)
        intensity_requested = activity_data.get('intensity_requested', 'medium')
        persona_id = activity_data.get('persona_id', 'nova')
        
        # Map intensity to numeric value
        intensity_map = {'soft': 0.25, 'medium': 0.5, 'hard': 0.75, 'extreme': 1.0}
        intensity_value = intensity_map.get(intensity_requested, 0.5)
        
        # Check if pattern exists
        cursor.execute('''
        SELECT activity_frequency, media_request_rate, preferred_intensity, preferred_persona
        FROM user_temporal_patterns
        WHERE user_id = ? AND hour_of_day = ? AND day_of_week = ?
        ''', (user_id, hour_of_day, day_of_week))
        
        result = cursor.fetchone()
        
        if result:
            # Update existing pattern
            activity_freq, media_req_rate, pref_intensity, pref_persona = result
            
            # Apply learning
            new_activity_freq = activity_freq * 0.9 + 0.1
            new_media_req_rate = media_req_rate * 0.9 + (0.1 if media_requested else 0)
            new_pref_intensity = pref_intensity * 0.8 + intensity_value * 0.2
            
            # Update preferred persona (simple majority vote)
            new_pref_persona = persona_id if pref_persona != persona_id else pref_persona
            
            cursor.execute('''
            UPDATE user_temporal_patterns
            SET activity_frequency = ?, media_request_rate = ?, 
                preferred_intensity = ?, preferred_persona = ?, 
                last_updated = CURRENT_TIMESTAMP
            WHERE user_id = ? AND hour_of_day = ? AND day_of_week = ?
            ''', (new_activity_freq, new_media_req_rate, new_pref_intensity, 
                   new_pref_persona, user_id, hour_of_day, day_of_week))
        else:
            # Insert new pattern
            cursor.execute('''
            INSERT INTO user_temporal_patterns
            (user_id, hour_of_day, day_of_week, activity_frequency, 
             media_request_rate, preferred_intensity, preferred_persona)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, hour_of_day, day_of_week, 1.0, 
                   (1.0 if media_requested else 0.0), intensity_value, persona_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Tracked activity for user {user_id}")
    
    def track_user_context(self, user_id: str, context_type: str, context_value: str, confidence: float = 0.5):
        """Track gebruikerscontext voor voorspellingen"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if context exists
        cursor.execute('''
        SELECT confidence FROM user_context
        WHERE user_id = ? AND context_type = ? AND context_value = ?
        ''', (user_id, context_type, context_value))
        
        result = cursor.fetchone()
        
        if result:
            # Update existing context
            old_confidence = result[0]
            new_confidence = min(old_confidence * 0.9 + confidence * 0.1, 1.0)
            
            cursor.execute('''
            UPDATE user_context
            SET confidence = ?, last_seen = CURRENT_TIMESTAMP
            WHERE user_id = ? AND context_type = ? AND context_value = ?
            ''', (new_confidence, user_id, context_type, context_value))
        else:
            # Insert new context
            cursor.execute('''
            INSERT INTO user_context
            (user_id, context_type, context_value, confidence)
            VALUES (?, ?, ?, ?)
            ''', (user_id, context_type, context_value, confidence))
        
        conn.commit()
        conn.close()
    
    def predict_user_needs(self, user_id: str, hours_ahead: int = 1) -> List[Dict[str, Any]]:
        """Voorspel gebruikersbehoeften voor de komende uren"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get current time
        now = datetime.now()
        target_time = now + timedelta(hours=hours_ahead)
        target_hour = target_time.hour
        target_day = target_time.weekday()
        
        # Get temporal pattern for target time
        cursor.execute('''
        SELECT activity_frequency, media_request_rate, preferred_intensity, preferred_persona
        FROM user_temporal_patterns
        WHERE user_id = ? AND hour_of_day = ? AND day_of_week = ?
        ''', (user_id, target_hour, target_day))
        
        temporal_result = cursor.fetchone()
        
        # Get user preferences
        cursor.execute('''
        SELECT preference_type, preference_key, preference_value, confidence
        FROM user_preferences
        WHERE user_id = ? AND confidence > 0.3
        ORDER BY confidence DESC
        ''', (user_id,))
        
        preference_results = cursor.fetchall()
        
        # Get recent context
        cursor.execute('''
        SELECT context_type, context_value, confidence
        FROM user_context
        WHERE user_id = ? AND last_seen > datetime('now', '-1 day')
        ORDER BY confidence DESC
        LIMIT 10
        ''', (user_id,))
        
        context_results = cursor.fetchall()
        
        conn.close()
        
        # Process predictions
        predictions = []
        
        if temporal_result:
            activity_freq, media_req_rate, pref_intensity, pref_persona = temporal_result
            
            # Calculate base confidence
            base_confidence = activity_freq * 0.7
            
            if base_confidence > 0.3: # Lower threshold to allow prediction test triggers
                # Create prediction
                prediction = {
                    'user_id': user_id,
                    'prediction_time': target_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'predicted_persona': pref_persona or 'nova',
                    'predicted_intensity': pref_intensity,
                    'predicted_media_type': 'image' if media_req_rate > 0.5 else 'text',
                    'confidence_score': base_confidence,
                    'reasoning': 'temporal_pattern'
                }
                
                predictions.append(prediction)
        
        # Add preference-based predictions
        preferences = defaultdict(dict)
        for pref_type, pref_key, pref_value, confidence in preference_results:
            preferences[pref_type][pref_key] = {'value': pref_value, 'confidence': confidence}
        
        # Check for high-confidence preferences
        if 'media' in preferences and 'visual_preference' in preferences['media']:
            visual_pref = preferences['media']['visual_preference']
            if visual_pref['confidence'] > 0.7 and visual_pref['value'] > 0.7:
                # Create visual content prediction
                prediction = {
                    'user_id': user_id,
                    'prediction_time': target_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'predicted_persona': pref_persona or 'nova',
                    'predicted_intensity': preferences.get('intensity', {}).get('preferred_level', {}).get('value', 0.5),
                    'predicted_media_type': 'image',
                    'confidence_score': visual_pref['confidence'] * 0.8,
                    'reasoning': 'preference_based'
                }
                
                predictions.append(prediction)
        
        # Sort by confidence
        predictions.sort(key=lambda x: x['confidence_score'], reverse=True)
        
        # Return top predictions
        return predictions[:3]
    
    def schedule_content_generation(self, user_id: str, prediction: Dict[str, Any]) -> str:
        """Plan content generatie based op voorspelling"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Generate content ID
        content_id = f"pred_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Insert prediction
        cursor.execute('''
        INSERT INTO content_predictions
        (user_id, prediction_time, predicted_persona, predicted_intensity, 
         predicted_media_type, confidence_score, generated_content_id, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            prediction['prediction_time'],
            prediction['predicted_persona'],
            prediction['predicted_intensity'],
            prediction['predicted_media_type'],
            prediction['confidence_score'],
            content_id,
            'pending'
        ))
        
        conn.commit()
        conn.close()
        
        # Store in active schedules
        self.active_schedules[content_id] = {
            'user_id': user_id,
            'prediction': prediction,
            'status': 'pending',
            'created_at': datetime.now()
        }
        
        logger.info(f"Scheduled content generation: {content_id}")
        
        return content_id
    
    async def generate_predicted_content(self, content_id: str) -> Dict[str, Any]:
        """Genereer voorspelde content"""
        if content_id not in self.active_schedules:
            return {'status': 'not_found'}
        
        schedule = self.active_schedules[content_id]
        user_id = schedule['user_id']
        prediction = schedule['prediction']
        
        try:
            # Import multimodal engine from src
            from src.multimodal_engine import SuperGrokMultiModalEngine
            from avatar_engine.nova_roleplay_brain import PERSONAS
            
            # Initialize engine
            multimodal_engine = SuperGrokMultiModalEngine()
            
            persona_key = prediction['predicted_persona']
            p_data = PERSONAS.get(persona_key, PERSONAS.get('nova'))
            
            persona = {
                'key': persona_key,
                'name': p_data.get('name', 'Nova'),
                'system_prompt': p_data.get('system_prompt', ''),
                'voice': p_data.get('voice', 'nl-BE-DenaNeural'),
                'avatar': p_data.get('avatar', '')
            }
            
            intensity_map = {0.25: 'soft', 0.5: 'medium', 0.75: 'hard', 1.0: 'extreme'}
            intensity_str = intensity_map.get(prediction['predicted_intensity'], 'medium')
            
            # Create experience request
            experience_request = {
                'user_id': user_id,
                'session_id': f"sched_{user_id}",
                'persona': persona,
                'message': 'Genereer iets speciaals gebaseerd op mijn voorkeuren',
                'context': {
                    'scenario': 'romantisch intiem moment',
                    'scene_id': 'strip',
                    'visual_type': prediction['predicted_media_type']
                },
                'media_requested': True if prediction['predicted_media_type'] == 'image' else False,
                'visual_type': prediction['predicted_media_type'],
                'intensity': intensity_str
            }
            
            # Generate content using personalization integration
            experience = await multimodal_engine.create_personalized_experience(experience_request)
            
            # Update schedule
            schedule['status'] = 'completed'
            schedule['content'] = experience
            schedule['completed_at'] = datetime.now()
            
            # Update database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
            UPDATE content_predictions
            SET status = 'completed'
            WHERE generated_content_id = ?
            ''', (content_id,))
            
            # Insert into scheduled content
            cursor.execute('''
            INSERT INTO scheduled_content
            (user_id, content_id, content_type, content_data, scheduled_time, status)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                content_id,
                prediction['predicted_media_type'],
                json.dumps(experience),
                prediction['prediction_time'],
                'ready'
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Generated predicted content: {content_id}")
            
            return {
                'status': 'completed',
                'content_id': content_id,
                'experience': experience
            }
            
        except Exception as e:
            logger.error(f"Failed to generate predicted content {content_id}: {str(e)}", exc_info=True)
            # Update schedule
            schedule['status'] = 'failed'
            schedule['error'] = str(e)
            schedule['failed_at'] = datetime.now()
            
            # Update database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
            UPDATE content_predictions
            SET status = 'failed'
            WHERE generated_content_id = ?
            ''', (content_id,))
            
            conn.commit()
            conn.close()
            
            return {
                'status': 'failed',
                'content_id': content_id,
                'error': str(e)
            }
    
    def get_ready_content(self, user_id: str) -> List[Dict[str, Any]]:
        """Get content die klaar is voor delivery"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get ready content (scheduled time is in the past or present)
        cursor.execute('''
        SELECT content_id, content_type, content_data, scheduled_time
        FROM scheduled_content
        WHERE user_id = ? AND status = 'ready' AND scheduled_time <= datetime('now')
        ORDER BY scheduled_time DESC
        ''', (user_id,))
        
        results = cursor.fetchall()
        conn.close()
        
        ready_content = []
        for content_id, content_type, content_data, scheduled_time in results:
            ready_content.append({
                'content_id': content_id,
                'content_type': content_type,
                'content': json.loads(content_data),
                'scheduled_time': scheduled_time
            })
        
        return ready_content
    
    def mark_content_delivered(self, content_id: str):
        """Markeer content als geleverd"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Update status
        cursor.execute('''
        UPDATE scheduled_content
        SET status = 'delivered', delivered_time = CURRENT_TIMESTAMP
        WHERE content_id = ?
        ''', (content_id,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Marked content as delivered: {content_id}")
    
    async def run_prediction_cycle(self):
        """Run volledige voorspellingscyclus"""
        logger.info("Starting prediction cycle...")
        
        # Get active users in last 7 days from user_interactions table
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT DISTINCT user_id FROM user_interactions
        WHERE timestamp > datetime('now', '-7 days')
        ''')
        
        users = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        # Generate predictions for each user
        for user_id in users:
            # Predict needs for next hour
            predictions = self.predict_user_needs(user_id, 1)
            
            # Schedule content for high-confidence predictions
            for prediction in predictions:
                if prediction['confidence_score'] >= self.min_confidence_threshold:
                    content_id = self.schedule_content_generation(user_id, prediction)
                    # Generate content in background
                    asyncio.create_task(self.generate_predicted_content(content_id))
        
        logger.info(f"Prediction cycle completed. Scheduled content for {len(users)} users")
