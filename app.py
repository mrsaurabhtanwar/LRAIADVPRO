# app.py - Educational Platform with External AI Tutor Integration
import logging
import requests
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.WARNING)
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Load configuration
config_name = os.environ.get('FLASK_ENV', 'development')
if config_name == 'production':
    from config import ProductionConfig
    app.config.from_object(ProductionConfig)
else:
    from config import DevelopmentConfig
    app.config.from_object(DevelopmentConfig)

# Initialize extensions
from extensions import db
db.init_app(app)

# Quiz generation is now handled by quiz_generator_service

# Import models
from models import (
    Student, Quiz, QuizAttempt, ChatSession, ChatMessage, 
    StudentRecommendation,
    StudentProfile, MLPrediction, Topic, AIInteraction
)

# Quiz generation is now handled by quiz_generator_service

# Import and initialize RAG tutor service
from rag_tutor_service import rag_tutor_service

# Import ML API service
from ml_api_service import ml_api_service

# Import Quiz Generator service
from quiz_generator_service import quiz_generator_service


# Template filters
@app.template_filter('chr')
def chr_filter(number: int, offset: int = 64) -> str:
    """Convert number to letter (1->A, 2->B, etc.)"""
    return chr(number + offset)

@app.template_filter('from_json')
def from_json_filter(value: str) -> Any:
    """Convert JSON string to Python object"""
    import json
    return json.loads(value)

# Add built-in 'abs' function to Jinja2 environment
app.jinja_env.globals['abs'] = abs

# ===================== SECURITY DECORATORS =====================

from typing import Callable


def login_required(f: Callable) -> Callable:
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function

# ===================== ERROR HANDLERS =====================

@app.errorhandler(404)
def not_found_error(error: Any) -> tuple[str, int]:
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error: Any) -> tuple[str, int]:
    db.session.rollback()
    return render_template('errors/500.html'), 500

@app.errorhandler(403)
def forbidden_error(error: Any) -> tuple[str, int]:
    return render_template('errors/403.html'), 403

# ===================== ML API INTEGRATION FUNCTIONS =====================

def call_ml_api_for_prediction(attempt: Any, student_id: int) -> Any:
    """Call the ML API to get student performance prediction using enhanced service"""
    try:
        # Extract student metrics using the ML service
        session_data = {
            'hints_used': session.get('hints_used', 0)
        }
        
        student_metrics = ml_api_service.extract_student_metrics(attempt, session_data)
        
        # Call ML API using the service
        result = ml_api_service.predict_performance(student_metrics)
        
        if result['success']:
            app.logger.info(f"ML API prediction successful for student {student_id} (attempt {result.get('attempt', 1)})")
            return result['data']
        else:
            app.logger.error(f"ML API prediction failed: {result['error']}")
            return None
            
    except Exception as e:
        app.logger.error(f"Error calling ML API: {e}")
        return None

def store_ml_prediction(student_id: int, attempt_id: int, prediction_data: Dict[str, Any]) -> None:
    """Store ML prediction data in the database with enhanced error handling"""
    try:
        prediction = MLPrediction()
        prediction.student_id = student_id
        prediction.quiz_attempt_id = attempt_id
        
        # Extract prediction data with fallbacks
        prediction_info = prediction_data.get('prediction', {})
        prediction.predicted_score = prediction_info.get('correctness_score', 0.5)
        prediction.category = prediction_info.get('performance_category', 'Average')
        prediction.confidence_level = prediction_data.get('confidence_level', 0.8)
        
        # Store learner profile and behaviors
        prediction.learner_profile_json = json.dumps(prediction_data.get('learner_profile', {}))
        prediction.features_json = json.dumps(prediction_data.get('behaviors', {}))
        
        # Store additional ML insights
        prediction.model_version = prediction_data.get('model_version', 'v1.0')
        prediction.created_at = datetime.now(timezone.utc)
        
        # Store raw API response for debugging
        prediction.raw_response_json = json.dumps(prediction_data)

        db.session.add(prediction)
        db.session.commit()

        app.logger.info(f"ML prediction stored for student {student_id}: {prediction.category} (score: {prediction.predicted_score})")

    except Exception as e:
        app.logger.error(f"Error storing ML prediction: {e}")
        db.session.rollback()

def update_student_profile_with_ml_data(student_id: int, prediction_data: Dict[str, Any]) -> None:
    """Update student profile with ML insights"""
    try:
        from models import StudentProfile
        
        profile = StudentProfile.query.filter_by(student_id=student_id).first()
        if not profile:
            profile = StudentProfile()
            profile.student_id = student_id
            db.session.add(profile)
        
        # Update profile with ML insights
        prediction = prediction_data.get('prediction', {})
        behaviors = prediction_data.get('behaviors', {})
        learner_profile = prediction_data.get('learner_profile', {})
        
        # Update basic prediction data
        profile.predicted_category = prediction.get('performance_category', 'General Learner')
        profile.confidence_level = prediction.get('correctness_score', 0.5)
        profile.last_prediction_update = datetime.now()
        profile.learner_profile_json = json.dumps(prediction_data)
        
        # Update learning style based on ML analysis
        if learner_profile:
            # Use ML-determined learning style if available
            profile.learning_style = learner_profile.get('learning_style', 'Adaptive Learner')
        elif behaviors:
            # Fallback to behavior-based classification
            if behaviors.get('engagement') == 'High' and behaviors.get('efficiency') == 'High':
                profile.learning_style = 'Active Learner'
            elif behaviors.get('hint_dependency') == 'High':
                profile.learning_style = 'Guided Learner'
            elif behaviors.get('persistence') == 'High':
                profile.learning_style = 'Persistent Learner'
            else:
                profile.learning_style = 'Adaptive Learner'
        else:
            profile.learning_style = 'Adaptive Learner'
        
        # Store additional ML insights
        if behaviors:
            profile.behavioral_insights_json = json.dumps(behaviors)
        
        # Generate recommendations based on ML insights
        generate_ml_based_recommendations(student_id, prediction_data)
        
        db.session.commit()
        app.logger.info(f"Student profile updated with ML data for student {student_id}: {profile.learning_style}")
        
    except Exception as e:
        app.logger.error(f"Error updating student profile: {e}")
        db.session.rollback()

def generate_ml_based_recommendations(student_id, prediction_data):
    """Generate recommendations based on ML analysis"""
    try:
        from models import StudentRecommendation
        
        prediction = prediction_data.get('prediction', {})
        behaviors = prediction_data.get('behaviors', {})
        recommendations_data = prediction_data.get('recommendations', {})
        
        # Create recommendation based on performance category
        category = prediction.get('performance_category', 'Average')
        
        if category == 'Poor':
            recommendation = StudentRecommendation(
                student_id=student_id,
                recommendation_type='intervention',
                title='Immediate Learning Support Needed',
                description=recommendations_data.get('feedback_message', 'Focus on building foundational concepts'),
                priority=1,
                settings_json=json.dumps({
                    'learning_material': recommendations_data.get('learning_material', ''),
                    'ml_category': category,
                    'confidence_score': prediction.get('correctness_score', 0)
                }),
                created_at=datetime.now(timezone.utc),
                expires_at=(datetime.now(timezone.utc).replace(hour=23, minute=59, second=59) + timedelta(days=30))
            )
        elif category == 'Weak':
            recommendation = StudentRecommendation(
                student_id=student_id,
                recommendation_type='practice',
                title='Additional Practice Recommended',
                description=recommendations_data.get('feedback_message', 'Work on strengthening your understanding'),
                priority=2,
                settings_json=json.dumps({
                    'learning_material': recommendations_data.get('learning_material', ''),
                    'ml_category': category
                }),
                created_at=datetime.now(timezone.utc),
                expires_at=(datetime.now(timezone.utc).replace(hour=23, minute=59, second=59) + timedelta(days=21))
            )
        elif category in ['Strong', 'Outstanding']:
            recommendation = StudentRecommendation(
                student_id=student_id,
                recommendation_type='advancement',
                title='Ready for Advanced Challenges',
                description=recommendations_data.get('feedback_message', 'Explore advanced topics and challenges'),
                priority=3,
                settings_json=json.dumps({
                    'learning_material': recommendations_data.get('learning_material', ''),
                    'ml_category': category
                }),
                created_at=datetime.now(timezone.utc),
                expires_at=(datetime.now(timezone.utc).replace(hour=23, minute=59, second=59) + timedelta(days=14))
            )
        
        # Deactivate old recommendations of the same type
        if 'recommendation' in locals():
            old_recs = StudentRecommendation.query.filter_by(
                student_id=student_id,
                recommendation_type=recommendation.recommendation_type,
                is_active=True
            ).all()
            
            for old_rec in old_recs:
                old_rec.is_active = False
                
            db.session.add(recommendation)
            
    except Exception as e:
        app.logger.error(f"Error generating ML-based recommendations: {e}")

# ===================== MAIN ROUTES =====================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        student_id = request.form.get('student_id')
        class_name = request.form.get('class')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not all([name, student_id, class_name, email, password]):
            flash('All fields are required')
            return render_template('register.html')
        
        # Check if email already exists
        existing_student = Student.query.filter_by(email=email).first()
        if existing_student:
            flash('Email already registered. Please use a different email or login.')
            return render_template('register.html')
        
        password_hash = generate_password_hash(password)
        
        student = Student(
            name=name,
            student_id=student_id,
            class_name=class_name,
            email=email,
            password_hash=password_hash
        )
        
        try:
            db.session.add(student)
            db.session.commit()
            flash('Registration successful! Please login.')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash('Registration failed. Please try again.')
            return render_template('register.html')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            flash('Please provide both email and password')
            return render_template('login.html')
        
        student = Student.query.filter_by(email=email).first()
        
        if student and check_password_hash(student.password_hash, password):
            session['user_id'] = student.id
            session['user_name'] = student.name
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Student dashboard with ML insights"""
    student_id = session['user_id']
    student = db.session.get(Student, student_id)
    
    # Get recent quiz attempts
    recent_quizzes = QuizAttempt.query.filter_by(
        student_id=student_id,
        is_completed=True
    ).order_by(QuizAttempt.completed_at.desc()).limit(5).all()
    
    # Get ML insights
    ml_insights = {}
    latest_prediction = MLPrediction.query.filter_by(
        student_id=student_id
    ).order_by(MLPrediction.created_at.desc()).first()
    
    if latest_prediction:
        ml_insights = {
            'category': latest_prediction.category,
            'score': latest_prediction.predicted_score,
            'confidence': latest_prediction.confidence_level,
            'model_version': latest_prediction.model_version,
            'created_at': latest_prediction.created_at
        }
        
        # Parse learner profile and behaviors
        try:
            if latest_prediction.learner_profile_json:
                ml_insights['learner_profile'] = json.loads(latest_prediction.learner_profile_json)
            if latest_prediction.features_json:
                ml_insights['behaviors'] = json.loads(latest_prediction.features_json)
        except (json.JSONDecodeError, AttributeError):
            pass
    
    # Get student profile for additional insights
    student_profile = StudentProfile.query.filter_by(student_id=student_id).first()
    if student_profile:
        ml_insights['learning_style'] = student_profile.learning_style
        ml_insights['last_update'] = student_profile.last_prediction_update
    
    # Calculate basic stats
    total_quizzes = len(recent_quizzes)
    average_score = sum(q.score for q in recent_quizzes if q.score) / total_quizzes if total_quizzes > 0 else 0
    
    return render_template('dashboard.html',
                         student=student,
                         recent_quizzes=recent_quizzes,
                         ml_insights=ml_insights,
                         total_quizzes=total_quizzes,
                         average_score=average_score)

@app.route('/quiz')
@login_required
def quiz_selection():
    """Quiz selection page"""
    quizzes = Quiz.query.filter_by(is_active=True).all()
    return render_template('quiz_selection.html', quizzes=quizzes)

@app.route('/quiz/<int:quiz_id>')
@login_required
def start_quiz(quiz_id):
    """Start a new quiz attempt"""
    quiz = db.session.get(Quiz, quiz_id)
    if not quiz:
        flash('Quiz not found')
        return redirect(url_for('quiz_selection'))
    
    # Create new attempt
    attempt = QuizAttempt(
        student_id=session['user_id'],
        quiz_id=quiz_id,
        started_at=datetime.now(timezone.utc)
    )
    
    db.session.add(attempt)
    db.session.commit()
    
    session['current_attempt'] = attempt.id
    return redirect(url_for('quiz_question', question_num=1))

@app.route('/quiz/question/<int:question_num>')
@login_required
def quiz_question(question_num):
    """Display a specific quiz question"""
    if 'current_attempt' not in session:
        return redirect(url_for('login'))

    attempt_id = session['current_attempt']
    attempt = db.session.get(QuizAttempt, attempt_id)

    if not attempt:
        flash('Quiz session not found')
        return redirect(url_for('quiz_selection'))

    quiz = db.session.get(Quiz, attempt.quiz_id)

    # Handle questions (ensure proper slicing)
    questions = json.loads(quiz.questions_json or '[]')

    # Ensure question_num is within bounds
    if question_num < 1 or question_num > len(questions):
        return redirect(url_for('complete_quiz'))

    current_question = questions[question_num - 1]
    
    # Clean and format question text
    question_text = current_question.get('question', current_question.get('text', ''))
    # Handle potential Markdown or LaTeX in question text
    question_text = question_text.replace('\n', '<br>')
    
    # Format each option
    options = current_question.get('options', [])
    formatted_options = []
    for option in options:
        if isinstance(option, dict):
            option_text = option.get('text', '').strip()
            formatted_options.append({
                'id': option.get('id', 'A'),
                'text': option_text,
                'option_text': option_text  # For backward compatibility
            })
        elif isinstance(option, str):
            formatted_options.append({
                'id': 'A',
                'text': option.strip(),
                'option_text': option.strip()
            })
    
    # Update question with formatted data
    current_question['question'] = question_text
    current_question['options'] = formatted_options

    return render_template('quiz_question.html',
                           question=current_question,
                           question_num=question_num,
                           total_questions=len(questions),
                           quiz=quiz)

@app.route('/quiz/submit/<int:question_num>', methods=['POST'])
@login_required
def submit_answer(question_num):
    """Submit quiz answer"""
    if 'current_attempt' not in session:
        return redirect(url_for('login'))
    
    attempt_id = session['current_attempt']
    attempt = db.session.get(QuizAttempt, attempt_id)
    
    # Store answer
    answer = request.form.get('answer')
    confidence = request.form.get('confidence', 0.5)
    
    # Track timing data for ML analysis
    current_time = datetime.now(timezone.utc)
    timing_data = json.loads(attempt.timing_data_json or '{}')
    
    # Record first response time if not already set
    if 'first_response_time' not in timing_data and question_num == 1:
        if hasattr(attempt, 'started_at') and attempt.started_at:
            first_response_time = (current_time - attempt.started_at).total_seconds() * 1000
            timing_data['first_response_time'] = first_response_time
    
    # Update timing data
    timing_data[f'question_{question_num}_response_time'] = current_time.isoformat()
    attempt.timing_data_json = json.dumps(timing_data)
    
    responses = json.loads(attempt.responses_json or '{}')
    responses[f'question_{question_num}'] = {
        'answer': answer,
        'confidence': confidence,
        'timestamp': current_time.isoformat()
    }
    attempt.responses_json = json.dumps(responses)
    
    db.session.commit()
    
    # Check if last question
    quiz = db.session.get(Quiz, attempt.quiz_id)
    questions = json.loads(quiz.questions_json or '[]')
    
    if question_num >= len(questions):
        return redirect(url_for('complete_quiz'))
    else:
        return redirect(url_for('quiz_question', question_num=question_num + 1))

@app.route('/quiz/complete')
@login_required
def complete_quiz():
    """Complete quiz and show results"""
    if 'current_attempt' not in session:
        return redirect(url_for('quiz_selection'))
    
    attempt_id = session['current_attempt']
    attempt = db.session.get(QuizAttempt, attempt_id)
    
    # Mark as completed and record total duration
    completion_time = datetime.now(timezone.utc)
    attempt.completed_at = completion_time
    attempt.is_completed = True
    
    # Record total duration for ML analysis
    if hasattr(attempt, 'started_at') and attempt.started_at:
        total_duration = (completion_time - attempt.started_at).total_seconds() * 1000
        timing_data = json.loads(attempt.timing_data_json or '{}')
        timing_data['total_duration'] = total_duration
        attempt.timing_data_json = json.dumps(timing_data)
    
    # Calculate score
    responses = json.loads(attempt.responses_json or '{}')
    quiz = db.session.get(Quiz, attempt.quiz_id)
    questions = json.loads(quiz.questions_json or '[]')
    
    correct_answers = 0
    detailed_analysis = []
    
    for i, question in enumerate(questions, 1):
        response = responses.get(f'question_{i}', {})
        user_answer = response.get('answer', '')
        
        # Get correct answer - handle different API response formats
        # Determine correct answer id and text (support both formats)
        correct_id = None
        correct_text = None
        if 'correct_answer' in question and question.get('correct_answer'):
            ca = question.get('correct_answer')
            if isinstance(ca, str) and len(ca.strip()) == 1 and ca.strip().upper() in 'ABCD':
                correct_id = ca.strip().upper()
            else:
                # If correct_answer appears to be full text, try to map to an option id
                if 'options' in question:
                    for o in question['options']:
                        if o.get('text') and isinstance(ca, str) and ca.strip().lower() == o.get('text').strip().lower():
                            correct_id = o.get('id')
                            break
                if not correct_id:
                    correct_text = str(ca)
        elif 'options' in question:
            for option in question['options']:
                if option.get('is_correct', False):
                    correct_id = option.get('id')
                    correct_text = option.get('text', option.get('option_text', ''))
                    break

        is_correct = False
        if user_answer:
            ua = str(user_answer).strip()
            # If user provided a letter (A/B/C/D)
            if len(ua) == 1 and ua.upper() in 'ABCD':
                if correct_id:
                    is_correct = ua.upper() == correct_id
                else:
                    # Fallback: map letter to option text and compare
                    option_index = ord(ua.upper()) - ord('A')
                    if 'options' in question and option_index < len(question['options']):
                        user_answer_text = question['options'][option_index].get('text', '')
                        if correct_text:
                            is_correct = user_answer_text.strip().lower() == correct_text.strip().lower()
            else:
                # User provided full text - compare to correct_text or option text
                if correct_text:
                    is_correct = ua.strip().lower() == correct_text.strip().lower()
                elif correct_id and 'options' in question:
                    for o in question['options']:
                        if o.get('id') == correct_id:
                            is_correct = ua.strip().lower() == o.get('text', '').strip().lower()
                            break
        
        if is_correct:
            correct_answers += 1
            
        # Store detailed analysis
        detailed_analysis.append({
            'question': question.get('question', question.get('question_text', f'Question {i}')),
            'user_answer': user_answer,
            'correct_answer': (correct_id or correct_text) or 'Not available',
            'is_correct': is_correct,
            'confidence': 0.8  # Default confidence
        })
    
    # Calculate final score
    attempt.score = (correct_answers / len(questions)) * 100 if questions else 0
    
    # Store detailed analysis for results page
    attempt.detailed_analysis_json = json.dumps(detailed_analysis)
    
    # Call ML API for student performance analysis
    ml_prediction = call_ml_api_for_prediction(attempt, session['user_id'])
    if ml_prediction:
        # Store ML prediction in database
        store_ml_prediction(session['user_id'], attempt_id, ml_prediction)
        
        # Update student profile with ML insights
        update_student_profile_with_ml_data(session['user_id'], ml_prediction)
    
    db.session.commit()
    session.pop('current_attempt', None)
    
    return redirect(url_for('quiz_results', attempt_id=attempt_id))

@app.route('/quiz/results/<int:attempt_id>')
@login_required
def quiz_results(attempt_id):
    """Display quiz results"""
    attempt = db.session.get(QuizAttempt, attempt_id)
    
    if attempt.student_id != session['user_id']:
        flash('Access denied.')
        return redirect(url_for('dashboard'))
    
    quiz = db.session.get(Quiz, attempt.quiz_id)
    
    # Get detailed question analysis
    question_analysis = []
    if hasattr(attempt, 'detailed_analysis_json') and attempt.detailed_analysis_json:
        try:
            question_analysis = json.loads(attempt.detailed_analysis_json)
        except (json.JSONDecodeError, AttributeError):
            # Fallback to old method if detailed analysis not available
            question_analysis = generate_fallback_analysis(attempt, quiz)
    else:
        question_analysis = generate_fallback_analysis(attempt, quiz)
    
    # Generate personalized recommendations based on quiz performance
    new_recommendations = generate_personalized_recommendations(attempt, quiz, question_analysis)
    
    # Get existing recommendations from database
    existing_recommendations = StudentRecommendation.query.filter_by(
        student_id=session['user_id'],
        is_completed=False
    ).limit(3).all()
    
    # Combine new and existing recommendations, prioritizing existing ones
    all_recommendations = list(existing_recommendations) + new_recommendations[:2]  # Limit total recommendations
    
    return render_template('quiz_results.html',
                         attempt=attempt,
                         quiz=quiz,
                         recommendations=all_recommendations,
                         question_analysis=question_analysis)

def generate_fallback_analysis(attempt, quiz):
    """Generate fallback question analysis if detailed analysis is not available"""
    question_analysis = []
    responses = json.loads(attempt.responses_json or '{}')
    questions = json.loads(quiz.questions_json or '[]')
    
    for i, question in enumerate(questions, 1):
        response = responses.get(f'question_{i}', {})
        user_answer = response.get('answer', 'No answer provided')
        
        # Try to determine correct answer id/text
        correct_id = None
        correct_text = None
        if 'correct_answer' in question and question.get('correct_answer'):
            ca = question.get('correct_answer')
            if isinstance(ca, str) and len(ca.strip()) == 1 and ca.strip().upper() in 'ABCD':
                correct_id = ca.strip().upper()
            else:
                # map full text to option id if possible
                if 'options' in question:
                    for o in question['options']:
                        if o.get('text') and isinstance(ca, str) and ca.strip().lower() == o.get('text').strip().lower():
                            correct_id = o.get('id')
                            break
                if not correct_id:
                    correct_text = str(ca)
        elif 'options' in question:
            for option in question['options']:
                if option.get('is_correct', False):
                    correct_id = option.get('id')
                    correct_text = option.get('text', option.get('option_text', ''))
                    break

        # Simple correctness check
        is_correct = False
        if isinstance(user_answer, str):
            ua = user_answer.strip()
            if len(ua) == 1 and ua.upper() in 'ABCD':
                if correct_id:
                    is_correct = ua.upper() == correct_id
                else:
                    # map letter to option text
                    idx = ord(ua.upper()) - ord('A')
                    if 'options' in question and idx < len(question['options']):
                        is_correct = question['options'][idx].get('text', '').strip().lower() == (correct_text or '').strip().lower()
            else:
                if correct_text:
                    is_correct = ua.lower() == correct_text.strip().lower()
                elif correct_id and 'options' in question:
                    for o in question['options']:
                        if o.get('id') == correct_id:
                            is_correct = ua.lower() == o.get('text', '').strip().lower()
                            break
        
        question_analysis.append({
            'question': question.get('question', question.get('question_text', f'Question {i}')),
            'user_answer': user_answer,
            'correct_answer': (correct_id or correct_text) or 'Not available',
            'is_correct': is_correct,
            'confidence': 0.8
        })
    
    return question_analysis

def generate_personalized_recommendations(attempt, quiz, question_analysis):
    """Generate personalized recommendations based on quiz performance"""
    recommendations = []
    
    # Calculate performance metrics
    total_questions = len(question_analysis)
    correct_count = sum(1 for qa in question_analysis if qa['is_correct'])
    score_percentage = (correct_count / total_questions * 100) if total_questions > 0 else 0
    
    # Performance-based recommendations
    if score_percentage < 60:
        recommendations.append({
            'title': 'Review Core Concepts',
            'description': f'Focus on {quiz.topic} fundamentals to strengthen your understanding.',
            'recommendation_type': 'study_material',
            'priority': 1
        })
        
        recommendations.append({
            'title': 'Practice More Questions',
            'description': 'Take additional practice quizzes to reinforce learning.',
            'recommendation_type': 'quiz_difficulty',
            'priority': 2
        })
    
    elif score_percentage < 80:
        recommendations.append({
            'title': 'Targeted Practice',
            'description': f'Work on specific areas within {quiz.topic} that need improvement.',
            'recommendation_type': 'focus_area',
            'priority': 1
        })
        
        recommendations.append({
            'title': 'Intermediate Level Quiz',
            'description': 'Try a medium difficulty quiz to challenge yourself.',
            'recommendation_type': 'quiz_difficulty',
            'priority': 2
        })
    
    else:
        recommendations.append({
            'title': 'Advanced Topics',
            'description': f'Explore advanced concepts in {quiz.topic} to deepen your knowledge.',
            'recommendation_type': 'study_material',
            'priority': 1
        })
        
        recommendations.append({
            'title': 'Challenge Yourself',
            'description': 'Take a harder difficulty quiz or explore related subjects.',
            'recommendation_type': 'quiz_difficulty',
            'priority': 2
        })
    
    # Time-based recommendations
    if hasattr(attempt, 'hints_used') and attempt.hints_used and attempt.hints_used > total_questions * 0.5:
        recommendations.append({
            'title': 'Build Confidence',
            'description': 'Practice without hints to build independent problem-solving skills.',
            'recommendation_type': 'focus_area',
            'priority': 3
        })
    
    # Save recommendations to database
    student_id = session['user_id']
    recommendation_objects = []
    
    for rec_data in recommendations:
        recommendation = StudentRecommendation(
            student_id=student_id,
            quiz_attempt_id=attempt.id,
            title=rec_data['title'],
            description=rec_data['description'],
            recommendation_type=rec_data['recommendation_type'],
            priority=rec_data['priority']
        )
        db.session.add(recommendation)
        recommendation_objects.append(recommendation)
    
    try:
        db.session.commit()
        # Now the objects have IDs after commit
        return recommendation_objects
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error saving recommendations: {e}")
        # Return empty list if saving fails
        return []

@app.route('/recommendation/<int:rec_id>/complete', methods=['POST'])
@login_required
def complete_recommendation(rec_id):
    """Mark a recommendation as completed"""
    recommendation = db.session.get(StudentRecommendation, rec_id)
    
    if recommendation and recommendation.student_id == session['user_id']:
        recommendation.is_completed = True
        recommendation.completed_at = datetime.now(timezone.utc)
        db.session.commit()
        flash('Recommendation marked as completed!', 'success')
    else:
        flash('Recommendation not found or access denied.', 'error')
    
    return redirect(request.referrer or url_for('dashboard'))

# ===================== QUIZ GENERATION ROUTES =====================

# Old quiz generation form removed - now using API-based generation

# Old generate_quiz function removed - now using /api/quiz-generator/generate

# Old hint function removed - hints are now handled by the AI tutor

# Old quiz API health endpoint removed - now using /api/quiz-generator/health

@app.route('/api/ml/health')
def ml_api_health():
    """Check ML API health status"""
    health = ml_api_service.check_health()
    return jsonify(health)

@app.route('/api/ml/analyze', methods=['POST'])
@login_required
def analyze_student_behavior():
    """Analyze student behavior using ML API"""
    try:
        data = request.get_json()
        student_id = session.get('user_id')
        
        if not student_id:
            return jsonify({'error': 'User not authenticated'}), 401
        
        # Get recent quiz attempt for analysis
        recent_attempt = QuizAttempt.query.filter_by(
            student_id=student_id,
            is_completed=True
        ).order_by(QuizAttempt.completed_at.desc()).first()
        
        if not recent_attempt:
            return jsonify({'error': 'No quiz attempts found for analysis'}), 404
        
        # Extract metrics and analyze
        session_data = {'hints_used': session.get('hints_used', 0)}
        student_metrics = ml_api_service.extract_student_metrics(recent_attempt, session_data)
        
        result = ml_api_service.analyze_behavior(student_metrics)
        
        if result['success']:
            return jsonify({
                'success': True,
                'analysis': result['data'],
                'response_time': result.get('response_time', 0)
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 500
            
    except Exception as e:
        app.logger.error(f"Error in behavior analysis: {e}")
        return jsonify({'error': 'Internal server error'}), 500

# ===================== RAG TUTOR API ROUTES =====================

@app.route('/api/ai/ask', methods=['POST'])
@login_required
def ask_ai_question():
    """Direct API endpoint to ask AI tutor questions"""
    data = request.get_json()
    question = data.get('question')
    
    if not question:
        return jsonify({'error': 'Question is required'}), 400
    
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'User not authenticated'}), 401
    
    # Get AI response using RAG service
    result = rag_tutor_service.ask_question(question)
    
    if 'error' in result:
        return jsonify({'error': result['error']}), 500
    
    # Store interaction in database
    try:
        interaction = AIInteraction(
            user_id=user_id,
            question=question,
            answer=result.get('answer', ''),
            video_link=result.get('videoLink'),
            website_link=result.get('websiteLink'),
            processing_time=result.get('processingTime'),
            api_used=result.get('apiUsed'),
            confidence_score=result.get('confidence_score'),
            has_context=result.get('hasContext', False),
            suggestions=result.get('suggestions', []),
            context_sources=result.get('context_sources', [])
        )
        db.session.add(interaction)
        db.session.commit()
    except Exception as e:
        app.logger.error(f"Error storing AI interaction: {e}")
        db.session.rollback()
    
    return jsonify(result)

@app.route('/api/ai/health')
def rag_api_health():
    """Check RAG tutor API health with comprehensive status"""
    health = rag_tutor_service.check_health()
    return jsonify(health)

@app.route('/api/ai/debug')
def rag_api_debug():
    """Get RAG tutor API debug information"""
    debug_info = rag_tutor_service.get_debug_info()
    return jsonify(debug_info)

@app.route('/api/ai/metrics')
def rag_api_metrics():
    """Get RAG tutor API metrics and performance data"""
    metrics = rag_tutor_service.get_metrics()
    return jsonify(metrics)

@app.route('/api/ai/test')
def rag_api_test():
    """Test RAG tutor API connectivity"""
    test_result = rag_tutor_service.test_connectivity()
    return jsonify(test_result)

@app.route('/api/ai/status')
def rag_api_status():
    """Get comprehensive RAG tutor service status"""
    status = rag_tutor_service.get_service_status()
    return jsonify(status)

# Quiz Generator API Endpoints
@app.route('/api/quiz-generator/health')
def quiz_generator_health():
    """Check Quiz Generator API health"""
    health = quiz_generator_service.check_health()
    return jsonify(health)

@app.route('/api/quiz-generator/status')
def quiz_generator_status():
    """Get Quiz Generator service status"""
    status = quiz_generator_service.get_service_status()
    return jsonify(status)

@app.route('/api/quiz-generator/metrics')
def quiz_generator_metrics():
    """Get Quiz Generator metrics"""
    metrics = quiz_generator_service.get_metrics()
    return jsonify(metrics)

@app.route('/api/quiz-generator/generate', methods=['POST'])
@login_required
def generate_quiz_questions():
    """Generate quiz questions using the Quiz Generator API"""
    try:
        data = request.get_json()
        topics = data.get('topics', [])
        difficulty = data.get('difficulty', 'medium')
        n_questions = data.get('n_questions', 5)
        question_type = data.get('type', 'mcq')
        include_explanations = data.get('include_explanations', True)
        
        if not topics:
            return jsonify({'error': 'Topics are required'}), 400
        
        if n_questions < 1 or n_questions > 10:
            return jsonify({'error': 'Number of questions must be between 1 and 10'}), 400
        
        if difficulty not in ['easy', 'medium', 'hard']:
            return jsonify({'error': 'Difficulty must be easy, medium, or hard'}), 400
        
        if question_type not in ['mcq', 'short']:
            return jsonify({'error': 'Question type must be mcq or short'}), 400
        
        # Get student behavior data for personalization
        student_id = session.get('user_id')
        student_behavior = None
        
        if student_id:
            # Get recent quiz performance for personalization
            recent_attempts = QuizAttempt.query.filter_by(
                student_id=student_id,
                is_completed=True
            ).order_by(QuizAttempt.completed_at.desc()).limit(5).all()
            
            if recent_attempts:
                # Calculate behavior metrics
                total_attempts = len(recent_attempts)
                avg_score = sum(attempt.score for attempt in recent_attempts if attempt.score) / total_attempts
                avg_time = sum(attempt.completion_time for attempt in recent_attempts if attempt.completion_time) / total_attempts
                
                # Calculate behavior metrics in the format expected by the API
                hint_count = max(1, min(5, int((100 - avg_score) / 20))) if avg_score else 2
                bottom_hint = 1 if avg_score and avg_score < 60 else 0
                attempt_count = max(1, min(5, int((100 - avg_score) / 25))) if avg_score else 2
                ms_first_response = max(1000, min(10000, int(avg_time * 1000))) if avg_time else 5000
                duration = max(300, min(3000, int(avg_time))) if avg_time else 1200
                action_count = max(3, min(10, int(avg_score / 10))) if avg_score else 5
                hint_dependency = max(0, min(1, (100 - avg_score) / 100)) if avg_score else 0.3
                response_speed = max(0, min(1, avg_score / 100)) if avg_score else 0.6
                confidence_balance = max(0, min(1, (avg_score - 30) / 70)) if avg_score else 0.5
                engagement_ratio = max(0, min(1, avg_score / 100)) if avg_score else 0.7
                
                student_behavior = {
                    "hint_count": float(hint_count),
                    "bottom_hint": float(bottom_hint),
                    "attempt_count": float(attempt_count),
                    "ms_first_response": float(ms_first_response),
                    "duration": float(duration),
                    "action_count": float(action_count),
                    "hint_dependency": hint_dependency,
                    "response_speed": response_speed,
                    "confidence_balance": confidence_balance,
                    "engagement_ratio": engagement_ratio,
                    "avg_score": avg_score,
                    "avg_completion_time": avg_time
                }
        
        # Generate quiz questions
        result = quiz_generator_service.generate_quiz(
            topics=topics,
            difficulty=difficulty,
            n_questions=n_questions,
            question_type=question_type,
            include_explanations=include_explanations,
            student_behavior=student_behavior
        )
        
        if 'error' in result:
            return jsonify(result), 500
        
        # Store quiz generation in database for analytics
        try:
            from models import QuizGeneration
            generation = QuizGeneration(
                student_id=student_id,
                topics=json.dumps(topics),
                difficulty=difficulty,
                question_count=n_questions,
                question_type=question_type,
                api_used=result.get('metadata', {}).get('api_used', 'unknown'),
                response_time=result.get('metadata', {}).get('response_time', 0),
                is_csv_fallback=result.get('metadata', {}).get('is_csv_fallback', False)
            )
            db.session.add(generation)
            db.session.commit()
        except Exception as e:
            app.logger.error(f"Error storing quiz generation: {e}")
            db.session.rollback()
        
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"Error generating quiz: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/ai/suggestions')
@login_required
def get_ai_suggestions():
    """Get AI study suggestions with enhanced functionality"""
    topic = request.args.get('topic')
    context = request.args.get('context', '')
    
    if context:
        result = rag_tutor_service.ask_with_context(
            f"What are some good study suggestions for {topic or 'general learning'}?",
            context
        )
    else:
        result = rag_tutor_service.get_suggestions(topic)
    
    return jsonify(result)

@app.route('/api/ai/resources', methods=['POST'])
@login_required
def get_educational_resources():
    """Get educational resources for a specific topic"""
    try:
        data = request.get_json()
        topic = data.get('topic')
        
        if not topic:
            return jsonify({'error': 'Topic is required'}), 400
        
        result = rag_tutor_service.get_educational_resources(topic)
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"Error getting educational resources: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/ai/ask-context', methods=['POST'])
@login_required
def ask_ai_with_context():
    """Ask AI tutor with specific context"""
    try:
        data = request.get_json()
        question = data.get('question')
        context = data.get('context', '')
        max_tokens = data.get('max_tokens', 500)
        temperature = data.get('temperature', 0.7)
        
        if not question:
            return jsonify({'error': 'Question is required'}), 400
        
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401
        
        # Get AI response with context
        result = rag_tutor_service.ask_with_context(question, context, max_tokens)
        
        if 'error' in result:
            return jsonify(result), 500
        
        # Store interaction in database
        try:
            interaction = AIInteraction(
                user_id=user_id,
                question=question,
                answer=result.get('answer', ''),
                video_link=result.get('videoLink'),
                website_link=result.get('websiteLink'),
                processing_time=result.get('processingTime'),
                api_used=result.get('apiUsed'),
                confidence_score=result.get('confidence_score'),
                has_context=result.get('hasContext', False),
                suggestions=result.get('suggestions', []),
                context_sources=result.get('context_sources', [])
            )
            db.session.add(interaction)
            db.session.commit()
        except Exception as e:
            app.logger.error(f"Error storing AI interaction: {e}")
            db.session.rollback()
        
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"Error in contextual AI request: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/student/analytics')
@login_required
def get_student_analytics():
    """Get student analytics data for dashboard"""
    try:
        student_id = session.get('user_id')
        if not student_id:
            return jsonify({'error': 'User not authenticated'}), 401
        
        # Get student data
        student = Student.query.get(student_id)
        if not student:
            return jsonify({'error': 'Student not found'}), 404
        
        # Get recent quiz attempts
        recent_attempts = QuizAttempt.query.filter_by(student_id=student_id)\
            .order_by(QuizAttempt.completed_at.desc()).limit(10).all()
        
        # Get ML predictions
        ml_predictions = MLPrediction.query.filter_by(student_id=student_id)\
            .order_by(MLPrediction.created_at.desc()).limit(5).all()
        
        # Calculate analytics
        analytics_data = {
            'student_id': student_id,
            'total_attempts': len(recent_attempts),
            'recent_attempts': [{
                'id': attempt.id,
                'quiz_title': attempt.quiz.title if attempt.quiz else 'Unknown Quiz',
                'score': attempt.score,
                'completed_at': attempt.completed_at.isoformat() if attempt.completed_at else None
            } for attempt in recent_attempts],
            'ml_predictions': [{
                'id': pred.id,
                'predicted_score': pred.predicted_score,
                'category': pred.category,
                'confidence_level': pred.confidence_level,
                'created_at': pred.created_at.isoformat() if pred.created_at else None
            } for pred in ml_predictions]
        }
        
        return jsonify(analytics_data)
    except Exception as e:
        app.logger.error(f"Error getting student analytics: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/ai/interactions')
@login_required
def get_ai_interactions():
    """Get user's AI interaction history"""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'User not authenticated'}), 401
    
    interactions = AIInteraction.query.filter_by(user_id=user_id)\
        .order_by(AIInteraction.created_at.desc())\
        .limit(20).all()
    
    interaction_data = []
    for interaction in interactions:
        interaction_data.append({
            'id': interaction.id,
            'question': interaction.question,
            'answer': interaction.answer,
            'video_link': interaction.video_link,
            'website_link': interaction.website_link,
            'processing_time': interaction.processing_time,
            'api_used': interaction.api_used,
            'confidence_score': interaction.confidence_score,
            'suggestions': interaction.suggestions,
            'created_at': interaction.created_at.isoformat()
        })
    
    return jsonify({'interactions': interaction_data})

# ===================== AI CHAT ROUTES =====================

@app.route('/chat')
@login_required
def chat_interface():
    """AI tutor chat interface"""
    student = Student.query.get(session['user_id'])
    
    # Get or create chat session
    active_session = ChatSession.query.filter_by(
        student_id=student.id,
        ended_at=None
    ).first()
    
    if not active_session:
        active_session = ChatSession(student_id=student.id)
        db.session.add(active_session)
        db.session.commit()
    
    # Get chat history
    messages = ChatMessage.query.filter_by(
        session_id=active_session.id
    ).order_by(ChatMessage.timestamp).all()
    
    return render_template('chat.html', 
                         student=student, 
                         session=active_session,
                         messages=messages)

@app.route('/chat/send', methods=['POST'])
@login_required
def send_message():
    """Send message to external AI tutor API with enhanced context support"""
    data = request.get_json()
    message = data.get('message')
    context = data.get('context', '')
    session_id = data.get('session_id')
    
    if not message:
        return jsonify({'error': 'Empty message'}), 400
    
    chat_session = ChatSession.query.get(session_id)
    if not chat_session or chat_session.student_id != session['user_id']:
        return jsonify({'error': 'Invalid session'}), 403
    
    # Store student message with context
    student_message = ChatMessage(
        session_id=session_id,
        sender='student',
        message=message
    )
    db.session.add(student_message)
    
    # Get AI response from RAG tutor API with context
    ai_response_data = get_ai_response_with_rag(message, chat_session, context)
    
    # Store AI response
    ai_message = ChatMessage(
        session_id=session_id,
        sender='ai',
        message=ai_response_data.get('answer', 'I apologize, but I encountered an error. Please try again.'),
        confidence_score=ai_response_data.get('confidence_score'),
        response_time_ms=int(ai_response_data.get('processingTime', 0) * 1000) if ai_response_data.get('processingTime') else None
    )
    db.session.add(ai_message)
    db.session.commit()
    
    return jsonify({
        'student_message': message,
        'context': context,
        'ai_response': ai_response_data.get('answer', 'I apologize, but I encountered an error. Please try again.'),
        'video_link': ai_response_data.get('videoLink'),
        'website_link': ai_response_data.get('websiteLink'),
        'suggestions': ai_response_data.get('suggestions', []),
        'processing_time': ai_response_data.get('processingTime'),
        'api_used': ai_response_data.get('apiUsed'),
        'confidence_score': ai_response_data.get('confidence_score'),
        'has_context': ai_response_data.get('hasContext', False),
        'rag_context': ai_response_data.get('rag_context', ''),
        'context_sources': ai_response_data.get('context_sources', []),
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

def generate_intelligent_fallback(question, student):
    """Generate intelligent fallback responses when RAG API is unavailable"""
    question_lower = question.lower().strip()
    
    # Math questions
    if any(op in question_lower for op in ['+', '-', '*', '/', 'plus', 'minus', 'times', 'divided']):
        if '2+2' in question_lower:
            return "2 + 2 = 4. This is basic addition! When you add 2 and 2 together, you get 4. You can think of it as having 2 apples and getting 2 more apples - you'd have 4 apples total. Would you like me to explain any other basic math operations?"
        else:
            return f"I'd be happy to help with your math question: '{question}'. While I'm having some technical difficulties, I can still help you work through this step by step. Could you break down the problem for me, or would you like me to explain a specific math concept?"
    
    # Study guidance questions
    elif any(word in question_lower for word in ['study', 'learn', 'next', 'what should', 'recommend']):
        return f"Great question about what to study next! While I'm experiencing some technical issues, I can still help guide your learning. Based on your recent quiz activity, I'd recommend focusing on areas where you want to improve. What subjects or topics are you most interested in exploring? I can help you create a study plan!"
    
    # Quiz-related questions
    elif any(word in question_lower for word in ['quiz', 'test', 'exam', 'results', 'score']):
        return f"I'd love to help you understand your quiz results! While I'm having some connectivity issues, I can still provide guidance. Could you tell me more about which quiz you took and what specific aspects you'd like to understand better? I can help you analyze your performance and suggest areas for improvement."
    
    # General greeting
    elif any(word in question_lower for word in ['hi', 'hello', 'hey', 'hii']):
        return f"Hello {student.name if student else 'there'}! 👋 I'm your AI tutor, and I'm here to help you learn! While I'm experiencing some technical difficulties with my advanced features, I can still assist you with your studies. What would you like to learn about today?"
    
    # Default intelligent response
    else:
        return f"Thanks for your question: '{question}'. I'm currently experiencing some technical difficulties with my advanced AI features, but I'm still here to help you learn! Could you provide a bit more context about what you'd like to know? I can help you break down complex topics, explain concepts, or guide you to helpful resources."

def get_ai_response_with_rag(student_message, chat_session, context=""):
    """Generate AI tutor response using RAG tutor chatbot API with full integration"""
    try:
        # Get student context
        student = Student.query.get(chat_session.student_id)
        
        # Get recent quiz performance for context
        recent_attempts = QuizAttempt.query.filter_by(
            student_id=student.id,
            is_completed=True
        ).order_by(QuizAttempt.completed_at.desc()).limit(3).all()
        
        # Prepare enhanced context
        enhanced_context = context
        if recent_attempts:
            recent_topics = [attempt.quiz.topic for attempt in recent_attempts if attempt.quiz and attempt.quiz.topic]
            if recent_topics:
                if enhanced_context:
                    enhanced_context += f" (Recent quiz topics: {', '.join(set(recent_topics))})"
                else:
                    enhanced_context = f"Recent quiz topics: {', '.join(set(recent_topics))}"
        
        # Call RAG tutor service with context
        result = rag_tutor_service.ask_question(student_message, enhanced_context)
        
        if 'error' in result:
            app.logger.error(f"RAG API error: {result['error']}")
            # Return intelligent fallback response based on the question
            fallback_answer = generate_intelligent_fallback(student_message, student)
            return {
                'answer': fallback_answer,
                'error': result['error'],
                'videoLink': None,
                'websiteLink': None,
                'suggestions': [],
                'processingTime': 0,
                'apiUsed': 'fallback',
                'confidence_score': 0.1
            }
        
        # Store the interaction in database
        try:
            interaction = AIInteraction(
                user_id=student.id,
                question=student_message,
                answer=result.get('answer', ''),
                video_link=result.get('videoLink'),
                website_link=result.get('websiteLink'),
                processing_time=result.get('processingTime'),
                api_used=result.get('apiUsed'),
                confidence_score=result.get('confidence_score'),
                has_context=result.get('hasContext', False),
                suggestions=result.get('suggestions', []),
                context_sources=result.get('context_sources', [])
            )
            db.session.add(interaction)
            db.session.commit()
            app.logger.info(f"Stored AI interaction for user {student.id}")
        except Exception as e:
            app.logger.error(f"Error storing AI interaction: {e}")
            db.session.rollback()
        
        return result
        
    except Exception as e:
        app.logger.error(f"Unexpected error in get_ai_response_with_rag: {e}")
        return {
            'answer': "I encountered an unexpected issue. Please try asking your question again!",
            'error': str(e),
            'videoLink': None,
            'websiteLink': None,
            'suggestions': [],
            'processingTime': 0,
            'apiUsed': 'error',
            'confidence_score': 0.0
        }

@app.route('/chat/clear-history', methods=['POST'])
@login_required
def clear_chat_history():
    """Clear chat history for the current session"""
    data = request.get_json()
    session_id = data.get('session_id')
    
    if not session_id:
        return jsonify({'success': False, 'error': 'Session ID required'}), 400
    
    try:
        # Verify session belongs to current user
        chat_session = ChatSession.query.get(session_id)
        if not chat_session or chat_session.student_id != session['user_id']:
            return jsonify({'success': False, 'error': 'Invalid session'}), 403
        
        # Delete all messages in this session
        ChatMessage.query.filter_by(session_id=session_id).delete()
        
        # Also clear AI interactions for this user (optional - you might want to keep these for analytics)
        # AIInteraction.query.filter_by(user_id=session['user_id']).delete()
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Chat history cleared successfully'})
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error clearing chat history: {e}")
        return jsonify({'success': False, 'error': 'Failed to clear chat history'}), 500

@app.route('/progress')
@login_required
def view_progress():
    """Student progress view"""
    student_id = session['user_id']
    student = db.session.get(Student, student_id)
    
    # Get all completed attempts
    attempts = QuizAttempt.query.filter_by(
        student_id=student_id,
        is_completed=True
    ).order_by(QuizAttempt.completed_at.desc()).all()
    
    # Calculate stats
    total_quizzes = len(attempts)
    average_score = sum(attempt.score for attempt in attempts if attempt.score) / total_quizzes if total_quizzes > 0 else 0
    
    # Calculate progress trend
    progress_trend = 0
    if len(attempts) >= 2:
        recent_scores = [attempt.score for attempt in attempts[:3] if attempt.score]
        older_scores = [attempt.score for attempt in attempts[3:6] if attempt.score]
        if recent_scores and older_scores:
            recent_avg = sum(recent_scores) / len(recent_scores)
            older_avg = sum(older_scores) / len(older_scores)
            progress_trend = recent_avg - older_avg
    
    # Get current recommendations
    current_recommendations = []
    if attempts:
        latest_score = attempts[0].score if attempts[0].score else 0
        if latest_score < 60:
            current_recommendations = [
                "Review fundamental concepts before attempting new quizzes",
                "Practice with easier questions to build confidence",
                "Use the chat feature to get help with difficult topics"
            ]
        elif latest_score < 80:
            current_recommendations = [
                "Focus on areas where you scored lowest",
                "Try more challenging quizzes to improve further",
                "Review incorrect answers to understand mistakes"
            ]
        else:
            current_recommendations = [
                "Excellent work! Try advanced level quizzes",
                "Help other students to reinforce your knowledge",
                "Explore new subject areas to expand learning"
            ]
    else:
        current_recommendations = [
            "Start with a beginner-level quiz to establish your baseline",
            "Take quizzes regularly to track your progress",
            "Use the chat feature if you need help with any topics"
        ]

    return render_template('progress.html',
                         student=student,
                         attempts=attempts,
                         total_quizzes=total_quizzes,
                         average_score=average_score,
                         progress_trend=progress_trend,
                         current_recommendations=current_recommendations)

@app.route('/student_profile')
@login_required  
def student_profile():
    """Comprehensive student profile with ML insights"""
    student_id = session['user_id']
    student = db.session.get(Student, student_id)
    
    # Get student profile or create if doesn't exist
    from models import StudentProfile, MLPrediction
    profile = StudentProfile.query.filter_by(student_id=student_id).first()
    if not profile:
        profile = StudentProfile(student_id=student_id)
        db.session.add(profile)
        db.session.commit()
    
    # Get recent quiz attempts for analysis
    recent_attempts = QuizAttempt.query.filter_by(
        student_id=student_id,
        is_completed=True
    ).order_by(QuizAttempt.completed_at.desc()).limit(10).all()
    
    # Get latest ML predictions
    latest_predictions = MLPrediction.query.filter_by(
        student_id=student_id
    ).order_by(MLPrediction.created_at.desc()).limit(5).all()
    
    # Calculate performance trends
    performance_data = []
    for attempt in reversed(recent_attempts[-10:]):  # Last 10 attempts chronologically
        performance_data.append({
            'quiz_title': attempt.quiz.title if attempt.quiz else 'Unknown Quiz',
            'score': attempt.score,
            'date': attempt.completed_at.strftime('%m/%d') if attempt.completed_at else 'N/A',
            'topic': attempt.quiz.topic if attempt.quiz else 'General'
        })
    
    # Get learning recommendations
    active_recommendations = StudentRecommendation.query.filter_by(
        student_id=student_id,
        is_active=True,
        is_completed=False
    ).order_by(StudentRecommendation.priority.asc()).limit(5).all()
    
    # Calculate learning statistics
    total_quizzes = len(QuizAttempt.query.filter_by(student_id=student_id, is_completed=True).all())
    average_score = sum(attempt.score for attempt in recent_attempts if attempt.score) / len(recent_attempts) if recent_attempts else 0
    improvement_rate = calculate_improvement_rate(recent_attempts)
    
    # Get learner profile from latest prediction
    learner_profile_data = None
    behavioral_insights = None
    if latest_predictions:
        try:
            latest_pred = latest_predictions[0]
            if hasattr(latest_pred, 'learner_profile_json') and latest_pred.learner_profile_json:
                learner_profile_data = json.loads(latest_pred.learner_profile_json)
                
            if hasattr(latest_pred, 'features_json') and latest_pred.features_json:
                behavioral_insights = json.loads(latest_pred.features_json)
        except (json.JSONDecodeError, AttributeError):
            pass
    
    return render_template('student_profile.html',
                         student=student,
                         profile=profile,
                         recent_attempts=recent_attempts,
                         latest_predictions=latest_predictions,
                         performance_data=performance_data,
                         active_recommendations=active_recommendations,
                         total_quizzes=total_quizzes,
                         average_score=average_score,
                         improvement_rate=improvement_rate,
                         learner_profile_data=learner_profile_data,
                         behavioral_insights=behavioral_insights)

def calculate_improvement_rate(attempts):
    """Calculate improvement rate based on recent attempts"""
    if len(attempts) < 3:
        return 0
    
    # Compare first half vs second half of recent attempts
    mid_point = len(attempts) // 2
    first_half_avg = sum(a.score for a in attempts[mid_point:] if a.score) / (len(attempts) - mid_point)
    second_half_avg = sum(a.score for a in attempts[:mid_point] if a.score) / mid_point
    
    return ((first_half_avg - second_half_avg) / second_half_avg) * 100 if second_half_avg > 0 else 0

# ===================== API ROUTES =====================

@app.route('/api/quiz/<int:quiz_id>/preview')
def api_quiz_preview(quiz_id):
    """API endpoint to get quiz preview data"""
    try:
        quiz = db.session.get(Quiz, quiz_id)
        if not quiz or not quiz.is_active:
            return jsonify({'success': False, 'message': 'Quiz not found'})
        
        quiz_data = {
            'id': quiz.id,
            'title': quiz.title,
            'description': quiz.description,
            'topic': quiz.topic,
            'difficulty': quiz.difficulty
        }
        
        return jsonify({'success': True, 'quiz': quiz_data})
        
    except Exception as e:
        app.logger.error(f"Error in quiz preview: {e}")
        return jsonify({'success': False, 'message': 'Internal server error'})

# Health check endpoint for deployment monitoring
@app.route('/health')
def health_check():
    """Simple health check endpoint for deployment monitoring"""
    try:
        # Test database connection
        db.session.execute('SELECT 1')
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"
    
    return jsonify({
        'status': 'healthy',
        'database': db_status,
        'app': 'Educational Platform',
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    print("Educational Platform starting...")
    print("✅ External AI Tutor API integrated")
    print("🌐 Chatbot API: https://rag-tutor-chatbot.onrender.com/")
    print("🚀 Access your app at: http://127.0.0.1:5001")
    
    app.run(debug=True, port=5001)
else:
    # This runs when deployed (via gunicorn)
    with app.app_context():
        db.create_all()
