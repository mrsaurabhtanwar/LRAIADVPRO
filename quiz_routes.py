# quiz_routes.py - Quiz handling and ML prediction routes
from flask import request, session, render_template, redirect, url_for, jsonify, flash
from models import *
from extensions import db
import json
from datetime import datetime
import numpy as np
from ml_utils import extract_features, make_prediction, generate_recommendations

# We need to get the app instance from the main module
import app as main_app
app = main_app.app

@app.route('/quiz/question/<int:question_num>')
def quiz_question(question_num):
    """Present quiz question"""
    if 'user_id' not in session or 'current_attempt' not in session:
        return redirect(url_for('login'))
    
    attempt = QuizAttempt.query.get(session['current_attempt'])
    if not attempt:
        return redirect(url_for('dashboard'))
    
    questions = Question.query.filter_by(quiz_id=attempt.quiz_id).order_by(Question.order_num).all()
    
    if question_num > len(questions):
        return redirect(url_for('quiz_complete'))
    
    current_question = questions[question_num - 1]
    
    # Check if student already answered this question
    existing_response = QuestionResponse.query.filter_by(
        attempt_id=attempt.id,
        question_id=current_question.id
    ).first()

    return render_template('quiz_question.html',
                         question=current_question,
                         question_num=question_num,
                         total_questions=len(questions),
                         existing_response=existing_response)

@app.route('/quiz/hint/<int:question_id>')
def get_hint(question_id):
    """Get hint for question based on student performance"""
    if 'current_attempt' not in session:
        return jsonify({'error': 'No active quiz attempt'}), 400
    
    question = Question.query.get(question_id)
    attempt = QuizAttempt.query.get(session['current_attempt'])
    
    # Increment hints used for this attempt
    attempt.hints_used = (attempt.hints_used or 0) + 1
    db.session.commit()
    
    # Return adaptive hint based on student's current performance
    hint_level = "basic"
    if attempt.hints_used > 3:
        hint_level = "detailed"
    
    return jsonify({
        'hint': question.hint,
        'hint_level': hint_level
    })

@app.route('/quiz/submit_answer', methods=['POST'])
def submit_answer():
    """Submit answer for current question"""
    if 'current_attempt' not in session:
        return jsonify({'error': 'No active quiz attempt'}), 400
    
    data = request.get_json()
    question_id = data.get('question_id')
    answer = data.get('answer')
    response_time = data.get('response_time')
    hints_used = data.get('hints_used', 0)
    
    attempt = QuizAttempt.query.get(session['current_attempt'])
    question = Question.query.get(question_id)
    
    # Check if answer is correct
    is_correct = (answer.strip().lower() == question.correct_answer.strip().lower())
    
    # Check for existing response
    response = QuestionResponse.query.filter_by(
        attempt_id=attempt.id,
        question_id=question_id
    ).first()
    
    if response:
        # Update existing response
        response.student_answer = answer
        response.is_correct = is_correct
        response.response_time_seconds = response_time
        response.hints_used = hints_used
        response.attempts_count += 1
    else:
        # Create new response
        response = QuestionResponse(
            attempt_id=attempt.id,
            question_id=question_id,
            student_answer=answer,
            is_correct=is_correct,
            response_time_seconds=response_time,
            hints_used=hints_used
        )
        db.session.add(response)
    
    db.session.commit()
    
    return jsonify({
        'correct': is_correct,
        'explanation': question.explanation if not is_correct else None
    })

@app.route('/quiz/complete')
def quiz_complete():
    """Complete quiz and trigger ML analysis"""
    if 'current_attempt' not in session:
        return redirect(url_for('dashboard'))
    
    attempt = QuizAttempt.query.get(session['current_attempt'])
    
    # Mark quiz as completed
    attempt.completed_at = datetime.utcnow()
    
    # Calculate basic scores
    responses = QuestionResponse.query.filter_by(attempt_id=attempt.id).all()
    correct_count = sum(1 for r in responses if r.is_correct)
    attempt.total_questions = len(responses)
    attempt.correct_answers = correct_count
    attempt.score = (correct_count / len(responses)) * 100 if responses else 0
    
    # Calculate time spent
    time_spent = (attempt.completed_at - attempt.started_at).total_seconds()
    attempt.time_spent_seconds = int(time_spent)
    
    db.session.commit()
    
    # Trigger ML feature extraction and prediction
    from tasks import extract_and_predict
    extract_and_predict.delay(attempt.id)
    
    # Clear current attempt from session
    session.pop('current_attempt', None)
    
    return render_template('quiz_complete.html', attempt=attempt)

@app.route('/submit_activity', methods=['POST'])
def submit_activity():
    """API endpoint for ML prediction after quiz completion"""
    data = request.get_json()
    attempt_id = data.get('attempt_id')
    
    attempt = QuizAttempt.query.get(attempt_id)
    if not attempt:
        return jsonify({'error': 'Attempt not found'}), 404
    
    # Extract features and make prediction
    features = extract_features(attempt)
    prediction, confidence = make_prediction(features)
    recommendations = generate_recommendations(prediction, features, attempt)
    
    # Store results
    attempt.predicted_performance = prediction
    attempt.confidence_score = confidence
    attempt.recommendations = json.dumps(recommendations)
    
    # Update features in database
    for key, value in features.items():
        if hasattr(attempt, key):
            setattr(attempt, key, value)
    
    db.session.commit()
    
    return jsonify({
        'prediction': prediction,
        'confidence': confidence,
        'recommendations': recommendations
    })