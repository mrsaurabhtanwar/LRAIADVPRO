# app.py - Educational Platform with External AI Tutor Integration
import logging
import requests
import json
from datetime import datetime
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

# Import models
from models import Student, Quiz, QuizAttempt, ChatSession, ChatMessage, StudentRecommendation, Answer, Question

# Import quiz generation API integration
from quiz_api_integration import quiz_api

# Template filters
@app.template_filter('chr')
def chr_filter(number, offset=64):
    """Convert number to letter (1->A, 2->B, etc.)"""
    return chr(number + offset)

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
    
    # Debug: Print question structure
    print(f"DEBUG: Displaying question {question_num}")
    print(f"DEBUG: Question data: {current_question}")
    print(f"DEBUG: Has options: {'options' in current_question}")
    
    # Safe check for options
    if 'options' in current_question and current_question['options'] is not None:
        print(f"DEBUG: Number of options: {len(current_question['options'])}")
        print(f"DEBUG: Options: {current_question['options']}")
    else:
        print("DEBUG: Options is None or missing!")
        # Look for other possible keys that might contain the choices
        for key, value in current_question.items():
            if isinstance(value, list) and value:
                print(f"DEBUG: Found list in key '{key}': {value}")
            elif key in ['choices', 'answers', 'alternatives', 'mcq_options']:
                print(f"DEBUG: Found potential options in key '{key}': {value}")

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
    """Generate a quiz using the external API"""
    topic = request.form.get('topic')
    difficulty = request.form.get('difficulty', 'medium')
    num_questions = int(request.form.get('num_questions', 5))
    
    if not topic:
        flash('Topic is required for quiz generation')
        return render_template('generate_quiz.html')
    
    # Get student behavioral data for personalization
    student_id = session['user_id']
    recent_attempts = QuizAttempt.query.filter_by(
        student_id=student_id,
        is_completed=True
    ).order_by(QuizAttempt.completed_at.desc()).limit(3).all()
    
    # Analyze student behavior for API personalization
    student_data = None
    if recent_attempts:
        student_data = quiz_api.analyze_student_behavior(recent_attempts[0])
    
    # Generate quiz using external API
    result = quiz_api.generate_quiz(
        topic=topic,
        difficulty=difficulty,
        num_questions=num_questions,
        student_data=student_data
    )
    
    if result['success']:
        # Create and save quiz to database
        quiz_data = result['quiz']
        
        # Create new Quiz object
        new_quiz = Quiz(
            title=f"{topic} Quiz - {difficulty.title()}",
            description=f"AI-generated quiz on {topic}",
            topic=topic,
            difficulty=difficulty,
            questions_json=json.dumps(quiz_data.get('questions', [])),
            is_active=True,
            created_at=datetime.now()
        )
        
        db.session.add(new_quiz)
        db.session.commit()
        
        flash(f'Quiz generated successfully! {num_questions} questions on {topic}')
        return redirect(url_for('start_quiz', quiz_id=new_quiz.id))
    else:
        flash(f"Failed to generate quiz: {result['message']}")
        return render_template('generate_quiz.html', 
                             error=result.get('error'),
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
    
    return render_template('progress.html',
                         student=student,
                         attempts=attempts,
                         total_quizzes=total_quizzes,
                         average_score=average_score)

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
