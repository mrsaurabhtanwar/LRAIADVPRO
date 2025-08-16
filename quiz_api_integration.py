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
            "generate_quiz": "/api/generate-quiz",
            "generate_hint": "/api/generate-hint",
            "health": "/api/health"
        }
    
    def generate_quiz(self, topic, difficulty="medium", num_questions=5, student_data=None):
        """Generate a quiz using the external API"""
        try:
            url = f"{self.base_url}/api/generate-quiz"
            
            # Prepare request payload
            payload = {
                "topics": [topic],  # API expects topics as a list
                "difficulty": difficulty,
                "num_questions": num_questions,
                "student_features": student_data or self._get_default_student_data()
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
                
                # WORKAROUND: Fix API issues with duplicate questions and wrong count
                if 'questions' in quiz_data:
                    questions = quiz_data['questions']
                    
                    # Remove duplicate questions by question text
                    seen_questions = set()
                    unique_questions = []
                    
                    for q in questions:
                        question_text = q.get('question', '')
                        if question_text and question_text not in seen_questions:
                            seen_questions.add(question_text)
                            unique_questions.append(q)
                    
                    # Limit to requested number of questions
                    if len(unique_questions) > num_questions:
                        unique_questions = unique_questions[:num_questions]
                    
                    # Update the quiz data
                    quiz_data['questions'] = unique_questions
                    quiz_data['total_questions'] = len(unique_questions)
                    
                    # Log the fix
                    original_count = len(questions)
                    final_count = len(unique_questions)
                    if current_app:
                        current_app.logger.info(f"Quiz API workaround: {original_count} -> {final_count} questions (requested: {num_questions})")
                
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
            url = f"{self.base_url}/api/generate-hint"
            
            payload = {
                "question_text": question_text,
                "current_topic": current_topic,
                "hint_level": hint_level,
                "student_behavior": student_data or self._get_default_student_data()
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
            response = requests.get(f"{self.base_url}/api/health", timeout=10)
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
            dict: Student behavioral analysis data
        """
        try:
            # Extract data from quiz attempt
            responses = json.loads(getattr(quiz_attempt, 'responses_json', None) or '{}')
            timing_data = json.loads(getattr(quiz_attempt, 'timing_data_json', None) or '{}')
            
            # Convert to string format as expected by API
            behavioral_data = {
                "hint_count": str(getattr(quiz_attempt, 'hints_used', 0)),
                "bottom_hint": str(getattr(quiz_attempt, 'reached_final_hint', False)).lower(),
                "attempt_count": str(getattr(quiz_attempt, 'attempt_number', 1)),
                "ms_first_response": str(getattr(quiz_attempt, 'time_to_first_answer', 5000) * 1000),
                "duration": str((getattr(quiz_attempt, 'time_taken', None) or 300) * 1000),  # Convert to milliseconds
                "confidence_frustrated": "0.1",  # Default values - could be calculated from responses
                "confidence_confused": "0.3",
                "confidence_concentrating": "0.5",
                "confidence_bored": "0.1",
                "action_count": str(len(responses)),
                "hint_dependency": str(min(getattr(quiz_attempt, 'hints_used', 0) / max(len(responses), 1), 1.0)),
                "response_speed": str(max(0.1, min(1.0, 60000 / max(getattr(quiz_attempt, 'time_taken', None) or 60, 1)))),
                "confidence_balance": "0.6",
                "engagement_ratio": str(max(0.1, min(1.0, len(responses) / max(getattr(quiz_attempt, 'total_questions', 10), 1)))),
                "efficiency_indicator": "0.7"
            }
            
            return behavioral_data
            
        except Exception as e:
            error_msg = f"Error analyzing student behavior: {e}"
            if current_app:
                current_app.logger.error(error_msg)
            else:
                print(f"Error: {error_msg}")
            return self._get_default_student_data()

    def _get_default_student_data(self):
        """Get default student behavioral data for API requests"""
        return {
            "hint_count": "0",
            "bottom_hint": "false",
            "attempt_count": "1",
            "ms_first_response": "5000",
            "duration": "30000",
            "confidence_frustrated": "0.1",
            "confidence_confused": "0.3",
            "confidence_concentrating": "0.5",
            "confidence_bored": "0.1",
            "action_count": "10",
            "hint_dependency": "0.2",
            "response_speed": "0.7",
            "confidence_balance": "0.6",
            "engagement_ratio": "0.8",
            "efficiency_indicator": "0.7"
        }


# Create global instance
quiz_api = QuizGenerationAPI()
