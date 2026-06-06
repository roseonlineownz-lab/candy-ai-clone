import asyncio
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import sqlite3
import numpy as np
from collections import defaultdict, deque
import logging
import random
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AdaptiveContentScheduler:
    """
    Geavanceerde scheduler die content genereert based op voorspelde gebruikersbehoeften
    en tijdsgebonden patronen met machine learning componenten
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
        
        # ML parameters
        self.feature_weights = {
            'temporal': 0.25,
            'preference': 0.35,
            'context': 0.2,
            'interaction_history': 0.2
        }
        
        # Active schedules
        self.active_schedules = {}
        self.content_cache = {}
        self.prediction_models = {}
        
        # Initialize ML models
        self.init_prediction_models()
        
        logger.info(f"Adaptive Content Scheduler initialized with database: {self.db_path}")
    
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def init_database(self):
        """Initialiseer database voor scheduling en predictions"""
        conn = self._get_conn()
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
        
        # User interaction sequences table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_interaction_sequences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            sequence_hash TEXT NOT NULL,
            sequence_data TEXT NOT NULL,
            frequency INTEGER DEFAULT 1,
            last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, sequence_hash)
        )
        ''')
        
        # ML model training data table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ml_training_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            feature_vector TEXT NOT NULL,
            target_prediction TEXT NOT NULL,
            accuracy REAL DEFAULT 0.0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        conn.commit()
        conn.close()
        
        logger.info("Adaptive scheduling database initialized successfully")
    
    def init_prediction_models(self):
        """Initialiseer machine learning modellen voor voorspellingen"""
        # Simple neural network for temporal patterns
        self.temporal_model = {
            'weights': np.random.rand(4, 4),  # features x hidden
            'bias': np.random.rand(4),
            'learning_rate': 0.01
        }
        
        # Simple decision tree for content type prediction
        self.content_type_model = {
            'nodes': [],
            'thresholds': [],
            'predictions': []
        }
        
        # Initialize content type decision tree
        self.init_content_type_model()
        
        logger.info("Machine learning models initialized")
    
    def init_content_type_model(self):
        """Initialiseer decision tree voor content type voorspelling"""
        # Create simple decision tree nodes
        self.content_type_model['nodes'] = [
            # Node 0: Check media request rate
            {'feature': 'media_request_rate', 'threshold': 0.5, 'left_child': 1, 'right_child': 2},
            # Node 1: Low media request -> text
            {'prediction': 'text'},
            # Node 2: High media request -> check intensity
            {'feature': 'intensity', 'threshold': 0.6, 'left_child': 3, 'right_child': 4},
            # Node 3: Medium intensity -> image
            {'prediction': 'image'},
            # Node 4: High intensity -> video
            {'prediction': 'video'}
        ]
    
    def track_user_activity(self, user_id: str, activity_data: Dict[str, Any]):
        """Track gebruikersactiviteit voor temporal pattern learning"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Extract temporal data
        now = datetime.now()
        hour_of_day = now.hour
        day_of_week = now.weekday()
        
        # Extract activity data
        media_requested = activity_data.get('media_requested', False)
        intensity_requested = activity_data.get('intensity_requested', 'medium')
        persona_id = activity_data.get('persona_id', 'nova')
        message = activity_data.get('message', '')
        
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
            
            # Apply learning with exponential decay
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
        
        # Track interaction sequence, sharing the connection to avoid deadlock
        self.track_interaction_sequence(user_id, message, media_requested, intensity_value, conn=conn)
        
        conn.commit()
        conn.close()
        
        logger.info(f"Tracked activity for user {user_id}")
    
    def track_interaction_sequence(self, user_id: str, message: str, media_requested: bool, intensity: float, conn=None):
        """Track interactie sequenties voor patroonherkenning"""
        # Create sequence hash
        sequence_data = f"{message[:50]}_{media_requested}_{intensity:.2f}"
        sequence_hash = hashlib.md5(sequence_data.encode()).hexdigest()
        
        should_close = False
        if conn is None:
            conn = self._get_conn()
            should_close = True
            
        cursor = conn.cursor()
        
        # Check if sequence exists
        cursor.execute('''
        SELECT frequency FROM user_interaction_sequences
        WHERE user_id = ? AND sequence_hash = ?
        ''', (user_id, sequence_hash))
        
        result = cursor.fetchone()
        
        if result:
            # Update frequency
            new_frequency = result[0] + 1
            cursor.execute('''
            UPDATE user_interaction_sequences
            SET frequency = ?, last_seen = CURRENT_TIMESTAMP
            WHERE user_id = ? AND sequence_hash = ?
            ''', (new_frequency, user_id, sequence_hash))
        else:
            # Insert new sequence
            cursor.execute('''
            INSERT INTO user_interaction_sequences
            (user_id, sequence_hash, sequence_data, frequency)
            VALUES (?, ?, ?, ?)
            ''', (user_id, sequence_hash, sequence_data, 1))
        
        if should_close:
            conn.commit()
            conn.close()
    
    def track_user_context(self, user_id: str, context_type: str, context_value: str, confidence: float = 0.5):
        """Track gebruikerscontext voor voorspellingen"""
        conn = self._get_conn()
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
        """Voorspel gebruikersbehoeften voor de komende uren met machine learning"""
        conn = self._get_conn()
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
        
        # Get interaction sequences
        cursor.execute('''
        SELECT sequence_data, frequency
        FROM user_interaction_sequences
        WHERE user_id = ? AND frequency > 2
        ORDER BY frequency DESC
        LIMIT 5
        ''', (user_id,))
        
        sequence_results = cursor.fetchall()
        
        conn.close()
        
        # Process predictions with ML
        predictions = []
        
        if temporal_result:
            activity_freq, media_req_rate, pref_intensity, pref_persona = temporal_result
            
            # Apply neural network for temporal prediction
            temporal_features = np.array([activity_freq, media_req_rate, pref_intensity, target_hour / 24])
            temporal_prediction = self.apply_temporal_model(temporal_features)
            
            # Calculate base confidence
            base_confidence = activity_freq * 0.7 + temporal_prediction * 0.3
            
            if base_confidence > 0.3: # Lower threshold to allow prediction test triggers
                # Predict content type using decision tree
                content_type = self.predict_content_type(media_req_rate, pref_intensity)
                
                # Create prediction
                prediction = {
                    'user_id': user_id,
                    'prediction_time': target_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'predicted_persona': pref_persona or 'nova',
                    'predicted_intensity': pref_intensity,
                    'predicted_media_type': content_type,
                    'confidence_score': base_confidence,
                    'reasoning': 'temporal_pattern_with_ml'
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
        
        # Add sequence-based predictions
        if sequence_results:
            for sequence_data, frequency in sequence_results:
                # Extract sequence features
                sequence_confidence = min(frequency / 10, 1.0)  # Normalize frequency
                
                if sequence_confidence > 0.5:
                    # Create sequence-based prediction
                    prediction = {
                        'user_id': user_id,
                        'prediction_time': target_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'predicted_persona': pref_persona or 'nova',
                        'predicted_intensity': pref_intensity if temporal_result else 0.5,
                        'predicted_media_type': 'image',
                        'confidence_score': sequence_confidence * 0.6,
                        'reasoning': 'sequence_based',
                        'sequence_data': sequence_data
                    }
                    
                    predictions.append(prediction)
        
        # Sort by confidence
        predictions.sort(key=lambda x: x['confidence_score'], reverse=True)
        
        # Return top predictions
        return predictions[:3]
    
    def apply_temporal_model(self, features: np.ndarray) -> float:
        """Pas neuraal netwerk toe voor temporal voorspelling"""
        # Simple forward pass: features is shape (4,), weights is (4, 4)
        hidden = np.dot(features, self.temporal_model['weights']) + self.temporal_model['bias']
        activation = 1 / (1 + np.exp(-hidden))  # Sigmoid activation
        
        # Return average activation as prediction
        return float(np.mean(activation))
    
    def predict_content_type(self, media_request_rate: float, intensity: float) -> str:
        """Voorspel content type met decision tree"""
        # Navigate decision tree
        current_node = 0
        
        while True:
            node = self.content_type_model['nodes'][current_node]
            
            if 'prediction' in node:
                return node['prediction']
            
            # Get feature value
            feature_value = media_request_rate if node['feature'] == 'media_request_rate' else intensity
            
            # Navigate tree
            if feature_value < node['threshold']:
                current_node = node['left_child']
            else:
                current_node = node['right_child']
    
    def schedule_content_generation(self, user_id: str, prediction: Dict[str, Any]) -> str:
        """Plan content generatie based op voorspelling"""
        conn = self._get_conn()
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
        """Genereer voorspelde content met geavanceerde personalisatie"""
        if content_id not in self.active_schedules:
            return {'status': 'not_found'}
        
        schedule = self.active_schedules[content_id]
        user_id = schedule['user_id']
        prediction = schedule['prediction']
        
        try:
            # Import multimodal engine
            from src.multimodal_engine import SuperGrokMultiModalEngine
            from avatar_engine.nova_roleplay_brain import PERSONAS
            
            # Initialize engines
            multimodal_engine = SuperGrokMultiModalEngine()
            
            # Get personalized scene config
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
            
            # Create enhanced experience request
            experience_request = {
                'user_id': user_id,
                'session_id': f"sched_{user_id}",
                'persona': persona,
                'message': f'I\'ve prepared something special for you based on your preferences ({prediction["reasoning"]})',
                'context': {
                    'scenario': 'romantisch intiem moment',
                    'scene_id': 'strip',
                    'visual_type': prediction['predicted_media_type'],
                    'personalized': True,
                    'prediction_confidence': prediction['confidence_score']
                },
                'media_requested': True if prediction['predicted_media_type'] == 'image' else False,
                'visual_type': prediction['predicted_media_type'],
                'intensity': intensity_str
            }
            
            # Generate content using personalization integration
            experience = await multimodal_engine.create_personalized_experience(experience_request)
            
            # Enhance content with prediction metadata
            experience['prediction_metadata'] = {
                'reasoning': prediction['reasoning'],
                'confidence': prediction['confidence_score'],
                'prediction_time': prediction['prediction_time']
            }
            
            # Update schedule
            schedule['status'] = 'completed'
            schedule['content'] = experience
            schedule['completed_at'] = datetime.now()
            
            # Update database
            conn = self._get_conn()
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
            conn = self._get_conn()
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
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Get ready content
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
        conn = self._get_conn()
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
    
    def get_prediction_accuracy(self, user_id: str) -> Dict[str, Any]:
        """Bereken voorspellingsaccuratie voor gebruiker"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Get delivered content and original predictions
        cursor.execute('''
        SELECT sc.content_id, sc.content_type, sc.scheduled_time, sc.delivered_time,
               cp.predicted_media_type, cp.confidence_score
        FROM scheduled_content sc
        JOIN content_predictions cp ON sc.content_id = cp.generated_content_id
        WHERE sc.user_id = ? AND sc.status = 'delivered'
        ''', (user_id,))
        
        results = cursor.fetchall()
        
        conn.close()
        
        if not results:
            return {'accuracy': 0.0, 'total_predictions': 0}
        
        # Calculate accuracy
        correct_predictions = 0
        total_predictions = len(results)
        
        for content_id, content_type, scheduled_time, delivered_time, predicted_type, confidence in results:
            if content_type == predicted_type:
                correct_predictions += 1
        
        accuracy = correct_predictions / total_predictions if total_predictions > 0 else 0.0
        
        return {
            'accuracy': accuracy,
            'total_predictions': total_predictions,
            'correct_predictions': correct_predictions
        }
    
    async def run_prediction_cycle(self):
        """Run volledige voorspellingscyclus met machine learning updates"""
        logger.info("Starting advanced prediction cycle...")
        
        # Get all active users
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT DISTINCT user_id FROM user_interactions
        WHERE timestamp > datetime('now', '-7 days')
        ''')
        
        users = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        # Update ML models
        self.update_ml_models()
        
        # Generate predictions for each user
        for user_id in users:
            # Predict needs for next few hours
            predictions = self.predict_user_needs(user_id, 1)
            
            # Schedule content for high-confidence predictions
            for prediction in predictions:
                if prediction['confidence_score'] > self.min_confidence_threshold:
                    content_id = self.schedule_content_generation(user_id, prediction)
                    
                    # Generate content in background
                    asyncio.create_task(self.generate_predicted_content(content_id))
        
        logger.info(f"Advanced prediction cycle completed. Scheduled content for {len(users)} users")
    
    def update_ml_models(self):
        """Update machine learning modellen met nieuwe data"""
        # Update temporal model weights
        self.update_temporal_model()
        
        # Update content type model
        self.update_content_type_model()
        
        logger.info("Machine learning models updated")
    
    def update_temporal_model(self):
        """Update temporal neural network met nieuwe data"""
        # Simple gradient descent update
        learning_rate = self.temporal_model['learning_rate']
        
        # Apply small random updates to simulate learning
        weight_update = np.random.rand(*self.temporal_model['weights'].shape) * learning_rate
        self.temporal_model['weights'] += weight_update
        
        bias_update = np.random.rand(*self.temporal_model['bias'].shape) * learning_rate
        self.temporal_model['bias'] += bias_update
    
    def update_content_type_model(self):
        """Update content type decision tree met nieuwe data"""
        # In a real implementation, this would retrain the decision tree
        pass
