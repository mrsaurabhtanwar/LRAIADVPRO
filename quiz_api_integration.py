"""
Quiz Generation API Integration Module
Handles quiz generation, hints, and student behavior analysis
"""

import requests
import json
try:
    from flask import current_app
except ImportError:
    current_app = None


class QuizGenerationAPI:
    """Integration class for the Quiz Generation API"""
    
    def __init__(self, base_url="https://rag-tutor-quiz-generator.onrender.com"):
        self.base_url = base_url
        self.endpoints = {
            "generate_quiz": "/generate-quiz",  # Updated endpoint path
            "generate_hint": "/generate-hint",  # Updated endpoint path  
            "health": "/health"  # Updated endpoint path
        }
    
    def generate_quiz(self, topic, difficulty="medium", num_questions=10, student_data=None):
        """Generate a quiz using the external API"""
        try:
            url = f"{self.base_url}/generate-quiz"
            
            # Get student behavior data
            behavior_data = student_data or self._get_default_student_behavior()
            
            # Prepare request payload according to new API schema
            payload = {
                "context_refs": [],  # Empty for now, can be populated later
                "topics": [topic] if isinstance(topic, str) else topic,
                "difficulty": difficulty,
                "type": "mcq",  # Multiple choice questions
                "n_questions": num_questions,
                "include_explanations": True,
                "include_resources": True,
                "student_behavior": behavior_data
            }
            
            # Make API request
            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60
            )
            
            if response.status_code == 200:
                quiz_data = response.json()
                
                # Process the response (assuming the new API returns cleaner data)
                if 'questions' in quiz_data:
                    questions = quiz_data['questions']
                    
                    # Ensure we have the right number of questions
                    if len(questions) > num_questions:
                        questions = questions[:num_questions]
                    
                    # Update the quiz data
                    quiz_data['questions'] = questions
                    quiz_data['total_questions'] = len(questions)
                    
                    if current_app:
                        current_app.logger.info(f"Quiz generated successfully: {len(questions)} questions for topic '{topic}'")
                
                return {
                    "success": True,
                    "quiz": quiz_data,
                    "message": "Quiz generated successfully"
                }
            else:
                error_msg = f"Quiz API error {response.status_code}: {response.text}"
                if current_app:
                    current_app.logger.error(error_msg)
                else:
                    print(f"Error: {error_msg}")
                return {
                    "success": False,
                    "error": f"API returned status {response.status_code}",
                    "message": "Failed to generate quiz. Please try again."
                }
                
        except Exception as e:
            error_msg = f"Quiz generation error: {e}"
            if current_app:
                current_app.logger.error(error_msg)
            else:
                print(f"Error: {error_msg}")
            return {
                "success": False,
                "error": "unexpected_error",
                "message": "An unexpected error occurred. Please try again."
            }
    
    def generate_hint(self, question_text, student_data=None, hint_level=1, current_topic="General Knowledge"):
        """Generate a personalized hint for a quiz question"""
        try:
            url = f"{self.base_url}/generate-hint"
            
            payload = {
                "question_text": question_text,
                "current_topic": current_topic,
                "hint_level": hint_level,
                "student_behavior": student_data or self._get_default_student_behavior()
            }
            
            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                hint_data = response.json()
                return {
                    "success": True,
                    "hint": hint_data.get("hint", "Try thinking about the key concepts in the question."),
                    "hint_level": hint_level,
                    "message": "Hint generated successfully"
                }
            else:
                error_msg = f"Hint API returned status {response.status_code}: {response.text}"
                if current_app:
                    current_app.logger.warning(error_msg)
                else:
                    print(f"Warning: {error_msg}")
                return {
                    "success": False,
                    "hint": "Think about what the question is really asking. Break it down into smaller parts.",
                    "message": "Using fallback hint"
                }
                
        except Exception as e:
            error_msg = f"Hint generation error: {e}"
            if current_app:
                current_app.logger.error(error_msg)
            else:
                print(f"Error: {error_msg}")
            return {
                "success": False,
                "hint": "Take your time and read the question carefully. What key information do you need?",
                "message": "Using fallback hint due to error"
            }
    
    def check_api_health(self):
        """Check if the Quiz Generation API is healthy"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)
            if response.status_code == 200:
                health_data = response.json()
                return {
                    "healthy": True,
                    "status": health_data.get("status", "unknown"),
                    "api_keys_available": health_data.get("api_keys_available", {}),
                    "message": "API is healthy"
                }
            else:
                return {"healthy": False, "error": f"Status {response.status_code}"}
        except Exception as e:
            return {"healthy": False, "error": str(e)}
    
    def analyze_student_behavior(self, quiz_attempt):
        """
        Analyze student behavior from quiz attempt data
        
        Args:
            quiz_attempt: QuizAttempt model instance
            
        Returns:
            dict: Student behavioral analysis data formatted for new API
        """
        try:
            # Extract data from quiz attempt
            responses = json.loads(getattr(quiz_attempt, 'responses_json', None) or '{}')
            timing_data = json.loads(getattr(quiz_attempt, 'timing_data_json', None) or '{}')
            
            # Calculate behavioral metrics for new API format
            behavioral_data = {
                "hint_count": getattr(quiz_attempt, 'hints_used', 0),
                "bottom_hint": getattr(quiz_attempt, 'reached_final_hint', False),
                "attempt_count": getattr(quiz_attempt, 'attempt_number', 1),
                "ms_first_response": getattr(quiz_attempt, 'time_to_first_answer', 5000),
                "duration": (getattr(quiz_attempt, 'time_taken', None) or 300) * 1000,  # Convert to milliseconds
                "confidence_frustrated": round(getattr(quiz_attempt, 'confidence_frustrated', 0.1), 2),
                "confidence_confused": round(getattr(quiz_attempt, 'confidence_confused', 0.3), 2),
                "confidence_concentrating": round(getattr(quiz_attempt, 'confidence_concentrating', 0.5), 2),
                "confidence_bored": round(getattr(quiz_attempt, 'confidence_bored', 0.1), 2),
                "action_count": len(responses),
                "hint_dependency": round(min(getattr(quiz_attempt, 'hints_used', 0) / max(len(responses), 1), 1.0), 2),
                "response_speed": "medium",  # Can be "fast", "medium", "slow"
                "confidence_balance": round(getattr(quiz_attempt, 'average_confidence', 0.6), 2),
                "engagement_ratio": round(max(0.1, min(1.0, len(responses) / max(getattr(quiz_attempt, 'total_questions', 10), 1))), 2),
                "efficiency_indicator": round(getattr(quiz_attempt, 'efficiency_score', 0.7), 2),
                "predicted_score": round(getattr(quiz_attempt, 'score', 0) / 100, 2),  # Convert to 0-1 scale
                "performance_category": self._get_performance_category(getattr(quiz_attempt, 'score', 0)),
                "learner_profile": self._get_learner_profile(quiz_attempt)
            }
            
            return behavioral_data
            
        except Exception as e:
            error_msg = f"Error analyzing student behavior: {e}"
            if current_app:
                current_app.logger.error(error_msg)
            else:
                print(f"Error: {error_msg}")
            return self._get_default_student_behavior()

    def _get_performance_category(self, score):
        """Determine performance category based on score"""
        if score >= 85:
            return "excellent"
        elif score >= 70:
            return "good"
        elif score >= 60:
            return "average"
        elif score >= 40:
            return "struggling"
        else:
            return "needs_help"

    def _get_learner_profile(self, quiz_attempt):
        """Determine learner profile based on attempt data"""
        hints_used = getattr(quiz_attempt, 'hints_used', 0)
        time_taken = getattr(quiz_attempt, 'time_taken', None) or 300
        score = getattr(quiz_attempt, 'score', 0)
        
        if hints_used > 3 and time_taken > 600:
            return "methodical_learner"
        elif hints_used == 0 and time_taken < 180:
            return "quick_learner"
        elif score >= 80 and hints_used <= 1:
            return "confident_learner"
        elif hints_used > 2 and score < 60:
            return "struggling_learner"
        else:
            return "balanced_learner"

    def _get_default_student_behavior(self):
        """Get default student behavioral data for API requests (new format)"""
        return {
            "hint_count": 0,
            "bottom_hint": False,
            "attempt_count": 1,
            "ms_first_response": 5000,
            "duration": 300000,  # 5 minutes in milliseconds
            "confidence_frustrated": 0.1,
            "confidence_confused": 0.3,
            "confidence_concentrating": 0.5,
            "confidence_bored": 0.1,
            "action_count": 10,
            "hint_dependency": 0.2,
            "response_speed": "medium",
            "confidence_balance": 0.6,
            "engagement_ratio": 0.8,
            "efficiency_indicator": 0.7,
            "predicted_score": 0.75,
            "performance_category": "good",
            "learner_profile": "balanced_learner"
        }


# Create global instance
quiz_api = QuizGenerationAPI()
