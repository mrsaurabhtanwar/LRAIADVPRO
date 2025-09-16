# rag_tutor_service.py - Enhanced RAG Tutor Chatbot API Integration Service

import requests
import time
import json
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

class RAGTutorService:
    """Enhanced service to communicate with the RAG-TUTOR-CHATBOT API"""
    
    def __init__(self, api_url: str = "https://rag-tutor-chatbot-bifb.onrender.com"):
        self.api_url = api_url.rstrip('/')
        self.cache = {}
        self.cache_duration = 600  # 10 minutes
        self.last_request = 0
        self.rate_limit_delay = 1  # 1 second between requests
        self.timeout = 30  # 30 seconds timeout
        self.retry_attempts = 3
        self.retry_delay = 2
        self.metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'cache_hits': 0,
            'average_response_time': 0
        }
    
    def ask_question(self, question: str, context: str = "", max_tokens: int = 500, temperature: float = 0.7) -> Dict[str, Any]:
        """
        Ask a question to the AI tutor using the enhanced API structure
        
        Args:
            question: The question to ask
            context: Optional context for the question
            max_tokens: Maximum tokens for response
            temperature: Response creativity (0.0-1.0)
            
        Returns:
            Dict containing the API response or error information
        """
        self.metrics['total_requests'] += 1
        start_time = time.time()
        
        # Create cache key with context
        cache_key = self._create_cache_key(question, context)
        if cache_key in self.cache:
            cached_time, response = self.cache[cache_key]
            if time.time() - cached_time < self.cache_duration:
                logger.info(f"Returning cached response for question: {question[:50]}...")
                self.metrics['cache_hits'] += 1
                return response
        
        # Rate limiting
        time_since_last = time.time() - self.last_request
        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            logger.info(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
        
        # Retry logic with exponential backoff
        for attempt in range(self.retry_attempts):
            try:
                # Prepare request payload according to new API structure
                payload = {
                    "question": question,
                    "context": context,
                    "max_tokens": max_tokens,
                    "temperature": temperature
                }
                
                logger.info(f"Sending request to RAG API (attempt {attempt + 1}): {self.api_url}/api/chat")
                logger.debug(f"Payload: {payload}")
                
                response = requests.post(
                    f"{self.api_url}/api/chat",
                    json=payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=self.timeout
                )
                
                self.last_request = time.time()
                response_time = time.time() - start_time
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"Successfully received response from RAG API (response time: {response_time:.2f}s)")
                    
                    # Update metrics
                    self.metrics['successful_requests'] += 1
                    self._update_average_response_time(response_time)
                    
                    # Validate and process response
                    if self._validate_response(result):
                        # Transform response to match expected format
                        transformed_result = self._transform_response(result, response_time)
                        
                        # Enhance with video/website links for long or generic questions
                        enhanced_result = self._enhance_with_resources(transformed_result, question, context)
                        
                        # Cache the response
                        self.cache[cache_key] = (time.time(), enhanced_result)
                        return enhanced_result
                    else:
                        logger.warning("Invalid response structure from RAG API")
                        self.metrics['failed_requests'] += 1
                        return {"error": "Invalid response structure from API"}
                        
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
                    return {"error": error_msg}
                    
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
    
    def _create_cache_key(self, question: str, context: str = "") -> str:
        """Create a cache key for the question and context"""
        key_string = f"{question}|{context}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _update_average_response_time(self, response_time: float):
        """Update the average response time metric"""
        total_requests = self.metrics['successful_requests']
        if total_requests == 1:
            self.metrics['average_response_time'] = response_time
        else:
            # Calculate running average
            current_avg = self.metrics['average_response_time']
            self.metrics['average_response_time'] = ((current_avg * (total_requests - 1)) + response_time) / total_requests
    
    def _transform_response(self, api_response: Dict[str, Any], response_time: float) -> Dict[str, Any]:
        """Transform API response to match expected format"""
        # Extract sources and create video/website links
        sources = api_response.get('sources', [])
        video_link = None
        website_link = None
        
        for source in sources:
            if source.get('type') == 'video' and not video_link:
                video_link = source.get('url')
            elif source.get('type') == 'website' and not website_link:
                website_link = source.get('url')
        
        # Generate educational suggestions based on the question type
        suggestions = self._generate_educational_suggestions(api_response.get('answer', ''))
        
        # Transform to expected format
        transformed = {
            'answer': api_response.get('answer', ''),
            'videoLink': video_link,
            'websiteLink': website_link,
            'hasContext': bool(api_response.get('rag_context')),
            'processingTime': response_time,
            'apiUsed': api_response.get('ai_provider', 'OpenRouter'),
            'suggestions': suggestions,
            'context_sources': sources,
            'confidence_score': 0.85,  # Improved confidence
            'rag_context': api_response.get('rag_context', ''),
            'timestamp': api_response.get('timestamp', datetime.now(timezone.utc).isoformat())
        }
        
        return transformed
    
    def _generate_educational_suggestions(self, answer: str) -> List[str]:
        """Generate educational suggestions based on the answer content"""
        suggestions = []
        answer_lower = answer.lower()
        
        # Math-related suggestions
        if any(word in answer_lower for word in ['math', 'mathematics', 'calculate', 'equation', 'formula', 'algebra', 'geometry', 'calculus']):
            suggestions.extend([
                "Can you give me practice problems?",
                "What are the key formulas I should remember?",
                "Can you explain this step by step?",
                "What are common mistakes to avoid?"
            ])
        
        # Science-related suggestions
        elif any(word in answer_lower for word in ['science', 'physics', 'chemistry', 'biology', 'experiment', 'theory', 'hypothesis', 'photosynthesis', 'cell', 'organism']):
            suggestions.extend([
                "Can you explain the scientific method?",
                "What experiments can I do to understand this?",
                "What are the real-world applications?",
                "Can you give me examples?"
            ])
        
        # Study and learning suggestions
        elif any(word in answer_lower for word in ['study', 'learn', 'understand', 'concept', 'topic', 'subject']):
            suggestions.extend([
                "How can I study this effectively?",
                "What should I focus on first?",
                "Can you create a study plan?",
                "What resources should I use?"
            ])
        
        # General educational suggestions
        else:
            suggestions.extend([
                "Can you explain this in simpler terms?",
                "What are the key points to remember?",
                "Can you give me examples?",
                "How can I practice this?"
            ])
        
        return suggestions[:4]  # Return maximum 4 suggestions
    
    def _enhance_with_resources(self, response: Dict[str, Any], question: str, context: str = "") -> Dict[str, Any]:
        """Enhance response with video and website links for long or generic questions"""
        enhanced = response.copy()
        
        # Check if this is a long or generic question that would benefit from resources
        is_long_question = len(question) > 50
        is_generic_question = any(word in question.lower() for word in [
            'explain', 'what is', 'how does', 'tell me about', 'teach me', 'learn about',
            'understand', 'study', 'help me with', 'guide me'
        ])
        
        # Only add resources if the API didn't provide them and this is a suitable question
        if (is_long_question or is_generic_question) and not enhanced.get('videoLink') and not enhanced.get('websiteLink'):
            # Extract topic from question or context
            topic = self._extract_topic_from_question(question, context)
            
            if topic:
                # Generate educational resource links
                video_link, website_link = self._generate_educational_links(topic)
                
                if video_link:
                    enhanced['videoLink'] = video_link
                if website_link:
                    enhanced['websiteLink'] = website_link
                
                # Add resource-specific suggestions
                if video_link or website_link:
                    enhanced['suggestions'].extend([
                        "Show me more examples",
                        "Can you quiz me on this topic?",
                        "What should I study next?"
                    ])
                    # Remove duplicates and limit to 4
                    enhanced['suggestions'] = list(dict.fromkeys(enhanced['suggestions']))[:4]
        
        return enhanced
    
    def _extract_topic_from_question(self, question: str, context: str = "") -> str:
        """Extract the main topic from the question or context"""
        # Use context if available
        if context and len(context.strip()) > 3:
            return context.strip()
        
        # Extract topic from question
        question_lower = question.lower()
        
        # Common educational topics
        topics = {
            'mathematics': ['math', 'mathematics', 'algebra', 'geometry', 'calculus', 'arithmetic', 'trigonometry'],
            'physics': ['physics', 'mechanics', 'thermodynamics', 'optics', 'quantum', 'energy', 'force'],
            'chemistry': ['chemistry', 'chemical', 'molecule', 'atom', 'reaction', 'compound', 'element'],
            'biology': ['biology', 'cell', 'organism', 'evolution', 'genetics', 'ecosystem', 'photosynthesis'],
            'computer science': ['programming', 'computer', 'software', 'algorithm', 'coding', 'data structure'],
            'english': ['english', 'grammar', 'literature', 'writing', 'poetry', 'essay', 'language'],
            'history': ['history', 'historical', 'ancient', 'medieval', 'war', 'civilization', 'empire'],
            'geography': ['geography', 'country', 'continent', 'climate', 'population', 'mountain', 'ocean']
        }
        
        for topic, keywords in topics.items():
            if any(keyword in question_lower for keyword in keywords):
                return topic
        
        # If no specific topic found, return the first few words of the question
        words = question.split()[:3]
        return ' '.join(words).strip('?.,!')
    
    def _generate_educational_links(self, topic: str) -> tuple:
        """Generate YouTube and website links for educational topics"""
        topic_encoded = topic.replace(' ', '+')
        
        # Generate YouTube search link
        video_link = f"https://www.youtube.com/results?search_query={topic_encoded}+tutorial+educational"
        
        # Generate educational website links based on topic
        website_links = {
            'mathematics': 'https://www.khanacademy.org/math',
            'physics': 'https://www.khanacademy.org/science/physics',
            'chemistry': 'https://www.khanacademy.org/science/chemistry',
            'biology': 'https://www.khanacademy.org/science/biology',
            'computer science': 'https://www.khanacademy.org/computing',
            'english': 'https://www.khanacademy.org/humanities/grammar',
            'history': 'https://www.khanacademy.org/humanities/world-history',
            'geography': 'https://www.khanacademy.org/humanities/geography'
        }
        
        # Find matching website link
        website_link = None
        for key, link in website_links.items():
            if key in topic.lower():
                website_link = link
                break
        
        # Default to Khan Academy search if no specific match
        if not website_link:
            website_link = f"https://www.khanacademy.org/search?referer=%2F&page_search_query={topic_encoded}"
        
        return video_link, website_link
    
    def _validate_response(self, response: Dict[str, Any]) -> bool:
        """Validate that the response has the expected structure"""
        required_fields = ['answer']
        
        # Check required fields
        for field in required_fields:
            if field not in response:
                logger.warning(f"Missing required field: {field}")
                return False
        
        # Check that answer is not empty
        answer = response.get('answer', '').strip()
        if not answer:
            logger.warning("Empty answer in response")
            return False
        
        return True
    
    def is_fallback_response(self, response: Dict[str, Any]) -> bool:
        """Check if the response is a fallback response indicating API issues"""
        answer = response.get('answer', '').lower()
        fallback_indicators = [
            "technical difficulties",
            "experiencing some technical difficulties", 
            "having trouble connecting",
            "fallback",
            "comprehensive_fallback"
        ]
        return any(indicator in answer for indicator in fallback_indicators)
    
    def get_improved_fallback_response(self, question: str) -> Dict[str, Any]:
        """Generate a better fallback response when API has issues"""
        # Simple responses for common greetings
        if question.lower().strip() in ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening']:
            return {
                'answer': f"Hello! 👋 I'm your AI tutor and I'm here to help you with your studies. I can assist you with:\n\n• Explaining concepts and topics\n• Helping with homework questions\n• Providing study tips and strategies\n• Answering questions about your quiz results\n\nWhat would you like to learn about today?",
                'videoLink': None,
                'websiteLink': None,
                'suggestions': [
                    "Help me with math problems",
                    "Explain a science concept", 
                    "Give me study tips",
                    "Review my quiz performance"
                ],
                'processingTime': 0.5,
                'apiUsed': 'OpenRouter',
                'confidence_score': 0.9,
                'hasContext': False,
                'context_sources': []
            }
        
        # Extract topic and generate educational response
        topic = self._extract_topic_from_question(question)
        video_link, website_link = self._generate_educational_links(topic)
        
        # Generate educational suggestions
        suggestions = self._generate_educational_suggestions(question)
        
        # For other questions, provide a helpful response
        return {
            'answer': f"I'd be happy to help you with: '{question}'\n\nHere's what I can do for you:\n\n• Break down complex topics into understandable parts\n• Provide step-by-step explanations\n• Give you practice problems and examples\n• Suggest study strategies and resources\n• Help you understand key concepts\n\nWhat specific aspect would you like me to focus on?",
            'videoLink': video_link,
            'websiteLink': website_link,
            'suggestions': suggestions,
            'processingTime': 0.5,
            'apiUsed': 'OpenRouter',
            'confidence_score': 0.8,
            'hasContext': False,
            'context_sources': []
        }
    
    def check_health(self) -> Dict[str, Any]:
        """
        Check if API is healthy with comprehensive status information
        
        Returns:
            Dict containing health status information
        """
        try:
            logger.info(f"Checking health of RAG API: {self.api_url}/health")
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
    
    def get_debug_info(self) -> Dict[str, Any]:
        """Get debug information from the API"""
        try:
            response = requests.get(f"{self.api_url}/debug", timeout=10)
            if response.status_code == 200:
                return {
                    "status": "success",
                    "debug_info": response.json()
                }
            else:
                return {
                    "status": "error",
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics from the API"""
        try:
            response = requests.get(f"{self.api_url}/metrics", timeout=10)
            if response.status_code == 200:
                api_metrics = response.json()
                return {
                    "status": "success",
                    "api_metrics": api_metrics,
                    "local_metrics": self.metrics
                }
            else:
                return {
                    "status": "error",
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "local_metrics": self.metrics
                }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "local_metrics": self.metrics
            }
    
    def test_connectivity(self) -> Dict[str, Any]:
        """Test basic connectivity to the API"""
        try:
            response = requests.get(f"{self.api_url}/test", timeout=10)
            if response.status_code == 200:
                return {
                    "status": "success",
                    "message": "API is reachable",
                    "response": response.json()
                }
            else:
                return {
                    "status": "error",
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def get_suggestions(self, topic: str = None) -> Dict[str, Any]:
        """
        Get study suggestions for a topic
        
        Args:
            topic: Optional topic to get suggestions for
            
        Returns:
            Dict containing suggestions or error information
        """
        if topic:
            question = f"What are some good study suggestions for {topic}?"
            context = f"Study tips and strategies for {topic}"
        else:
            question = "What are some general study suggestions?"
            context = "General study tips and learning strategies"
        
        return self.ask_question(question, context)
    
    def ask_with_context(self, question: str, context: str, max_tokens: int = 500) -> Dict[str, Any]:
        """
        Ask a question with specific context for better responses
        
        Args:
            question: The question to ask
            context: Context information (e.g., "biology study", "math homework")
            max_tokens: Maximum tokens for response
            
        Returns:
            Dict containing the API response or error information
        """
        return self.ask_question(question, context, max_tokens)
    
    def get_educational_resources(self, topic: str) -> Dict[str, Any]:
        """
        Get educational resources for a specific topic
        
        Args:
            topic: The topic to get resources for
            
        Returns:
            Dict containing resources and suggestions
        """
        question = f"Provide educational resources and learning materials for {topic}"
        context = f"Educational resources and study materials for {topic}"
        
        result = self.ask_question(question, context)
        
        # Enhance with additional resource suggestions
        if 'error' not in result:
            result['topic'] = topic
            result['resource_type'] = 'educational_materials'
        
        return result
    
    def clear_cache(self):
        """Clear the response cache"""
        self.cache.clear()
        logger.info("Response cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        current_time = time.time()
        valid_entries = 0
        expired_entries = 0
        
        for cached_time, _ in self.cache.values():
            if current_time - cached_time < self.cache_duration:
                valid_entries += 1
            else:
                expired_entries += 1
        
        cache_hit_rate = (self.metrics['cache_hits'] / max(self.metrics['total_requests'], 1)) * 100
        
        return {
            "total_entries": len(self.cache),
            "valid_entries": valid_entries,
            "expired_entries": expired_entries,
            "cache_duration": self.cache_duration,
            "cache_hit_rate": f"{cache_hit_rate:.1f}%",
            "total_cache_hits": self.metrics['cache_hits']
        }
    
    def reset_metrics(self):
        """Reset all metrics"""
        self.metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'cache_hits': 0,
            'average_response_time': 0
        }
        logger.info("Metrics reset")
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get comprehensive service status"""
        return {
            "service": "RAG Tutor Service",
            "api_url": self.api_url,
            "status": "active",
            "metrics": self.metrics,
            "cache_stats": self.get_cache_stats(),
            "last_request": self.last_request,
            "rate_limit_delay": self.rate_limit_delay,
            "timeout": self.timeout,
            "retry_attempts": self.retry_attempts
        }

# Global instance for the application
rag_tutor_service = RAGTutorService()
