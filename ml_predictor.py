import pandas as pd
import pickle
import numpy as np
from datetime import datetime, timedelta
import logging

class LearningAnalytics:
    def __init__(self, model_path='student_model.pkl'):
        """Initialize the ML predictor with trained model"""
        self.model_path = model_path
        self.model = None
        self.load_model()
        
    def load_model(self):
        """Load the pre-trained ML model"""
        try:
            with open(self.model_path, 'rb') as f:
                self.model = pickle.load(f)
            logging.info("ML model loaded successfully")
        except FileNotFoundError:
            logging.error(f"Model file not found: {self.model_path}")
        except Exception as e:
            logging.error(f"Error loading model: {str(e)}")
    
    def extract_features_from_attempt(self, quiz_attempt):
        """
        Extract the 15 features from a quiz attempt as shown in your diagram
        """
        features = {}
        
        # Basic metrics
        features['hint_count'] = quiz_attempt.hints_used or 0
        features['bottom_hint'] = 1 if quiz_attempt.reached_final_hint else 0
        features['attempt_count'] = quiz_attempt.attempt_number or 1
        
        # Time-based features
        if quiz_attempt.started_at and quiz_attempt.completed_at:
            duration = (quiz_attempt.completed_at - quiz_attempt.started_at).total_seconds()
            features['duration'] = duration
            features['ms_first_response'] = quiz_attempt.time_to_first_answer or duration
        else:
            features['duration'] = 0
            features['ms_first_response'] = 0
        
        # Performance metrics
        features['score'] = quiz_attempt.score or 0
        features['average_confidence'] = quiz_attempt.average_confidence or 0.5
        
        # Efficiency calculation
        if features['duration'] > 0:
            features['efficiency_indicator'] = features['score'] / features['duration']
        else:
            features['efficiency_indicator'] = 0
            
        # Historical performance features
        student_history = self.get_student_history(quiz_attempt.student_id)
        features.update(student_history)
        
        return features
    
    def get_student_history(self, student_id, lookback_days=30):
        """Get historical performance features for the student"""
        from models import QuizAttempt  # Import here to avoid circular imports
        
        cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)
        
        recent_attempts = QuizAttempt.query.filter(
            QuizAttempt.student_id == student_id,
            QuizAttempt.completed_at >= cutoff_date,
            QuizAttempt.completed_at.isnot(None)
        ).all()
        
        if not recent_attempts:
            return {
                'avg_recent_score': 0,
                'consistency_score': 0,
                'improvement_trend': 0,
                'total_attempts': 0,
                'success_rate': 0,
                'avg_time_per_question': 0,
                'hint_usage_pattern': 0,
                'difficulty_preference': 0
            }
        
        scores = [attempt.score for attempt in recent_attempts if attempt.score]
        durations = [
            (attempt.completed_at - attempt.started_at).total_seconds() 
            for attempt in recent_attempts 
            if attempt.started_at and attempt.completed_at
        ]
        
        return {
            'avg_recent_score': np.mean(scores) if scores else 0,
            'consistency_score': 1 - (np.std(scores) / np.mean(scores)) if scores and np.mean(scores) > 0 else 0,
            'improvement_trend': self.calculate_trend(scores),
            'total_attempts': len(recent_attempts),
            'success_rate': len([s for s in scores if s >= 60]) / len(scores) if scores else 0,
            'avg_time_per_question': np.mean(durations) if durations else 0,
            'hint_usage_pattern': np.mean([a.hints_used or 0 for a in recent_attempts]),
            'difficulty_preference': self.calculate_difficulty_preference(recent_attempts)
        }
    
    def calculate_trend(self, scores):
        """Calculate improvement trend (-1 to 1)"""
        if len(scores) < 2:
            return 0
        
        # Simple linear trend
        x = np.arange(len(scores))
        slope = np.polyfit(x, scores, 1)[0]
        return max(-1, min(1, slope / 10))  # Normalize to [-1, 1]
    
    def calculate_difficulty_preference(self, attempts):
        """Calculate student's difficulty preference"""
        # This would depend on your quiz difficulty scoring
        # Placeholder implementation
        return 0.5
    
    def predict_performance(self, quiz_attempt):
        """
        Make prediction based on quiz attempt
        Returns: dict with prediction results matching your diagram
        """
        if not self.model:
            return self.get_default_prediction()
        
        try:
            # Extract features
            features = self.extract_features_from_attempt(quiz_attempt)
            
            # Convert to DataFrame for model input
            feature_df = pd.DataFrame([features])
            
            # Make prediction
            predicted_score = self.model.predict(feature_df)[0]
            prediction_proba = self.model.predict_proba(feature_df)[0] if hasattr(self.model, 'predict_proba') else None
            
            # Categorize performance
            if predicted_score < 60:
                category = 'struggling'
            elif predicted_score > 85:
                category = 'advanced'
            else:
                category = 'average'
            
            # Generate learner profile
            learner_profile = self.generate_learner_profile(features)
            
            # Calculate confidence level
            confidence_level = max(prediction_proba) if prediction_proba is not None else 0.7
            
            return {
                'predicted_score': float(predicted_score),
                'category': category,
                'learner_profile': learner_profile,
                'confidence_level': float(confidence_level),
                'features_used': features
            }
            
        except Exception as e:
            logging.error(f"Prediction error: {str(e)}")
            return self.get_default_prediction()
    
    def generate_learner_profile(self, features):
        """Generate learning style indicators"""
        profile = {}
        
        # Analyze learning patterns
        if features['hint_count'] > 3:
            profile['support_needed'] = 'high'
        elif features['hint_count'] > 1:
            profile['support_needed'] = 'medium'
        else:
            profile['support_needed'] = 'low'
        
        if features['duration'] > 600:  # 10 minutes
            profile['learning_pace'] = 'deliberate'
        elif features['duration'] < 180:  # 3 minutes
            profile['learning_pace'] = 'fast'
        else:
            profile['learning_pace'] = 'moderate'
        
        if features['efficiency_indicator'] > 0.1:
            profile['problem_solving'] = 'efficient'
        else:
            profile['problem_solving'] = 'needs_practice'
        
        return profile
    
    def get_default_prediction(self):
        """Return default prediction when model fails"""
        return {
            'predicted_score': 70.0,
            'category': 'average',
            'learner_profile': {
                'support_needed': 'medium',
                'learning_pace': 'moderate',
                'problem_solving': 'average'
            },
            'confidence_level': 0.5,
            'features_used': {}
        }

class RecommendationEngine:
    """Generate personalized learning recommendations"""
    
    def __init__(self):
        self.recommendation_templates = {
            'struggling': {
                'next_quiz_difficulty': 'easy',
                'study_materials': ['basic_concepts', 'worked_examples', 'practice_problems'],
                'focus_areas': ['fundamental_understanding', 'step_by_step_solutions'],
                'hint_settings': 'generous'
            },
            'average': {
                'next_quiz_difficulty': 'medium',
                'study_materials': ['practice_problems', 'concept_review', 'application_exercises'],
                'focus_areas': ['problem_solving_speed', 'accuracy_improvement'],
                'hint_settings': 'moderate'
            },
            'advanced': {
                'next_quiz_difficulty': 'hard',
                'study_materials': ['challenge_problems', 'advanced_concepts', 'real_world_applications'],
                'focus_areas': ['complex_problem_solving', 'critical_thinking'],
                'hint_settings': 'minimal'
            }
        }
    
    def generate_recommendations(self, prediction_result, student_id):
        """Generate personalized recommendations based on prediction"""
        category = prediction_result.get('category', 'average')
        learner_profile = prediction_result.get('learner_profile', {})
        
        # Get base recommendations for category
        base_recs = self.recommendation_templates.get(category, self.recommendation_templates['average']).copy()
        
        # Customize based on learner profile
        self._customize_recommendations(base_recs, learner_profile, prediction_result)
        
        return base_recs
    
    def _customize_recommendations(self, recommendations, learner_profile, prediction_result):
        """Customize recommendations based on learner profile"""
        
        # Adjust based on learning pace
        pace = learner_profile.get('learning_pace', 'moderate')
        if pace == 'fast':
            # Add more challenging materials
            if 'challenge_problems' not in recommendations['study_materials']:
                recommendations['study_materials'].append('challenge_problems')
        elif pace == 'deliberate':
            # Add more foundational materials
            if 'step_by_step_guides' not in recommendations['study_materials']:
                recommendations['study_materials'].insert(0, 'step_by_step_guides')
        
        # Adjust based on support needed
        support = learner_profile.get('support_needed', 'medium')
        if support == 'high':
            recommendations['hint_settings'] = 'generous'
            if 'tutoring_sessions' not in recommendations['study_materials']:
                recommendations['study_materials'].append('tutoring_sessions')
        elif support == 'low':
            recommendations['hint_settings'] = 'minimal'
        
        # Adjust based on problem solving efficiency
        problem_solving = learner_profile.get('problem_solving', 'average')
        if problem_solving == 'needs_practice':
            if 'problem_solving_strategies' not in recommendations['focus_areas']:
                recommendations['focus_areas'].append('problem_solving_strategies')