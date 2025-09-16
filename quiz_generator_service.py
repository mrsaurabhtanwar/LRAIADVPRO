# quiz_generator_service.py - Quiz Generator API Integration Service

import requests
import time
import json
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

class QuizGeneratorService:
    """Enhanced service to communicate with the Quiz Generator API"""
    
    def __init__(self, api_url: str = "https://rag-tutor-quiz-generator-6a40.onrender.com"):
        self.api_url = api_url.rstrip('/')
        self.cache = {}
        self.cache_duration = 1800  # 30 minutes for quiz questions
        self.last_request = 0
        self.rate_limit_delay = 0.5  # 0.5 seconds between requests
        self.timeout = 30  # 30 seconds timeout
        self.retry_attempts = 3
        self.retry_delay = 1
        self.metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'cache_hits': 0,
            'csv_questions': 0,
            'ai_questions': 0,
            'average_response_time': 0
        }
        
        # Known subjects for instant CSV responses
        self.csv_subjects = {
            'mathematics', 'math', 'physics', 'chemistry', 'biology',
            'computer science', 'cs', 'artificial intelligence', 'ai',
            'data science', 'astronomy', 'cybersecurity', 'english',
            'quantum physics', 'robotics'
        }
    
    def get_available_topics(self) -> Dict[str, Any]:
        """Get available topics from the API"""
        try:
            response = requests.get(f"{self.api_url}/api/topics", timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to get topics: {response.status_code}")
                return {"topics": [], "error": f"API returned {response.status_code}"}
        except requests.exceptions.ConnectionError:
            logger.warning("Cannot connect to quiz generator API for topics")
            return {
                "topics": ["Mathematics", "Physics", "Chemistry", "Biology", "Computer Science"],
                "error": "Connection error - using default topics"
            }
        except Exception as e:
            logger.error(f"Error getting topics: {e}")
            return {"topics": [], "error": str(e)}

    def generate_quiz(self, topics: List[str], difficulty: str = "medium", 
                     n_questions: int = 5, question_type: str = "mcq",
                     include_explanations: bool = True,
                     student_behavior: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate quiz questions using the Quiz Generator API
        
        Args:
            topics: List of subject topics
            difficulty: Question difficulty (easy, medium, hard)
            n_questions: Number of questions to generate
            question_type: Type of questions (mcq, short)
            include_explanations: Whether to include explanations
            student_behavior: Optional student behavior data for personalization
            
        Returns:
            Dict containing the generated questions or error information
        """
        self.metrics['total_requests'] += 1
        start_time = time.time()
        
        # Create cache key
        cache_key = self._create_cache_key(topics, difficulty, n_questions, question_type)
        if cache_key in self.cache:
            cached_time, response = self.cache[cache_key]
            if time.time() - cached_time < self.cache_duration:
                logger.info(f"Returning cached quiz for topics: {topics}")
                self.metrics['cache_hits'] += 1
                return response
        
        # Rate limiting
        time_since_last = time.time() - self.last_request
        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            logger.info(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
        
        # Optimize topics for faster responses
        optimized_topics = self._optimize_topics(topics)
        
        # Retry logic with exponential backoff
        for attempt in range(self.retry_attempts):
            try:
                # Prepare request payload
                payload = {
                    "topics": optimized_topics,
                    "difficulty": difficulty,
                    "n_questions": n_questions,
                    "type": question_type,
                    "include_explanations": include_explanations
                }
                
                # Add student behavior if provided (convert to required format)
                if student_behavior:
                    # Convert our format to the API's expected format
                    api_behavior = {
                        "hint_count": student_behavior.get("hint_count", 2.0),
                        "bottom_hint": student_behavior.get("bottom_hint", 1.0),
                        "attempt_count": student_behavior.get("attempt_count", 3.0),
                        "ms_first_response": student_behavior.get("ms_first_response", 5000.0),
                        "duration": student_behavior.get("duration", 1200.0),
                        "action_count": student_behavior.get("action_count", 5.0),
                        "hint_dependency": student_behavior.get("hint_dependency", 0.3),
                        "response_speed": student_behavior.get("response_speed", "medium"),
                        "efficiency_indicator": student_behavior.get("efficiency_indicator", 0.6),
                        "confidence_balance": student_behavior.get("confidence_balance", 0.5),
                        "engagement_ratio": student_behavior.get("engagement_ratio", 0.7)
                    }
                    payload["student_behavior"] = api_behavior
                
                logger.info(f"Generating quiz (attempt {attempt + 1}): {self.api_url}/api/generate-quiz")
                logger.debug(f"Payload: {payload}")
                
                response = requests.post(
                    f"{self.api_url}/api/generate-quiz",
                    json=payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=self.timeout
                )
                
                self.last_request = time.time()
                response_time = time.time() - start_time
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"Successfully generated quiz (response time: {response_time:.2f}s)")
                    
                    # Update metrics
                    self.metrics['successful_requests'] += 1
                    self._update_average_response_time(response_time)
                    
                    # Track question source
                    api_used = result.get('apiUsed', 'unknown')
                    if api_used == 'csv_fallback':
                        self.metrics['csv_questions'] += 1
                    elif api_used in ['gemini', 'openai', 'claude']:
                        self.metrics['ai_questions'] += 1
                    
                    # Validate and enhance response
                    if self._validate_quiz_response(result):
                        enhanced_result = self._enhance_quiz_response(result, topics, response_time)
                        
                        # Cache the response
                        self.cache[cache_key] = (time.time(), enhanced_result)
                        return enhanced_result
                    else:
                        logger.warning("Invalid quiz response structure")
                        self.metrics['failed_requests'] += 1
                        return {"error": "Invalid response structure from API"}
                        
                elif response.status_code == 422:
                    # Validation error
                    error_data = response.json()
                    error_msg = error_data.get('detail', 'Validation error')
                    logger.error(f"Validation error: {error_msg}")
                    self.metrics['failed_requests'] += 1
                    return {"error": f"Validation error: {error_msg}"}
                    
                elif response.status_code == 429:
                    # Rate limit exceeded
                    if attempt < self.retry_attempts - 1:
                        wait_time = self.retry_delay * (2 ** attempt)
                        logger.warning(f"Rate limit exceeded, waiting {wait_time}s before retry")
                        time.sleep(wait_time)
                        continue
                    else:
                        self.metrics['failed_requests'] += 1
                        return {"error": "Rate limit exceeded, please try again later"}
                        
                else:
                    error_msg = f"API error: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    self.metrics['failed_requests'] += 1
                    return {"error": error_msg}
                    
            except requests.exceptions.Timeout:
                if attempt < self.retry_attempts - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.warning(f"Request timeout, retrying in {wait_time}s")
                    time.sleep(wait_time)
                    continue
                else:
                    error_msg = "API timeout - service may be sleeping"
                    logger.error(error_msg)
                    self.metrics['failed_requests'] += 1
                    return {"error": error_msg}
                    
            except requests.exceptions.ConnectionError as e:
                if attempt < self.retry_attempts - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.warning(f"Connection error, retrying in {wait_time}s: {str(e)}")
                    time.sleep(wait_time)
                    continue
                else:
                    error_msg = f"Connection error: {str(e)}"
                    logger.error(error_msg)
                    self.metrics['failed_requests'] += 1
                    # Return a fallback response instead of error
                    return self._generate_fallback_quiz(topics, difficulty, n_questions, question_type, include_explanations)
                    
            except requests.exceptions.RequestException as e:
                error_msg = f"Request error: {str(e)}"
                logger.error(error_msg)
                self.metrics['failed_requests'] += 1
                return {"error": error_msg}
                
            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                logger.error(error_msg)
                self.metrics['failed_requests'] += 1
                return {"error": error_msg}
        
        return {"error": "All retry attempts failed"}
    
    def _generate_fallback_quiz(self, topics: List[str], difficulty: str, 
                               n_questions: int, question_type: str, 
                               include_explanations: bool) -> Dict[str, Any]:
        """Generate a fallback quiz when API is unavailable"""
        logger.info("Generating fallback quiz due to API unavailability")
        
        # Create simple fallback questions
        questions = []
        for i in range(min(n_questions, 5)):  # Limit to 5 questions max
            topic = topics[0] if topics else "General"
            
            if question_type == "mcq":
                question = {
                    "id": i + 1,
                    "question": f"Sample {topic} question {i + 1}?",
                    "type": "mcq",
                    "options": ["Option A", "Option B", "Option C", "Option D"],
                    "correct_answer": "Option A",
                    "answer_index": 0,
                    "difficulty": difficulty,
                    "topic": topic,
                    "explanation": f"This is a sample {topic} question for demonstration." if include_explanations else None
                }
            else:
                question = {
                    "id": i + 1,
                    "question": f"Explain {topic} concept {i + 1}.",
                    "type": "short",
                    "correct_answer": f"Sample answer for {topic} concept {i + 1}.",
                    "difficulty": difficulty,
                    "topic": topic,
                    "explanation": f"This is a sample {topic} question for demonstration." if include_explanations else None
                }
            
            questions.append(question)
        
        return {
            "quiz_id": f"fallback_{int(time.time())}",
            "questions": questions,
            "total_questions": len(questions),
            "difficulty": difficulty,
            "topics": topics,
            "videoLinks": None,
            "websiteLinks": None,
            "processingTime": 0.1,
            "apiUsed": "fallback",
            "suggestions": [
                "This is a sample quiz generated offline.",
                "The quiz generator API is currently unavailable.",
                "Please try again later for AI-generated questions."
            ],
            "metadata": {
                "is_fallback": True,
                "api_unavailable": True,
                "generated_at": datetime.now(timezone.utc).isoformat()
            }
        }
    
    def _create_cache_key(self, topics: List[str], difficulty: str, 
                         n_questions: int, question_type: str) -> str:
        """Create a cache key for the quiz request"""
        key_string = f"{sorted(topics)}|{difficulty}|{n_questions}|{question_type}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _optimize_topics(self, topics: List[str]) -> List[str]:
        """Optimize topics for faster CSV responses"""
        optimized = []
        for topic in topics:
            topic_lower = topic.lower().strip()
            
            # Check for exact matches
            if topic_lower in self.csv_subjects:
                optimized.append(topic)
                continue
            
            # Check for partial matches
            for csv_subject in self.csv_subjects:
                if topic_lower in csv_subject or csv_subject in topic_lower:
                    optimized.append(csv_subject.title())
                    break
            else:
                # No CSV match found, use original topic for AI generation
                optimized.append(topic)
        
        return optimized
    
    def _validate_quiz_response(self, response: Dict[str, Any]) -> bool:
        """Validate that the response has the expected structure"""
        if 'questions' not in response:
            return False
        
        questions = response.get('questions', [])
        if not isinstance(questions, list) or len(questions) == 0:
            return False
        
        # Validate each question structure
        for question in questions:
            if not isinstance(question, dict):
                return False
            
            required_fields = ['question']
            for field in required_fields:
                if field not in question or not question[field]:
                    return False
        
        return True
    
    def _enhance_quiz_response(self, api_response: Dict[str, Any], 
                              original_topics: List[str], response_time: float) -> Dict[str, Any]:
        """Enhance the API response with additional metadata"""
        enhanced = api_response.copy()
        
        # Add metadata
        enhanced['metadata'] = {
            'original_topics': original_topics,
            'optimized_topics': api_response.get('topics', original_topics),
            'response_time': response_time,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'question_count': len(api_response.get('questions', [])),
            'api_used': api_response.get('apiUsed', 'unknown'),
            'is_csv_fallback': api_response.get('apiUsed') == 'csv_fallback'
        }
        
        # Add performance indicators
        enhanced['performance'] = {
            'is_fast_response': response_time < 1.0,
            'is_csv_questions': api_response.get('apiUsed') == 'csv_fallback',
            'estimated_ai_cost': 0 if api_response.get('apiUsed') == 'csv_fallback' else 0.01
        }
        
        return enhanced
    
    def _update_average_response_time(self, response_time: float):
        """Update the average response time metric"""
        total_requests = self.metrics['successful_requests']
        if total_requests == 1:
            self.metrics['average_response_time'] = response_time
        else:
            # Calculate running average
            current_avg = self.metrics['average_response_time']
            self.metrics['average_response_time'] = ((current_avg * (total_requests - 1)) + response_time) / total_requests
    
    def check_health(self) -> Dict[str, Any]:
        """Check if the Quiz Generator API is healthy"""
        try:
            logger.info(f"Checking health of Quiz Generator API: {self.api_url}/health")
            start_time = time.time()
            response = requests.get(f"{self.api_url}/health", timeout=10)
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                health_data = response.json()
                return {
                    "status": "healthy",
                    "api_url": self.api_url,
                    "response_time": response_time,
                    "details": health_data,
                    "local_metrics": self.get_metrics()
                }
            else:
                return {
                    "status": "unhealthy",
                    "api_url": self.api_url,
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "response_time": response_time
                }
                
        except requests.exceptions.Timeout:
            return {
                "status": "timeout",
                "api_url": self.api_url,
                "error": "Health check timed out",
                "response_time": 10.0
            }
        except requests.exceptions.ConnectionError:
            return {
                "status": "connection_error",
                "api_url": self.api_url,
                "error": "Cannot connect to API",
                "response_time": 0.0
            }
        except Exception as e:
            return {
                "status": "error",
                "api_url": self.api_url,
                "error": str(e),
                "response_time": 0.0
            }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        cache_hit_rate = (self.metrics['cache_hits'] / max(self.metrics['total_requests'], 1)) * 100
        csv_ratio = (self.metrics['csv_questions'] / max(self.metrics['successful_requests'], 1)) * 100
        
        return {
            "total_requests": self.metrics['total_requests'],
            "successful_requests": self.metrics['successful_requests'],
            "failed_requests": self.metrics['failed_requests'],
            "cache_hits": self.metrics['cache_hits'],
            "cache_hit_rate": f"{cache_hit_rate:.1f}%",
            "csv_questions": self.metrics['csv_questions'],
            "ai_questions": self.metrics['ai_questions'],
            "csv_ratio": f"{csv_ratio:.1f}%",
            "average_response_time": self.metrics['average_response_time']
        }
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get comprehensive service status"""
        return {
            "service": "Quiz Generator Service",
            "api_url": self.api_url,
            "status": "active",
            "metrics": self.get_metrics(),
            "cache_stats": {
                "total_entries": len(self.cache),
                "cache_duration": self.cache_duration
            },
            "csv_subjects": list(self.csv_subjects),
            "last_request": self.last_request,
            "rate_limit_delay": self.rate_limit_delay,
            "timeout": self.timeout,
            "retry_attempts": self.retry_attempts
        }
    
    def clear_cache(self):
        """Clear the response cache"""
        self.cache.clear()
        logger.info("Quiz cache cleared")
    
    def reset_metrics(self):
        """Reset all metrics"""
        self.metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'cache_hits': 0,
            'csv_questions': 0,
            'ai_questions': 0,
            'average_response_time': 0
        }
        logger.info("Quiz generator metrics reset")

# Global instance for the application
quiz_generator_service = QuizGeneratorService()
