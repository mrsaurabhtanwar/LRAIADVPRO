"""
Quiz Generation API Integration Module with CSV Fallback
Handles quiz generation, hints, and student behavior analysis
"""

import requests
import json
import time
import csv
import random
import os
import math
from typing import List, Dict, Any, Optional
try:
    from flask import current_app
except ImportError:
    current_app = None

class QuizGenerationAPI:
    """Integration class for the Quiz Generation API with CSV fallback"""
    
    def __init__(self, base_url="https://rag-tutor-quiz-generator.onrender.com", csv_path="quiz_questions.csv"):
        self.base_url = base_url
        self.csv_path = csv_path
        self.endpoints = {
            "generate_quiz": "/api/generate-quiz",
            "generate_hint": "/api/generate-hint",
            "health": "/health"
        }
        # Cache CSV questions
        self.cached_questions: List[Dict[str, Any]] = []
        self._load_csv_questions()
    
    def _load_csv_questions(self):
        """Load questions from CSV file into memory"""
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                self.cached_questions = [row for row in reader]
            if current_app:
                current_app.logger.info(f"Loaded {len(self.cached_questions)} questions from CSV")
        except Exception as e:
            error_msg = f"Error loading CSV questions: {e}"
            if current_app:
                current_app.logger.error(error_msg)
            else:
                print(f"Error: {error_msg}")
            self.cached_questions = []

    def _filter_questions(self, topic: str, difficulty: str, num_questions: int) -> List[Dict[str, Any]]:
        """Filter questions from CSV based on topic and difficulty"""
        # Map API difficulty levels to CSV difficulty levels
        difficulty_map = {
            "easy": "easy",
            "medium": "medium",
            "hard": "hard"
        }
        
        # Map topics to class levels (assuming topics are related to grade levels)
        try:
            # Try to extract grade level from topic
            grade_level = None
            topic_lower = topic.lower()
            if "grade" in topic_lower:
                grade_level = next((str(i) for i in range(1, 13) if str(i) in topic_lower), None)
            elif "class" in topic_lower:
                grade_level = next((str(i) for i in range(1, 13) if str(i) in topic_lower), None)
            
            # Filter questions
            filtered_questions = []
            for question in self.cached_questions:
                matches_class = True
                if grade_level:
                    matches_class = question['class'] == grade_level
                
                matches_difficulty = question['difficulty'] == difficulty_map.get(difficulty, 'medium')
                
                if matches_class and matches_difficulty:
                    filtered_questions.append(question)
            
            # If we don't have enough questions, relax the difficulty constraint
            if len(filtered_questions) < num_questions:
                filtered_questions = [q for q in self.cached_questions if grade_level is None or q['class'] == grade_level]
            
            # Randomly select required number of questions
            if filtered_questions:
                return random.sample(filtered_questions, min(num_questions, len(filtered_questions)))
            else:
                # If no matching questions found, return random questions
                return random.sample(self.cached_questions, min(num_questions, len(self.cached_questions)))
                
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error filtering questions: {e}")
            else:
                print(f"Error filtering questions: {e}")
            # Return random questions as fallback
            return random.sample(self.cached_questions, min(num_questions, len(self.cached_questions)))

    def _format_questions_for_api(self, questions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Format CSV questions to match API response format"""
        formatted_questions = []
        for question in questions:
            formatted_question = {
                "id": f"csv_{hash(question['question'])}",
                "text": question['question'].strip(),
                "question": question['question'].strip(),  # Add formatted question field
                "options": [
                    {"id": "A", "text": question['option_A'].strip()},
                    {"id": "B", "text": question['option_B'].strip()},
                    {"id": "C", "text": question['option_C'].strip()},
                    {"id": "D", "text": question['option_D'].strip()}
                ],
                "correct_answer": question['answer'],
                "difficulty": question['difficulty'],
                "topic": f"Class {question['class']}",
                "explanation": "This question is from our local question bank.",
                "resources": [],
                "type": "mcq"
            }
            formatted_questions.append(formatted_question)
        
        return {
            "quiz_id": f"csv_{int(time.time())}",
            "questions": formatted_questions,
            "total_questions": len(formatted_questions),
            "topic": f"Class {questions[0]['class']}" if questions else "General",
            "difficulty": questions[0]['difficulty'] if questions else "medium",
            "created_at": int(time.time()),
            "source": "csv_fallback"
        }

    def generate_quiz(self, topic, difficulty="medium", num_questions=10, student_data=None):
        """Generate a quiz using the external API with CSV fallback"""
        max_retries = 3
        base_timeout = 60
        
        for attempt in range(max_retries):
            try:
                url = f"{self.base_url}/api/generate-quiz"
                
                behavior_data = student_data or self._get_default_student_behavior()
                
                payload = {
                    "context_refs": [],
                    "topics": [topic] if isinstance(topic, str) else topic,
                    "difficulty": difficulty,
                    "type": "mcq",
                    "n_questions": num_questions,
                    "include_explanations": True,
                    "include_resources": True,
                    "student_behavior": behavior_data
                }
                
                timeout = base_timeout * (attempt + 1)
                
                if current_app:
                    current_app.logger.info(f"Quiz generation attempt {attempt + 1}/{max_retries} for topic '{topic}'")
                
                response = requests.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=timeout
                )

                if response.status_code == 200:
                    quiz_data = response.json()
                    
                    if 'questions' in quiz_data:
                        questions = quiz_data['questions']
                        if len(questions) > num_questions:
                            questions = questions[:num_questions]
                        quiz_data['questions'] = questions
                        quiz_data['total_questions'] = len(questions)
                    
                    return {
                        "success": True,
                        "quiz": quiz_data,
                        "message": "Quiz generated successfully using API"
                    }
            
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, Exception) as e:
                if attempt < max_retries - 1:
                    if current_app:
                        current_app.logger.warning(f"Error on attempt {attempt + 1}: {e}, retrying...")
                    time.sleep(3)
                    continue
                
                # If all retries failed, use CSV fallback
                if current_app:
                    current_app.logger.info("Using CSV fallback for quiz generation")
                
                fallback_questions = self._filter_questions(topic, difficulty, num_questions)
                if fallback_questions:
                    quiz_data = self._format_questions_for_api(fallback_questions)
                    return {
                        "success": True,
                        "quiz": quiz_data,
                        "message": "Quiz generated successfully using local question bank",
                        "fallback": True
                    }
                else:
                    return {
                        "success": False,
                        "error": "no_questions_available",
                        "message": "Could not generate quiz. No questions available."
                    }
        
        # This shouldn't be reached, but just in case use CSV fallback
        fallback_questions = self._filter_questions(topic, difficulty, num_questions)
        if fallback_questions:
            quiz_data = self._format_questions_for_api(fallback_questions)
            return {
                "success": True,
                "quiz": quiz_data,
                "message": "Quiz generated successfully using local question bank",
                "fallback": True
            }
        else:
            return {
                "success": False,
                "error": "no_questions_available",
                "message": "Could not generate quiz. No questions available."
            }
    
    def generate_hint(self, question_text, student_data=None, hint_level=1, current_topic="General Knowledge"):
        """Generate a personalized hint for a quiz question with simple fallback"""
        try:
            url = f"{self.base_url}/api/generate-hint"
            
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
                timeout=60
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
                return self._generate_fallback_hint(hint_level)
                
        except Exception as e:
            return self._generate_fallback_hint(hint_level)
    
    def _generate_fallback_hint(self, hint_level):
        """Generate a simple fallback hint based on hint level"""
        hints = {
            1: "Take your time to read the question carefully. What is it asking for?",
            2: "Break down the problem into smaller parts. Which part should you solve first?",
            3: "Think about similar problems you've solved before. What techniques did you use?",
            4: "Review the key terms and concepts in the question. How do they relate to each other?",
            5: "Consider all the information given. Have you used everything important?"
        }
        return {
            "success": False,
            "hint": hints.get(hint_level, hints[1]),
            "hint_level": hint_level,
            "message": "Using fallback hint system"
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
                    "message": "API is healthy",
                    "fallback_available": bool(self.cached_questions)
                }
            else:
                return {
                    "healthy": False,
                    "error": f"Status {response.status_code}",
                    "fallback_available": bool(self.cached_questions)
                }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "fallback_available": bool(self.cached_questions)
            }
    
    def analyze_student_behavior(self, quiz_attempt):
        """Analyze student behavior from quiz attempt data"""
        try:
            responses = json.loads(getattr(quiz_attempt, 'responses_json', None) or '{}')
            timing_data = json.loads(getattr(quiz_attempt, 'timing_data_json', None) or '{}')
            
            behavioral_data = {
                "hint_count": getattr(quiz_attempt, 'hints_used', 0),
                "bottom_hint": getattr(quiz_attempt, 'reached_final_hint', False),
                "attempt_count": getattr(quiz_attempt, 'attempt_number', 1),
                "ms_first_response": int(getattr(quiz_attempt, 'time_to_first_answer', 5000)),
                "duration": int((getattr(quiz_attempt, 'time_taken', None) or 300) * 1000),
                "confidence_frustrated": round(getattr(quiz_attempt, 'confidence_frustrated', 0.1), 2),
                "confidence_confused": round(getattr(quiz_attempt, 'confidence_confused', 0.3), 2),
                "confidence_concentrating": round(getattr(quiz_attempt, 'confidence_concentrating', 0.5), 2),
                "confidence_bored": round(getattr(quiz_attempt, 'confidence_bored', 0.1), 2),
                "action_count": len(responses),
                "hint_dependency": round(min(getattr(quiz_attempt, 'hints_used', 0) / max(len(responses), 1), 1.0), 2),
                "response_speed": "medium",
                "confidence_balance": round(getattr(quiz_attempt, 'average_confidence', 0.6), 2),
                "engagement_ratio": round(max(0.1, min(1.0, len(responses) / max(getattr(quiz_attempt, 'total_questions', 10), 1))), 2),
                "efficiency_indicator": round(getattr(quiz_attempt, 'efficiency_score', 0.7), 2),
                "predicted_score": round(getattr(quiz_attempt, 'score', 0) / 100, 2),
                "performance_category": self._get_performance_category(getattr(quiz_attempt, 'score', 0)),
                "learner_profile": self._get_learner_profile(quiz_attempt)
            }
            
            return behavioral_data
            
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error analyzing student behavior: {e}")
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
        """Get default student behavioral data for API requests"""
        return {
            "hint_count": 0,
            "bottom_hint": False,
            "attempt_count": 1,
            "ms_first_response": 5000,
            "duration": 300000,
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
