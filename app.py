# app.py - Educational Platform with External AI Tutor Integration
import logging
import requests
import json
from typing import Dict, Any, Optional, List, cast
from datetime import datetime, timedelta
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
from typing import List, Optional, Any
db.init_app(app)

# Import quiz generation API integration first
from quiz_api_integration_with_fallback import QuizGenerationAPI

# Import models
from models import (
    Student, Quiz, QuizAttempt, ChatSession, ChatMessage, 
    StudentRecommendation, Question, QuestionOption,
    StudentProfile, MLPrediction, Topic
)

# Initialize quiz API globally
quiz_api = QuizGenerationAPI()

def get_quiz_questions(quiz_id: int) -> List[Question]:
    """Helper function to get questions for a quiz with explicit Question model usage"""
    questions = Question.query.filter_by(quiz_id=quiz_id).order_by(Question.order_index).all()
    # Explicitly using Question model type to resolve Pylance warning
    return questions

# Template filters
@app.template_filter('chr')
def chr_filter(number, offset=64):
    """Convert number to letter (1->A, 2->B, etc.)"""
    return chr(number + offset)

@app.template_filter('from_json')
def from_json_filter(value):
    """Convert JSON string to Python object"""
    import json
    return json.loads(value)

# Add built-in 'abs' function to Jinja2 environment
app.jinja_env.globals['abs'] = abs

# ===================== SECURITY DECORATORS =====================

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ===================== ERROR HANDLERS =====================

@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500

@app.errorhandler(403)
def forbidden_error(error):
    return render_template('errors/403.html'), 403

# ===================== ML API INTEGRATION FUNCTIONS =====================

def call_ml_api_for_prediction(attempt, student_id):
    """Call the ML API to get student performance prediction"""
    try:
        # Prepare data for ML API based on quiz attempt
        responses = json.loads(attempt.responses_json or '{}')
        
        # Calculate quiz metrics
        hint_count = session.get('hints_used', 0)
        bottom_hint = 1 if hint_count > 0 else 0
        attempt_count = len(responses)  # Number of questions answered
        
        # Calculate timing metrics
        timing_data = json.loads(attempt.timing_data_json or '{}') if hasattr(attempt, 'timing_data_json') else {}
        ms_first_response = timing_data.get('first_response_time', 5000)  # Default 5 seconds
        duration = timing_data.get('total_duration', 300000)  # Default 5 minutes
        
        # Mock confidence levels (you can replace with real data)
        avg_conf_frustrated = 0.2
        avg_conf_confused = 0.3  
        avg_conf_concentrating = 0.7
        avg_conf_bored = 0.1
        
        # Prepare API payload
        api_data = {
            "hint_count": float(hint_count),
            "bottom_hint": float(bottom_hint),
            "attempt_count": float(attempt_count),
            "ms_first_response": float(ms_first_response),
            "duration": float(duration),
            "avg_conf_frustrated": avg_conf_frustrated,
            "avg_conf_confused": avg_conf_confused,
            "avg_conf_concentrating": avg_conf_concentrating,
            "avg_conf_bored": avg_conf_bored
        }
        
        # Call ML API
        ml_api_url = "https://ml-api-pz1u.onrender.com/predict"
        response = requests.post(
            ml_api_url,
            json=api_data,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status_code == 200:
            prediction_data = response.json()
            app.logger.info(f"ML API prediction successful for student {student_id}")
            return prediction_data
        else:
            app.logger.error(f"ML API returned status {response.status_code}: {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        app.logger.error("ML API request timed out")
        return None
    except requests.exceptions.RequestException as e:
        app.logger.error(f"ML API request failed: {e}")
        return None
    except Exception as e:
        app.logger.error(f"Error calling ML API: {e}")
        return None

def store_ml_prediction(student_id, attempt_id, prediction_data):
    """Store ML prediction data in the database"""
    try:
        prediction = MLPrediction(
            student_id=student_id,
            quiz_attempt_id=attempt_id,
            predicted_score=prediction_data['prediction']['correctness_score'],
            category=prediction_data['prediction']['performance_category'],
            confidence_level=prediction_data.get('confidence_level', 0.8),
            learner_profile_json=json.dumps(prediction_data.get('learner_profile', {})),
            features_json=json.dumps(prediction_data.get('behaviors', {})),
            model_version="v1.0",
            created_at=datetime.utcnow()
        )
        
        db.session.add(prediction)
        db.session.commit()
        
        app.logger.info(f"ML prediction stored for student {student_id}")
        
    except Exception as e:
        app.logger.error(f"Error storing ML prediction: {e}")
        db.session.rollback()

def update_student_profile_with_ml_data(student_id, prediction_data):
    """Update student profile with ML insights"""
    try:
        from models import StudentProfile
        
        profile = StudentProfile.query.filter_by(student_id=student_id).first()
        if not profile:
            profile = StudentProfile(student_id=student_id)
            db.session.add(profile)
        
        # Update profile with ML insights
        prediction = prediction_data.get('prediction', {})
        behaviors = prediction_data.get('behaviors', {})
        
        profile.predicted_category = prediction.get('performance_category', 'General Learner')
        profile.confidence_level = prediction.get('correctness_score', 0.5)
        profile.last_prediction_update = datetime.utcnow()
        profile.learner_profile_json = json.dumps(prediction_data)
        
        # Update learning style based on behaviors
        if behaviors.get('engagement') == 'High' and behaviors.get('efficiency') == 'High':
            profile.learning_style = 'Active Learner'
        elif behaviors.get('hint_dependency') == 'High':
            profile.learning_style = 'Guided Learner'
        elif behaviors.get('persistence') == 'High':
            profile.learning_style = 'Persistent Learner'
        else:
            profile.learning_style = 'Adaptive Learner'
        
        # Generate recommendations based on ML insights
        generate_ml_based_recommendations(student_id, prediction_data)
        
        db.session.commit()
        app.logger.info(f"Student profile updated with ML data for student {student_id}")
        
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
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow().replace(hour=23, minute=59, second=59) + timedelta(days=30)
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
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow().replace(hour=23, minute=59, second=59) + timedelta(days=21)
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
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow().replace(hour=23, minute=59, second=59) + timedelta(days=14)
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
    """Student dashboard"""
    student_id = session['user_id']
    student = db.session.get(Student, student_id)
    
    # Get recent quiz attempts
    recent_quizzes = QuizAttempt.query.filter_by(
        student_id=student_id,
        is_completed=True
    ).order_by(QuizAttempt.completed_at.desc()).limit(5).all()
    
    return render_template('dashboard.html',
                         student=student,
                         recent_quizzes=recent_quizzes)

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
        started_at=datetime.utcnow()
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
    questions = json.loads(quiz.questions_json) if quiz.questions_json else []

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
    
    # Debug logging
    print(f"DEBUG: Question {question_num}, Answer received: '{answer}'")
    print(f"DEBUG: Form data: {dict(request.form)}")
    
    responses = json.loads(attempt.responses_json or '{}')
    responses[f'question_{question_num}'] = {
        'answer': answer,
        'confidence': confidence,
        'timestamp': datetime.utcnow().isoformat()
    }
    attempt.responses_json = json.dumps(responses)
    
    db.session.commit()
    
    # Check if last question
    quiz = db.session.get(Quiz, attempt.quiz_id)
    questions = json.loads(quiz.questions_json) if quiz.questions_json else []
    
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
    
    # Mark as completed
    attempt.completed_at = datetime.utcnow()
    attempt.is_completed = True
    
    # Calculate score
    responses = json.loads(attempt.responses_json or '{}')
    quiz = db.session.get(Quiz, attempt.quiz_id)
    questions = json.loads(quiz.questions_json) if quiz.questions_json else []
    
    correct_answers = 0
    detailed_analysis = []
    
    for i, question in enumerate(questions, 1):
        response = responses.get(f'question_{i}', {})
        user_answer = response.get('answer', '')
        
        # Get correct answer - handle different API response formats
        correct_answer = None
        if 'correct_answer' in question:
            correct_answer = question['correct_answer']
        elif 'options' in question:
            # Find correct answer from options
            for option in question['options']:
                if option.get('is_correct', False):
                    correct_answer = option.get('text', option.get('option_text', ''))
                    break
        
        is_correct = False
        if correct_answer and user_answer:
            # Handle both letter answers (A, B, C, D) and full text answers
            if len(user_answer) == 1 and user_answer.upper() in 'ABCD':
                # Convert letter to option text
                option_index = ord(user_answer.upper()) - ord('A')
                if 'options' in question and option_index < len(question['options']):
                    user_answer_text = question['options'][option_index].get('text', question['options'][option_index].get('option_text', ''))
                    is_correct = user_answer_text == correct_answer
            else:
                # Direct text comparison
                is_correct = user_answer.strip().lower() == correct_answer.strip().lower()
        
        if is_correct:
            correct_answers += 1
            
        # Store detailed analysis
        detailed_analysis.append({
            'question': question.get('question', question.get('question_text', f'Question {i}')),
            'user_answer': user_answer,
            'correct_answer': correct_answer or 'Not available',
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
    questions = json.loads(quiz.questions_json) if quiz.questions_json else []
    
    for i, question in enumerate(questions, 1):
        response = responses.get(f'question_{i}', {})
        user_answer = response.get('answer', 'No answer provided')
        
        # Try to get correct answer
        correct_answer = 'Not available'
        if 'correct_answer' in question:
            correct_answer = question['correct_answer']
        elif 'options' in question:
            for option in question['options']:
                if option.get('is_correct', False):
                    correct_answer = option.get('text', option.get('option_text', ''))
                    break
        
        # Simple correctness check
        is_correct = user_answer == correct_answer
        
        question_analysis.append({
            'question': question.get('question', question.get('question_text', f'Question {i}')),
            'user_answer': user_answer,
            'correct_answer': correct_answer,
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
        print(f"Error saving recommendations: {e}")
        # Return empty list if saving fails
        return []

@app.route('/recommendation/<int:rec_id>/complete', methods=['POST'])
@login_required
def complete_recommendation(rec_id):
    """Mark a recommendation as completed"""
    recommendation = db.session.get(StudentRecommendation, rec_id)
    
    if recommendation and recommendation.student_id == session['user_id']:
        recommendation.is_completed = True
        recommendation.completed_at = datetime.utcnow()
        db.session.commit()
        flash('Recommendation marked as completed!', 'success')
    else:
        flash('Recommendation not found or access denied.', 'error')
    
    return redirect(request.referrer or url_for('dashboard'))

# ===================== QUIZ GENERATION ROUTES =====================

@app.route('/quiz/generate')
@login_required
def quiz_generation_form():
    """Display quiz generation form"""
    return render_template('generate_quiz.html')

@app.route('/quiz/generate', methods=['POST'])
@login_required
def generate_quiz():
    """Generate a quiz using the external API with error handling"""
    try:
        topic: str = request.form.get('topic', '')
        difficulty: str = request.form.get('difficulty', 'medium')
        try:
            num_questions: int = int(request.form.get('num_questions', '5'))
        except (ValueError, TypeError):
            num_questions = 5
            app.logger.warning('Invalid num_questions value, using default of 5')
        
        if not topic:
            flash('Topic is required for quiz generation')
            return render_template('generate_quiz.html')
    
        # Get student behavioral data for personalization
        student_id: int = session.get('user_id')
        if not student_id:
            flash('Please log in to generate a quiz')
            return redirect(url_for('login'))
            
        recent_attempts = QuizAttempt.query.filter_by(
            student_id=student_id,
            is_completed=True
        ).order_by(QuizAttempt.completed_at.desc()).limit(3).all()
        
        # Analyze student behavior for API personalization
        student_data = None
        try:
            if recent_attempts:
                student_data = quiz_api.analyze_student_behavior(recent_attempts[0])
        except Exception as e:
            app.logger.error(f"Error analyzing student behavior: {e}")
            # Continue without student data
        # Extract grade level from topic if possible
        grade_level = None
        topic_lower = topic.lower()
        if "grade" in topic_lower:
            grade_level = next((str(i) for i in range(1, 13) if str(i) in topic_lower), None)
        elif "class" in topic_lower:
            grade_level = next((str(i) for i in range(1, 13) if str(i) in topic_lower), None)

        # Generate quiz through the API (it will use CSV fallback automatically)
        generation_result = quiz_api.generate_quiz(topic, difficulty, num_questions, student_data)
        
        if not generation_result.get('success'):
            flash(generation_result.get('message', 'Failed to generate quiz'))
            return redirect(url_for('quiz_selection'))
        
        quiz_data = cast(Dict[str, Any], generation_result.get('quiz', {}))
        
        if not isinstance(quiz_data, dict) or 'questions' not in quiz_data:
            flash('Invalid quiz data received')
            return redirect(url_for('quiz_selection'))
        
        try:
            # Create new Quiz object with appropriate fields
            new_quiz = Quiz()
            new_quiz.title = str(f"{topic} Quiz - {difficulty.title()}")
            new_quiz.description = str(f"Quiz from question bank on {topic}")
            new_quiz.topic = str(topic)
            new_quiz.difficulty = str(difficulty)
            new_quiz.content_source_type = "csv"
            new_quiz.content_source_data = json.dumps({"topic": topic, "difficulty": difficulty})
            new_quiz.is_active = True
            new_quiz.time_limit = 60  # Default 60 minutes
            new_quiz.questions_json = json.dumps(quiz_data['questions'])
            new_quiz.max_score = 100
            
            db.session.add(new_quiz)
            db.session.commit()
            
            flash(f'Quiz created successfully! {len(quiz_data.get("questions", []))} questions on {topic}')
            return redirect(url_for('start_quiz', quiz_id=new_quiz.id))
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error creating quiz: {e}")
            flash(f'Error creating quiz: {str(e)}')
            return redirect(url_for('quiz_selection'))
        
    except Exception as e:
        app.logger.error(f"Error creating quiz: {str(e)}")
        flash(f"Failed to create quiz: {str(e)}")
        return render_template('generate_quiz.html', 
                             error="Failed to create quiz from question bank",
                             topic=topic,
                             difficulty=difficulty,
                             num_questions=num_questions)

@app.route('/quiz/hint/<int:quiz_id>/<int:question_num>')
@login_required
def get_quiz_hint(quiz_id, question_num):
    """Get a hint for a specific quiz question"""
    # Get current quiz attempt
    attempt_id = session.get('current_attempt')
    if not attempt_id:
        return jsonify({'error': 'No active quiz attempt'}), 400
    
    attempt = db.session.get(QuizAttempt, attempt_id)
    if not attempt or attempt.quiz_id != quiz_id:
        return jsonify({'error': 'Invalid quiz attempt'}), 400
    
    # Get the quiz and question
    quiz = db.session.get(Quiz, quiz_id)
    if not quiz:
        return jsonify({'error': 'Quiz not found'}), 404
    
    questions = json.loads(quiz.questions_json or '[]')
    if question_num > len(questions):
        return jsonify({'error': 'Question not found'}), 404
    
    question = questions[question_num - 1]
    question_text = question.get('question', '')
    
    # Track hint usage
    hints_used = getattr(attempt, 'hints_used', 0)
    attempt.hints_used = hints_used + 1
    
    # Determine hint level (1-3 based on how many hints already used)
    hint_level = min(3, (hints_used % 3) + 1)
    
    # Get student behavioral data
    student_data = quiz_api.analyze_student_behavior(attempt)
    
    # Generate hint using external API
    hint_result = quiz_api.generate_hint(
        question_text=question_text,
        student_data=student_data,
        hint_level=hint_level
    )
    
    # Save hint usage to database
    db.session.commit()
    
    return jsonify({
        'hint': hint_result['hint'],
        'hint_level': hint_level,
        'hints_used': attempt.hints_used,
        'success': hint_result['success']
    })

@app.route('/api/quiz/health')
def quiz_api_health():
    """Check quiz generation API health"""
    health = quiz_api.check_api_health()
    return jsonify(health)

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
    """Send message to external AI tutor API"""
    data = request.get_json()
    message = data.get('message')
    session_id = data.get('session_id')
    
    if not message:
        return jsonify({'error': 'Empty message'}), 400
    
    chat_session = ChatSession.query.get(session_id)
    if not chat_session or chat_session.student_id != session['user_id']:
        return jsonify({'error': 'Invalid session'}), 403
    
    # Store student message
    student_message = ChatMessage(
        session_id=session_id,
        sender='student',
        message=message
    )
    db.session.add(student_message)
    
    # Get AI response from external API
    ai_response = get_ai_response(message, chat_session)
    
    # Store AI response
    ai_message = ChatMessage(
        session_id=session_id,
        sender='ai',
        message=ai_response
    )
    db.session.add(ai_message)
    db.session.commit()
    
    return jsonify({
        'student_message': message,
        'ai_response': ai_response,
        'timestamp': datetime.utcnow().isoformat()
    })

def get_ai_response(student_message, chat_session):
    """Generate AI tutor response using external RAG tutor chatbot API"""
    try:
        # Get student context
        student = Student.query.get(chat_session.student_id)
        
        # Get recent quiz performance for context
        recent_attempts = QuizAttempt.query.filter_by(
            student_id=student.id,
            is_completed=True
        ).order_by(QuizAttempt.completed_at.desc()).limit(3).all()
        
        # Prepare context for the external API
        context = {
            "student_name": student.name if student else "Student",
            "recent_quiz_count": len(recent_attempts),
            "average_score": None
        }
        
        # Calculate average score if there are recent attempts
        if recent_attempts:
            scores = [attempt.score for attempt in recent_attempts if attempt.score is not None]
            if scores:
                context["average_score"] = sum(scores) / len(scores)
        
        # Prepare the request - the API expects 'question' not 'message'
        params = {
            "question": student_message
        }
        
        # Call the external RAG tutor chatbot API
        api_url = "https://rag-tutor-chatbot.onrender.com/api/chat"
        
        response = requests.get(
            api_url, 
            params=params,
            timeout=30
        )
        
        if response.status_code == 200:
            response_data = response.json()
            # The API might return different response structure
            return response_data.get("answer", response_data.get("response", "I'm here to help you learn! Could you please rephrase your question?"))
        else:
            # Fallback response if API fails
            return f"I'm having trouble connecting to my knowledge base right now, but I'm still here to help you, {context['student_name']}! Could you try asking your question again?"
            
    except requests.exceptions.Timeout:
        return "I'm taking a bit longer to think about your question. Could you please try asking again?"
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error calling external API: {e}")
        return "I'm having some technical difficulties right now, but I'm still here to help! Please try your question again."
    except Exception as e:
        app.logger.error(f"Unexpected error in get_ai_response: {e}")
        return "I encountered an unexpected issue. Please try asking your question again!"

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
