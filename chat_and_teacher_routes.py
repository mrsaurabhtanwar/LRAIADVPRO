# chat_and_teacher_routes.py - AI Chat and Teacher Dashboard routes
from flask import request, session, render_template, redirect, url_for, jsonify, flash
from werkzeug.security import check_password_hash
from models import *
from extensions import db
import json
from datetime import datetime, timedelta
import numpy as np
import openai  # For AI chat functionality
import os

# We need to get the app instance from the main module
import app as main_app
app = main_app.app

# Configure OpenAI (or use any other LLM API)
openai.api_key = os.getenv('OPENAI_API_KEY')

# ===================== AI CHAT ROUTES =====================

@app.route('/chat')
def chat_interface():
    """Open AI tutor chat interface"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
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
def send_message():
    """Send message to AI tutor"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
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
    
    # Get AI response
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

@app.route('/chat/end', methods=['POST'])
def end_chat():
    """End current chat session"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    data = request.get_json()
    session_id = data.get('session_id')
    
    chat_session = ChatSession.query.get(session_id)
    if chat_session and chat_session.student_id == session['user_id']:
        chat_session.ended_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True})
    
    return jsonify({'error': 'Session not found'}), 404

def get_ai_response(student_message, chat_session):
    """Generate AI tutor response using LLM"""
    # Get student context
    student = Student.query.get(chat_session.student_id)
    
    # Get recent quiz performance for context
    recent_attempts = QuizAttempt.query.filter_by(
        student_id=student.id
    ).filter(
        QuizAttempt.completed_at.isnot(None)
    ).order_by(QuizAttempt.completed_at.desc()).limit(3).all()
    
    # Build context for AI
    context = f"""You are an AI tutor helping {student.name}, a {student.class_name} student.
    
Recent performance:"""
    
    for attempt in recent_attempts:
        context += f"\n- Quiz: {attempt.quiz.title}, Score: {attempt.score}%, Performance: {attempt.predicted_performance}"
    
    # Get chat history for context
    previous_messages = ChatMessage.query.filter_by(
        session_id=chat_session.id
    ).order_by(ChatMessage.timestamp.desc()).limit(10).all()
    
    conversation_history = []
    for msg in reversed(previous_messages):
        role = "user" if msg.sender == "student" else "assistant"
        conversation_history.append({"role": role, "content": msg.message})
    
    # Add current message
    conversation_history.append({"role": "user", "content": student_message})
    
    try:
        # Call OpenAI API (replace with your preferred LLM)
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": context + "\n\nBe helpful, encouraging, and educational. Keep responses concise but informative."},
                *conversation_history
            ],
            max_tokens=300,
            temperature=0.7
        )
        
        return response.choices[0].message.content
    
    except Exception as e:
        # Fallback response if API fails
        return "I'm sorry, I'm having trouble connecting right now. Please try asking your question again, or consider asking your teacher for help."

# ===================== TEACHER DASHBOARD ROUTES =====================

@app.route('/teacher/login', methods=['GET', 'POST'])
def teacher_login():
    """Teacher login"""
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        teacher = Teacher.query.filter_by(email=email).first()
        
        if teacher and check_password_hash(teacher.password_hash, password):
            session['teacher_id'] = teacher.id
            session['teacher_name'] = teacher.name
            return redirect(url_for('teacher_dashboard'))
        else:
            flash('Invalid credentials!')
    
    return render_template('teacher_login.html')

@app.route('/teacher/dashboard')
def teacher_dashboard():
    """Teacher main dashboard"""
    if 'teacher_id' not in session:
        return redirect(url_for('teacher_login'))
    
    teacher = Teacher.query.get(session['teacher_id'])
    
    # Get class overview data
    total_students = Student.query.count()
    recent_attempts = QuizAttempt.query.filter(
        QuizAttempt.completed_at >= datetime.utcnow() - timedelta(days=7)
    ).count()
    
    # Get performance distribution
    performance_stats = db.session.query(
        QuizAttempt.predicted_performance,
        db.func.count(QuizAttempt.id)
    ).filter(
        QuizAttempt.predicted_performance.isnot(None)
    ).group_by(QuizAttempt.predicted_performance).all()
    
    return render_template('teacher_dashboard.html',
                         teacher=teacher,
                         total_students=total_students,
                         recent_attempts=recent_attempts,
                         performance_stats=performance_stats)

@app.route('/teacher/students')
def teacher_students():
    """View all students with analytics"""
    if 'teacher_id' not in session:
        return redirect(url_for('teacher_login'))
    
    # Get filter parameters
    grade_filter = request.args.get('grade')
    subject_filter = request.args.get('subject')
    
    # Build query
    students_query = Student.query
    
    if grade_filter:
        students_query = students_query.filter_by(class_name=grade_filter)
    
    students = students_query.all()
    
    # Get analytics for each student
    student_analytics = []
    for student in students:
        recent_attempts = QuizAttempt.query.filter_by(
            student_id=student.id
        ).filter(
            QuizAttempt.completed_at.isnot(None)
        ).order_by(QuizAttempt.completed_at.desc()).limit(5).all()
        
        avg_score = np.mean([a.score for a in recent_attempts]) if recent_attempts else 0
        latest_performance = recent_attempts[0].predicted_performance if recent_attempts else 'No data'
        
        student_analytics.append({
            'student': student,
            'recent_attempts': len(recent_attempts),
            'avg_score': avg_score,
            'latest_performance': latest_performance
        })
    
    # Get available grades and subjects for filters
    grades = db.session.query(Student.class_name).distinct().all()
    subjects = db.session.query(Topic.subject).distinct().all()
    
    return render_template('teacher_students.html',
                         student_analytics=student_analytics,
                         grades=[g[0] for g in grades],
                         subjects=[s[0] for s in subjects],
                         current_grade=grade_filter,
                         current_subject=subject_filter)

@app.route('/teacher/student/<int:student_id>')
def student_detail(student_id):
    """Detailed view of individual student"""
    if 'teacher_id' not in session:
        return redirect(url_for('teacher_login'))
    
    student = Student.query.get_or_404(student_id)
    
    # Get all quiz attempts
    attempts = QuizAttempt.query.filter_by(
        student_id=student_id
    ).filter(
        QuizAttempt.completed_at.isnot(None)
    ).order_by(QuizAttempt.completed_at.desc()).all()
    
    # Get chat sessions
    chat_sessions = ChatSession.query.filter_by(
        student_id=student_id
    ).order_by(ChatSession.started_at.desc()).limit(5).all()
    
    # Calculate trends
    if len(attempts) >= 2:
        recent_scores = [a.score for a in attempts[:5]]
        trend = 'improving' if recent_scores[0] > recent_scores[-1] else 'declining'
    else:
        trend = 'insufficient_data'
    
    return render_template('student_detail.html',
                         student=student,
                         attempts=attempts,
                         chat_sessions=chat_sessions,
                         trend=trend)

@app.route('/students/<int:student_id>/history')
def student_history(student_id):
    """API endpoint for student's quiz history"""
    if 'user_id' not in session and 'teacher_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Check if it's the student themselves or a teacher
    if 'user_id' in session and session['user_id'] != student_id:
        return jsonify({'error': 'Forbidden'}), 403
    
    attempts = QuizAttempt.query.filter_by(
        student_id=student_id
    ).filter(
        QuizAttempt.completed_at.isnot(None)
    ).order_by(QuizAttempt.completed_at.desc()).all()
    
    history = []
    for attempt in attempts:
        recommendations = json.loads(attempt.recommendations) if attempt.recommendations else []
        
        history.append({
            'id': attempt.id,
            'quiz_title': attempt.quiz.title,
            'score': attempt.score,
            'completed_at': attempt.completed_at.isoformat(),
            'predicted_performance': attempt.predicted_performance,
            'confidence_score': attempt.confidence_score,
            'recommendations': recommendations
        })
    
    return jsonify({'history': history})

@app.route('/teacher/export')
def export_data():
    """Export student data for analysis"""
    if 'teacher_id' not in session:
        return redirect(url_for('teacher_login'))
    
    # Get all student data
    attempts = QuizAttempt.query.filter(
        QuizAttempt.completed_at.isnot(None)
    ).all()
    
    data = []
    for attempt in attempts:
        data.append({
            'student_id': attempt.student.student_id,
            'student_name': attempt.student.name,
            'class': attempt.student.class_name,
            'quiz_title': attempt.quiz.title,
            'score': attempt.score,
            'predicted_performance': attempt.predicted_performance,
            'completed_at': attempt.completed_at.isoformat() if attempt.completed_at else None,
            'time_spent_minutes': (attempt.time_spent_seconds / 60) if attempt.time_spent_seconds else None
        })
    
    return jsonify({'data': data})

# ===================== PROGRESS VIEW ROUTES =====================

@app.route('/progress')
def view_progress():
    """Student progress view"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    student_id = session['user_id']
    student = Student.query.get(student_id)
    
    # Get recent attempts with predictions
    attempts = QuizAttempt.query.filter_by(
        student_id=student_id
    ).filter(
        QuizAttempt.completed_at.isnot(None),
        QuizAttempt.predicted_performance.isnot(None)
    ).order_by(QuizAttempt.completed_at.desc()).limit(10).all()
    
    # Get current recommendations
    latest_attempt = attempts[0] if attempts else None
    current_recommendations = []
    
    if latest_attempt and latest_attempt.recommendations:
        current_recommendations = json.loads(latest_attempt.recommendations)
    
    # Calculate progress metrics
    if len(attempts) >= 2:
        recent_avg = np.mean([a.score for a in attempts[:3]])
        older_avg = np.mean([a.score for a in attempts[3:6]]) if len(attempts) > 3 else recent_avg
        progress_trend = recent_avg - older_avg
    else:
        progress_trend = 0
    
    return render_template('progress.html',
                         student=student,
                         attempts=attempts,
                         current_recommendations=current_recommendations,
                         progress_trend=progress_trend)

@app.route('/recommendations/follow', methods=['POST'])
def follow_recommendation():
    """Handle student following a recommendation"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    data = request.get_json()
    action = data.get('action')
    
    if action == 'take_quiz':
        return jsonify({'redirect': url_for('quiz_selection')})
    elif action == 'study_material':
        return jsonify({'redirect': url_for('learning_resources')})
    elif action == 'get_help':
        return jsonify({'redirect': url_for('chat_interface')})
    else:
        return jsonify({'redirect': url_for('dashboard')})

@app.route('/resources')
def learning_resources():
    """Access learning resources"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Get topics and resources
    topics = Topic.query.all()
    
    return render_template('learning_resources.html', topics=topics)