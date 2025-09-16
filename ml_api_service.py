"""
ML API Service for Student Performance Prediction
Integrates with https://ml-api-pz1u.onrender.com
"""

import requests
import json
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

class MLAPIService:
    """Service class for interacting with the ML Performance Prediction API"""
    
    def __init__(self, base_url: str = "https://ml-api-1-o3jm.onrender.com"):
        self.base_url = base_url
        self.timeout = 30  # Increased timeout for cold starts
        self.retry_attempts = 3
        self.retry_delay = 2
        
    def check_health(self) -> Dict[str, Any]:
        """Check ML API health status"""
        try:
            response = requests.get(
                f"{self.base_url}/health",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return {
                    'status': 'healthy',
                    'response_time': response.elapsed.total_seconds(),
                    'data': response.json() if response.content else {}
                }
            else:
                return {
                    'status': 'unhealthy',
                    'status_code': response.status_code,
                    'error': response.text
                }
                
        except requests.exceptions.Timeout:
            return {
                'status': 'timeout',
                'error': 'API request timed out - possible cold start'
            }
        except requests.exceptions.RequestException as e:
            return {
                'status': 'error',
                'error': str(e)
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': f"Unexpected error: {str(e)}"
            }
    
    def predict_performance(self, student_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predict student performance using ML API
        
        Args:
            student_data: Dictionary containing student quiz metrics
            
        Returns:
            Dictionary with prediction results or error information
        """
        # Validate required fields
        required_fields = [
            'hint_count', 'bottom_hint', 'attempt_count', 
            'ms_first_response', 'duration',
            'avg_conf_frustrated', 'avg_conf_confused',
            'avg_conf_concentrating', 'avg_conf_bored'
        ]
        
        for field in required_fields:
            if field not in student_data:
                return {
                    'success': False,
                    'error': f'Missing required field: {field}'
                }
        
        # Ensure all values are floats
        api_payload = {}
        for key, value in student_data.items():
            try:
                api_payload[key] = float(value)
            except (ValueError, TypeError):
                return {
                    'success': False,
                    'error': f'Invalid value for {key}: {value}'
                }
        
        # Make API request with retries
        for attempt in range(self.retry_attempts):
            try:
                logger.info(f"ML API prediction attempt {attempt + 1}/{self.retry_attempts}")
                
                response = requests.post(
                    f"{self.base_url}/predict",
                    json=api_payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    prediction_data = response.json()
                    logger.info("ML API prediction successful")
                    
                    return {
                        'success': True,
                        'data': prediction_data,
                        'response_time': response.elapsed.total_seconds(),
                        'attempt': attempt + 1
                    }
                else:
                    error_msg = f"API returned status {response.status_code}: {response.text}"
                    logger.warning(error_msg)
                    
                    if attempt < self.retry_attempts - 1:
                        time.sleep(self.retry_delay * (attempt + 1))
                        continue
                    else:
                        return {
                            'success': False,
                            'error': error_msg,
                            'status_code': response.status_code
                        }
                        
            except requests.exceptions.Timeout:
                error_msg = "ML API request timed out - possible cold start"
                logger.warning(f"{error_msg} (attempt {attempt + 1})")
                
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                else:
                    return {
                        'success': False,
                        'error': error_msg,
                        'timeout': True
                    }
                    
            except requests.exceptions.RequestException as e:
                error_msg = f"ML API request failed: {str(e)}"
                logger.error(error_msg)
                
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                else:
                    return {
                        'success': False,
                        'error': error_msg
                    }
                    
            except Exception as e:
                error_msg = f"Unexpected error in ML API call: {str(e)}"
                logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg
                }
        
        return {
            'success': False,
            'error': 'All retry attempts failed'
        }
    
    def analyze_behavior(self, student_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze student behavior using ML API /analyze endpoint
        
        Args:
            student_data: Dictionary containing student quiz metrics
            
        Returns:
            Dictionary with behavior analysis results
        """
        try:
            # Use same payload as prediction
            api_payload = {}
            for key, value in student_data.items():
                api_payload[key] = float(value)
            
            response = requests.post(
                f"{self.base_url}/analyze",
                json=api_payload,
                headers={'Content-Type': 'application/json'},
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'data': response.json(),
                    'response_time': response.elapsed.total_seconds()
                }
            else:
                return {
                    'success': False,
                    'error': f"API returned status {response.status_code}: {response.text}",
                    'status_code': response.status_code
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f"Error in behavior analysis: {str(e)}"
            }
    
    def extract_student_metrics(self, quiz_attempt, session_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Extract student metrics from quiz attempt for ML API
        
        Args:
            quiz_attempt: QuizAttempt object
            session_data: Additional session data (hints used, etc.)
            
        Returns:
            Dictionary with student metrics for ML API
        """
        try:
            # Get responses
            responses = json.loads(getattr(quiz_attempt, 'responses_json', None) or '{}')
            
            # Calculate basic metrics
            hint_count = 0
            if session_data:
                hint_count = session_data.get('hints_used', 0)
            elif hasattr(quiz_attempt, 'hints_used'):
                hint_count = quiz_attempt.hints_used or 0
            
            bottom_hint = 1 if hint_count > 0 else 0
            attempt_count = len(responses)
            
            # Calculate timing metrics
            timing_data = {}
            if hasattr(quiz_attempt, 'timing_data_json') and quiz_attempt.timing_data_json:
                timing_data = json.loads(quiz_attempt.timing_data_json)
            
            # Calculate duration in milliseconds
            duration_ms = 300000  # Default 5 minutes
            if hasattr(quiz_attempt, 'started_at') and hasattr(quiz_attempt, 'completed_at'):
                if quiz_attempt.started_at and quiz_attempt.completed_at:
                    # Ensure both datetimes are timezone-aware for comparison
                    started_at = quiz_attempt.started_at
                    completed_at = quiz_attempt.completed_at
                    
                    if started_at.tzinfo is None:
                        started_at = started_at.replace(tzinfo=timezone.utc)
                    if completed_at.tzinfo is None:
                        completed_at = completed_at.replace(tzinfo=timezone.utc)
                    
                    duration = (completed_at - started_at).total_seconds()
                    duration_ms = int(duration * 1000)
            elif timing_data:
                duration_ms = int(timing_data.get('total_duration', 300000))
            
            # Calculate first response time
            ms_first_response = 5000  # Default 5 seconds
            if timing_data:
                ms_first_response = int(timing_data.get('first_response_time', 5000))
            
            # Calculate confidence levels based on quiz performance
            # These could be enhanced with actual emotion detection data
            score = getattr(quiz_attempt, 'score', 0) or 0
            total_questions = attempt_count
            
            # Estimate confidence levels based on performance patterns
            if score >= 80:
                avg_conf_frustrated = 0.1
                avg_conf_confused = 0.1
                avg_conf_concentrating = 0.8
                avg_conf_bored = 0.2
            elif score >= 60:
                avg_conf_frustrated = 0.2
                avg_conf_confused = 0.2
                avg_conf_concentrating = 0.6
                avg_conf_bored = 0.1
            else:
                avg_conf_frustrated = 0.4
                avg_conf_confused = 0.3
                avg_conf_concentrating = 0.4
                avg_conf_bored = 0.1
            
            # Adjust based on hint usage
            if hint_count > total_questions * 0.5:
                avg_conf_frustrated += 0.2
                avg_conf_confused += 0.1
                avg_conf_concentrating -= 0.1
            
            # Adjust based on response time
            if ms_first_response > 10000:  # Slow first response
                avg_conf_confused += 0.1
                avg_conf_concentrating -= 0.1
            
            # Normalize confidence levels
            total_conf = avg_conf_frustrated + avg_conf_confused + avg_conf_concentrating + avg_conf_bored
            if total_conf > 0:
                avg_conf_frustrated = max(0, min(1, avg_conf_frustrated / total_conf))
                avg_conf_confused = max(0, min(1, avg_conf_confused / total_conf))
                avg_conf_concentrating = max(0, min(1, avg_conf_concentrating / total_conf))
                avg_conf_bored = max(0, min(1, avg_conf_bored / total_conf))
            
            return {
                'hint_count': float(hint_count),
                'bottom_hint': float(bottom_hint),
                'attempt_count': float(attempt_count),
                'ms_first_response': float(ms_first_response),
                'duration': float(duration_ms),
                'avg_conf_frustrated': avg_conf_frustrated,
                'avg_conf_confused': avg_conf_confused,
                'avg_conf_concentrating': avg_conf_concentrating,
                'avg_conf_bored': avg_conf_bored
            }
            
        except Exception as e:
            logger.error(f"Error extracting student metrics: {e}")
            # Return default values
            return {
                'hint_count': 0.0,
                'bottom_hint': 0.0,
                'attempt_count': 5.0,
                'ms_first_response': 5000.0,
                'duration': 300000.0,
                'avg_conf_frustrated': 0.2,
                'avg_conf_confused': 0.3,
                'avg_conf_concentrating': 0.7,
                'avg_conf_bored': 0.1
            }

# Global instance
ml_api_service = MLAPIService()
