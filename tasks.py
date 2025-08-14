# tasks.py - Celery background tasks
from extensions import db, celery
from models import Topic, Quiz, Question, QuizAttempt
import json

def generate_questions_from_content(content, difficulty_level):
    # Placeholder for AI question generation
    sample_questions = [
        {
            'question': 'What is the main concept in this topic?',
            'type': 'multiple_choice',
            'options': ['Option A', 'Option B', 'Option C', 'Option D'],
            'correct_answer': 'Option A',
            'explanation': 'This is the correct answer because...',
            'hint': 'Think about the key principles discussed.',
            'difficulty': difficulty_level
        }
    ]
    return sample_questions[:10]

@celery.task
def generate_quiz_task(topic_id):
    topic = Topic.query.get(topic_id)
    if not topic:
        return None
    quiz = Quiz(
        topic_id=topic_id,
        title=f"{topic.name} Quiz",
        total_questions=10
    )
    db.session.add(quiz)
    db.session.flush()
    questions_data = generate_questions_from_content(topic.content, topic.difficulty_level)
    for i, q_data in enumerate(questions_data):
        question = Question(
            quiz_id=quiz.id,
            question_text=q_data['question'],
            question_type=q_data['type'],
            correct_answer=q_data['correct_answer'],
            explanation=q_data.get('explanation', ''),
            difficulty=q_data.get('difficulty', 'medium'),
            hint=q_data.get('hint', ''),
            order_num=i + 1
        )
        if q_data['type'] == 'multiple_choice':
            question.set_options(q_data['options'])
        db.session.add(question)
    db.session.commit()
    return quiz.id

@celery.task
def extract_and_predict(attempt_id):
    """Background task to extract features and make ML prediction"""
    from ml_utils import extract_features, make_prediction, generate_recommendations
    
    attempt = QuizAttempt.query.get(attempt_id)
    if not attempt:
        return
    
    # Extract 15 features
    features = extract_features(attempt)
    
    # Make prediction
    prediction, confidence = make_prediction(features)
    
    # Generate recommendations
    recommendations = generate_recommendations(prediction, features, attempt)
    
    # Update attempt with results
    attempt.predicted_performance = prediction
    attempt.confidence_score = confidence
    attempt.recommendations = json.dumps(recommendations)
    
    # Store extracted features
    for key, value in features.items():
        if hasattr(attempt, key):
            setattr(attempt, key, value)
    
    db.session.commit()
