# app.py - Main Flask application
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from extensions import db, make_celery
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
import json
import os
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import pickle
from dotenv import load_dotenv

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
db.init_app(app)
celery = make_celery(app)

# Configure logging
import logging
if not app.debug:
    logging.basicConfig(level=logging.INFO)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Educational Platform startup')

# Import your ML components AFTER app initialization
from ml_predictor import LearningAnalytics, RecommendationEngine
from models import Student, StudentProfile, Topic, Quiz, QuizAttempt, MLPrediction, StudentRecommendation, MLDataManager

# Initialize ML components
ml_analytics = LearningAnalytics()
recommendation_engine = RecommendationEngine()

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

def validate_user_access(f):
    """Decorator to validate user has access to requested resource"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        # Additional validation can be added here
        user = db.session.get(Student, session['user_id'])
        if not user:
            session.clear()
            flash('Invalid session. Please log in again.', 'error')
            return redirect(url_for('login'))
            
        return f(*args, **kwargs)
    return decorated_function

# ===================== EXISTING CORE ROUTES =====================

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
        
        # Validate required fields
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
def dashboard():
    """Enhanced dashboard with ML recommendations"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    student_id = session['user_id']
    student = db.session.get(Student, student_id)
    
    # Get recent activities
    recent_quizzes = QuizAttempt.query.filter_by(
        student_id=student_id,
        is_completed=True
    ).order_by(QuizAttempt.completed_at.desc()).limit(5).all()
    
    # Get personalized recommendations
    active_recommendations = StudentRecommendation.query.filter_by(
        student_id=student_id,
        is_active=True
    ).order_by(StudentRecommendation.priority).limit(3).all()
    
    # Get student profile for personalization
    profile = StudentProfile.query.filter_by(student_id=student_id).first()
    
    # Get recommended topics based on ML insights
    recommended_difficulty = 'medium'  # default
    if profile and profile.predicted_category:
        if profile.predicted_category == 'struggling':
            recommended_difficulty = 'easy'
        elif profile.predicted_category == 'advanced':
            recommended_difficulty = 'hard'
    
    recommended_topics = Topic.query.filter_by(difficulty_level=recommended_difficulty).limit(3).all()
    
    return render_template('dashboard.html',
                         student=student,
                         recent_quizzes=recent_quizzes,
                         active_recommendations=active_recommendations,
                         recommended_topics=recommended_topics,
                         profile=profile)

@app.route('/quiz')
def quiz_selection():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('quiz_selection.html')

@app.route('/quiz/<int:quiz_id>')
def start_quiz(quiz_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
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
def quiz_question(question_num):
    if 'user_id' not in session or 'current_attempt' not in session:
        return redirect(url_for('login'))
    
    attempt_id = session['current_attempt']
    attempt = db.session.get(QuizAttempt, attempt_id)
    
    if not attempt:
        flash('Quiz session not found')
        return redirect(url_for('quiz_selection'))
    
    quiz = db.session.get(Quiz, attempt.quiz_id)
    questions = json.loads(quiz.questions_json)
    
    if question_num > len(questions):
        return redirect(url_for('complete_quiz'))
    
    current_question = questions[question_num - 1]
    
    return render_template('quiz_question.html',
                         question=current_question,
                         question_num=question_num,
                         total_questions=len(questions),
                         quiz=quiz)

# ===================== QUIZ SUBMISSION & ML INTEGRATION ROUTES =====================

@app.route('/quiz/submit/<int:question_num>', methods=['POST'])
def submit_answer(question_num):
    """Handle quiz answer submission with ML feature tracking"""
    if 'user_id' not in session or 'current_attempt' not in session:
        return redirect(url_for('login'))
    
    attempt_id = session['current_attempt']
    attempt = db.session.get(QuizAttempt, attempt_id)
    
    # Get form data
    answer = request.form.get('answer')
    confidence = float(request.form.get('confidence', 0.5))
    hints_used_this_question = int(request.form.get('hints_used', 0))
    time_spent = float(request.form.get('time_spent', 0))
    
    # Update attempt with ML features
    attempt.hints_used = (attempt.hints_used or 0) + hints_used_this_question
    attempt.reached_final_hint = request.form.get('reached_final_hint') == 'true'
    
    # Store timing data
    timing_data = json.loads(attempt.timing_data_json or '{}')
    timing_data[f'question_{question_num}'] = {
        'time_spent': time_spent,
        'confidence': confidence,
        'hints_used': hints_used_this_question
    }
    attempt.timing_data_json = json.dumps(timing_data)
    
    # Set time to first answer if this is first question
    if question_num == 1 and not attempt.time_to_first_answer:
        attempt.time_to_first_answer = time_spent
    
    # Store responses
    responses = json.loads(attempt.responses_json or '{}')
    responses[f'question_{question_num}'] = {
        'answer': answer,
        'confidence': confidence,
        'timestamp': datetime.utcnow().isoformat()
    }
    attempt.responses_json = json.dumps(responses)
    
    db.session.commit()
    
    # Check if this is the last question
    quiz = db.session.get(Quiz, attempt.quiz_id)
    questions = json.loads(quiz.questions_json)
    
    if question_num >= len(questions):
        return redirect(url_for('complete_quiz'))
    else:
        return redirect(url_for('quiz_question', question_num=question_num + 1))

@app.route('/quiz/complete')
def complete_quiz():
    """Complete quiz and trigger ML prediction pipeline"""
    if 'user_id' not in session or 'current_attempt' not in session:
        return redirect(url_for('login'))
    
    attempt_id = session['current_attempt']
    attempt = db.session.get(QuizAttempt, attempt_id)
    
    # Mark as completed
    attempt.completed_at = datetime.utcnow()
    attempt.is_completed = True
    
    # Calculate final score and confidence
    responses = json.loads(attempt.responses_json or '{}')
    confidences = []
    correct_answers = 0
    
    quiz = db.session.get(Quiz, attempt.quiz_id)
    questions = json.loads(quiz.questions_json)
    
    for i, question in enumerate(questions, 1):
        response = responses.get(f'question_{i}', {})
        if response.get('answer') == question.get('correct_answer'):
            correct_answers += 1
        if 'confidence' in response:
            confidences.append(response['confidence'])
    
    attempt.score = (correct_answers / len(questions)) * 100 if questions else 0
    attempt.average_confidence = sum(confidences) / len(confidences) if confidences else 0.5
    
    db.session.commit()
    
    # Trigger ML prediction pipeline
    try:
        prediction_result = ml_analytics.predict_performance(attempt)
        
        # Save prediction to database
        ml_prediction = MLDataManager.save_prediction(attempt_id, prediction_result)
        
        # Generate and save recommendations
        recommendations = recommendation_engine.generate_recommendations(
            prediction_result, 
            session['user_id']
        )
        
        MLDataManager.save_recommendations(
            session['user_id'], 
            attempt_id, 
            recommendations
        )
        
        # Update student profile
        MLDataManager.update_student_profile(session['user_id'], prediction_result)
        
        # Clear current attempt from session
        session.pop('current_attempt', None)
        
        # Redirect to results with ML insights
        return redirect(url_for('quiz_results', attempt_id=attempt_id))
        
    except Exception as e:
        # Log error but don't break user experience
        app.logger.error(f"ML prediction failed: {str(e)}")
        session.pop('current_attempt', None)
        flash('Quiz completed! Some advanced features may be temporarily unavailable.')
        return redirect(url_for('quiz_results', attempt_id=attempt_id))

@app.route('/quiz/results/<int:attempt_id>')
def quiz_results(attempt_id):
    """Display quiz results with ML insights and recommendations"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    attempt = db.session.get(QuizAttempt, attempt_id)
    
    # Verify this attempt belongs to current user
    if attempt.student_id != session['user_id']:
        flash('Access denied.')
        return redirect(url_for('dashboard'))
    
    # Get ML prediction and recommendations
    ml_prediction = MLPrediction.query.filter_by(quiz_attempt_id=attempt_id).first()
    recommendations = StudentRecommendation.query.filter_by(
        student_id=session['user_id'],
        quiz_attempt_id=attempt_id,
        is_active=True
    ).all()
    
    # Get quiz details
    quiz = db.session.get(Quiz, attempt.quiz_id)
    topic = db.session.get(Topic, quiz.topic_id) if quiz else None
    
    # Parse responses for detailed breakdown
    responses = json.loads(attempt.responses_json or '{}')
    questions = json.loads(quiz.questions_json) if quiz else []
    
    question_analysis = []
    for i, question in enumerate(questions, 1):
        response = responses.get(f'question_{i}', {})
        question_analysis.append({
            'question': question.get('question', ''),
            'correct_answer': question.get('correct_answer', ''),
            'user_answer': response.get('answer', ''),
            'is_correct': response.get('answer') == question.get('correct_answer'),
            'confidence': response.get('confidence', 0),
            'options': question.get('options', [])
        })
    
    return render_template('quiz_complete.html',  # Using existing template for now
                         attempt=attempt,
                         quiz=quiz,
                         topic=topic,
                         ml_prediction=ml_prediction,
                         recommendations=recommendations,
                         question_analysis=question_analysis)

# ===================== STUDENT PROFILE & ANALYTICS ROUTES =====================

@app.route('/student/profile')
def student_profile():
    """Student profile page with ML insights"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    student = db.session.get(Student, session['user_id'])
    profile = StudentProfile.query.filter_by(student_id=session['user_id']).first()
    
    if not profile:
        profile = StudentProfile(student_id=session['user_id'])
        db.session.add(profile)
        db.session.commit()
    
    # Get recent attempts and predictions
    recent_attempts = QuizAttempt.query.filter_by(
        student_id=session['user_id'],
        is_completed=True
    ).order_by(QuizAttempt.completed_at.desc()).limit(10).all()
    
    recent_predictions = MLPrediction.query.filter_by(
        student_id=session['user_id']
    ).order_by(MLPrediction.created_at.desc()).limit(5).all()
    
    # Get active recommendations
    active_recommendations = StudentRecommendation.query.filter_by(
        student_id=session['user_id'],
        is_active=True
    ).order_by(StudentRecommendation.priority, StudentRecommendation.created_at.desc()).limit(10).all()
    
    # Performance analytics
    performance_data = {
        'total_quizzes': len(recent_attempts),
        'average_score': profile.average_score,
        'current_category': profile.predicted_category,
        'confidence_trend': [p.confidence_level for p in recent_predictions],
        'score_trend': [a.score for a in recent_attempts if a.score]
    }
    
    return render_template('progress.html',  # Using existing template for now
                         student=student,
                         profile=profile,
                         recent_attempts=recent_attempts,
                         recent_predictions=recent_predictions,
                         recommendations=active_recommendations,
                         performance_data=performance_data)

@app.route('/recommendations/complete/<int:rec_id>', methods=['POST'])
def complete_recommendation(rec_id):
    """Mark a recommendation as completed"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    recommendation = db.session.get(StudentRecommendation, rec_id)
    
    # Verify ownership
    if recommendation.student_id != session['user_id']:
        flash('Access denied.')
        return redirect(url_for('student_profile'))
    
    recommendation.is_completed = True
    recommendation.is_active = False
    db.session.commit()
    
    flash('Recommendation completed!')
    return redirect(url_for('student_profile'))

@app.route('/api/student/analytics')
def student_analytics_api():
    """API endpoint for student analytics dashboard"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    student_id = session['user_id']
    
    # Get recent performance data
    recent_attempts = QuizAttempt.query.filter_by(
        student_id=student_id,
        is_completed=True
    ).order_by(QuizAttempt.completed_at.desc()).limit(20).all()
    
    # Get ML predictions
    predictions = MLPrediction.query.filter_by(
        student_id=student_id
    ).order_by(MLPrediction.created_at.desc()).limit(10).all()
    
    # Prepare analytics data
    analytics_data = {
        'performance_trend': [
            {
                'date': attempt.completed_at.strftime('%Y-%m-%d'),
                'score': attempt.score,
                'predicted_score': predictions[i].predicted_score if i < len(predictions) else None,
                'category': predictions[i].category if i < len(predictions) else None
            }
            for i, attempt in enumerate(recent_attempts)
        ],
        'learning_profile': predictions[0].learner_profile if predictions else {},
        'improvement_areas': [],
        'strengths': []
    }
    
    # Analyze learning profile for insights
    if predictions:
        latest_profile = predictions[0].learner_profile
        if latest_profile.get('support_needed') == 'high':
            analytics_data['improvement_areas'].append('Needs more guided practice')
        if latest_profile.get('problem_solving') == 'efficient':
            analytics_data['strengths'].append('Efficient problem solving')
        if latest_profile.get('learning_pace') == 'fast':
            analytics_data['strengths'].append('Quick learner')
    
    return jsonify(analytics_data)

# ===================== CELERY TASK UPDATES =====================

@celery.task
def analyze_student_performance(student_id):
    """Background task to analyze student performance and update recommendations"""
    try:
        # Get recent attempts
        recent_attempts = QuizAttempt.query.filter_by(
            student_id=student_id,
            is_completed=True
        ).order_by(QuizAttempt.completed_at.desc()).limit(5).all()
        
        if not recent_attempts:
            return "No recent attempts to analyze"
        
        # Run ML analysis on recent attempts
        for attempt in recent_attempts:
            existing_prediction = MLPrediction.query.filter_by(quiz_attempt_id=attempt.id).first()
            if not existing_prediction:
                # Generate prediction for attempts that don't have one
                prediction_result = ml_analytics.predict_performance(attempt)
                MLDataManager.save_prediction(attempt.id, prediction_result)
                
                # Generate recommendations
                recommendations = recommendation_engine.generate_recommendations(
                    prediction_result, 
                    student_id
                )
                MLDataManager.save_recommendations(student_id, attempt.id, recommendations)
        
        # Update student profile
        latest_attempt = recent_attempts[0]
        latest_prediction = MLPrediction.query.filter_by(quiz_attempt_id=latest_attempt.id).first()
        if latest_prediction:
            prediction_result = {
                'predicted_score': latest_prediction.predicted_score,
                'category': latest_prediction.category,
                'confidence_level': latest_prediction.confidence_level,
                'learner_profile': latest_prediction.learner_profile
            }
            MLDataManager.update_student_profile(student_id, prediction_result)
        
        return f"Successfully analyzed performance for student {student_id}"
        
    except Exception as e:
        return f"Error analyzing student performance: {str(e)}"

# ===================== PLACEHOLDER ROUTES FOR MISSING FUNCTIONALITY =====================

# Teacher routes (placeholder)
@app.route('/teacher/login', methods=['GET', 'POST'])
def teacher_login():
    return render_template('login.html')  # Reuse login template for now

@app.route('/teacher/logout')
def teacher_logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/teacher/dashboard')
def teacher_dashboard():
    return "Teacher dashboard coming soon!"

# Chat interface (placeholder)
@app.route('/chat')
def chat_interface():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return "Chat interface coming soon!"

# Progress view (using existing progress template)
@app.route('/progress')
def view_progress():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('student_profile'))  # Redirect to student profile for now

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    # Skip importing optional route modules for now since they have conflicts
    # The core functionality is already implemented above
    print("Educational Platform Flask application starting...")
    print("Core routes available: login, register, dashboard, quiz, profile")
    print("Optional features (teacher dashboard, chat) are placeholders")
    
    app.run(debug=True, port=5001)