# ml_utils.py - Machine Learning utilities for feature extraction and prediction
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import pickle
import os
from datetime import datetime, timedelta
from models import *

def extract_features(attempt):
    """Extract 15 features from quiz attempt for ML prediction"""
    responses = QuestionResponse.query.filter_by(attempt_id=attempt.id).all()
    
    if not responses:
        return {}
    
    features = {}
    
    # 1. Time-based features
    total_time = attempt.time_spent_seconds or 0
    features['time_spent_seconds'] = total_time
    features['average_response_time'] = np.mean([r.response_time_seconds for r in responses if r.response_time_seconds])
    
    # 2. Accuracy features
    correct_answers = sum(1 for r in responses if r.is_correct)
    features['correct_answers'] = correct_answers
    accuracy_rate = correct_answers / len(responses) if responses else 0
    
    # 3. Help-seeking behavior
    features['hints_used'] = sum(r.hints_used for r in responses)
    features['help_requests'] = attempt.help_requests or 0
    
    # 4. Attempt patterns
    total_attempts = sum(r.attempts_count for r in responses)
    features['wrong_attempts_per_question'] = (total_attempts - len(responses)) / len(responses) if responses else 0
    
    # 5. Consistency and performance patterns
    correct_sequence = [1 if r.is_correct else 0 for r in responses]
    features['consistency_score'] = calculate_consistency(correct_sequence)
    features['improvement_trend'] = calculate_improvement_trend(correct_sequence)
    
    # 6. Question difficulty adaptation
    features['difficulty_adaptation'] = calculate_difficulty_adaptation(responses)
    
    # 7. Interaction patterns (simulated - in real app, track these client-side)
    features['mouse_movements'] = estimate_mouse_movements(responses)
    features['clicks_per_question'] = estimate_clicks_per_question(responses)
    
    # 8. Time distribution analysis
    response_times = [r.response_time_seconds for r in responses if r.response_time_seconds]
    if response_times:
        wrong_responses = [r for r in responses if not r.is_correct]
        wrong_times = [r.response_time_seconds for r in wrong_responses if r.response_time_seconds]
        features['time_on_wrong_answers'] = np.mean(wrong_times) if wrong_times else 0
    else:
        features['time_on_wrong_answers'] = 0
    
    # 9. Review and reflection indicators
    features['review_time_ratio'] = calculate_review_time_ratio(responses, total_time)
    
    # 10. Learning progression indicators
    features['concept_mastery_score'] = calculate_concept_mastery(responses)
    features['retention_indicator'] = calculate_retention_indicator(attempt.student_id, responses)
    
    return features

def calculate_consistency(correct_sequence):
    """Calculate how consistent the student's performance is"""
    if len(correct_sequence) < 2:
        return 0.5
    
    # Calculate variance in performance
    variance = np.var(correct_sequence)
    # Normalize to 0-1 scale (lower variance = higher consistency)
    consistency = 1 - variance
    return consistency

def calculate_improvement_trend(correct_sequence):
    """Calculate if student is improving during the quiz"""
    if len(correct_sequence) < 3:
        return 0.0
    
    # Split into first and second half
    mid = len(correct_sequence) // 2
    first_half_avg = np.mean(correct_sequence[:mid])
    second_half_avg = np.mean(correct_sequence[mid:])
    
    # Return improvement (positive) or decline (negative)
    return second_half_avg - first_half_avg

def calculate_difficulty_adaptation(responses):
    """Calculate how well student adapts to question difficulty"""
    if not responses:
        return 0.5
    
    # Assume questions get progressively harder (or use actual difficulty ratings)
    difficulty_scores = []
    for i, response in enumerate(responses):
        # Higher index = harder question (or use actual difficulty from question)
        question_difficulty = (i + 1) / len(responses)
        if response.is_correct:
            difficulty_scores.append(question_difficulty)
    
    return np.mean(difficulty_scores) if difficulty_scores else 0.0

def estimate_mouse_movements(responses):
    """Estimate mouse movements based on response patterns"""
    # In real implementation, track actual mouse movements client-side
    # For now, estimate based on response times and attempts
    base_movements = len(responses) * 10  # Base movements per question
    extra_movements = sum(r.attempts_count * 5 for r in responses)  # Extra for retries
    return base_movements + extra_movements

def estimate_clicks_per_question(responses):
    """Estimate clicks per question"""
    if not responses:
        return 0
    
    total_clicks = sum(r.attempts_count * 2 + r.hints_used for r in responses)
    return total_clicks / len(responses)

def calculate_review_time_ratio(responses, total_time):
    """Calculate ratio of time spent reviewing vs answering"""
    if not responses or total_time == 0:
        return 0.5
    
    active_answer_time = sum(r.response_time_seconds for r in responses if r.response_time_seconds)
    review_time = total_time - active_answer_time
    
    return review_time / total_time if total_time > 0 else 0.5

def calculate_concept_mastery(responses):
    """Calculate mastery of concepts based on response patterns"""
    if not responses:
        return 0.0
    
    # Weight later questions more heavily (learning progression)
    weighted_score = 0
    total_weight = 0
    
    for i, response in enumerate(responses):
        weight = i + 1  # Later questions have more weight
        score = 1 if response.is_correct else 0
        weighted_score += score * weight
        total_weight += weight
    
    return weighted_score / total_weight if total_weight > 0 else 0.0

def calculate_retention_indicator(student_id, current_responses):
    """Calculate retention based on previous quiz performance"""
    # Get student's previous quiz attempts
    previous_attempts = QuizAttempt.query.filter_by(
        student_id=student_id
    ).filter(
        QuizAttempt.completed_at.isnot(None)
    ).order_by(QuizAttempt.completed_at.desc()).limit(5).all()
    
    if not previous_attempts:
        return 0.5  # Neutral for first-time students
    
    # Calculate improvement over time
    scores = [attempt.score for attempt in reversed(previous_attempts)]
    if len(scores) < 2:
        return 0.5
    
    # Calculate trend
    recent_avg = np.mean(scores[-2:])
    earlier_avg = np.mean(scores[:-2]) if len(scores) > 2 else scores[0]
    
    improvement = (recent_avg - earlier_avg) / 100.0  # Normalize
    return max(0, min(1, 0.5 + improvement))  # Clamp to [0, 1]

def make_prediction(features):
    """Make performance prediction using ML model"""
    # Load trained model
    model_path = 'models/performance_predictor.pkl'
    scaler_path = 'models/feature_scaler.pkl'
    
    try:
        with open(model_path, 'rb') as f:
            model = pickle.load(f)
        with open(scaler_path, 'rb') as f:
            scaler = pickle.load(f)
    except FileNotFoundError:
        # If no trained model exists, create and train a basic one
        model, scaler = create_initial_model()
    
    # Prepare feature vector
    feature_names = [
        'time_spent_seconds', 'average_response_time', 'correct_answers',
        'hints_used', 'help_requests', 'wrong_attempts_per_question',
        'consistency_score', 'improvement_trend', 'difficulty_adaptation',
        'mouse_movements', 'clicks_per_question', 'time_on_wrong_answers',
        'review_time_ratio', 'concept_mastery_score', 'retention_indicator'
    ]
    
    feature_vector = np.array([[features.get(name, 0) for name in feature_names]])
    
    # Scale features
    feature_vector_scaled = scaler.transform(feature_vector)
    
    # Make prediction
    prediction = model.predict(feature_vector_scaled)[0]
    confidence = max(model.predict_proba(feature_vector_scaled)[0])
    
    return prediction, confidence

def create_initial_model():
    """Create initial ML model if none exists"""
    # This would normally be trained on historical data
    # For demo purposes, create a simple model
    
    # Generate some sample training data
    np.random.seed(42)
    n_samples = 1000
    
    # Generate features
    X = np.random.randn(n_samples, 15)
    
    # Generate labels based on simple rules
    y = []
    for features in X:
        score = (features[2] + features[6] + features[8] + features[13]) / 4  # Use some features
        if score > 0.5:
            y.append('excellent' if score > 1.0 else 'good')
        else:
            y.append('struggling' if score < -0.5 else 'needs_improvement')
    
    # Train model
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_scaled, y)
    
    # Save model and scaler
    os.makedirs('models', exist_ok=True)
    with open('models/performance_predictor.pkl', 'wb') as f:
        pickle.dump(model, f)
    with open('models/feature_scaler.pkl', 'wb') as f:
        pickle.dump(scaler, f)
    
    return model, scaler

def generate_recommendations(prediction, features, attempt):
    """Generate personalized recommendations based on prediction and features"""
    recommendations = []
    
    # Base recommendations on prediction
    if prediction == 'excellent':
        recommendations.extend([
            "Great job! Try more challenging topics to continue growing.",
            "Consider helping other students or becoming a peer tutor.",
            "Explore advanced concepts in this subject area."
        ])
    
    elif prediction == 'good':
        recommendations.extend([
            "Good performance! Keep up the consistent work.",
            "Try to improve your weaker areas with focused practice.",
            "Consider slightly more challenging questions next time."
        ])
    
    elif prediction == 'needs_improvement':
        recommendations.extend([
            "Review the concepts you missed in this quiz.",
            "Take your time and use hints when needed.",
            "Practice similar questions to build confidence."
        ])
    
    else:  # struggling
        recommendations.extend([
            "Don't worry! Learning takes time and practice.",
            "Review the basic concepts before attempting more questions.",
            "Consider asking for help from a teacher or tutor.",
            "Use the AI chat tutor for additional explanations."
        ])
    
    # Feature-specific recommendations
    if features.get('hints_used', 0) > 3:
        recommendations.append("You used many hints. Try to think through problems before asking for help.")
    
    if features.get('average_response_time', 0) > 120:  # More than 2 minutes per question
        recommendations.append("You're taking time to think carefully - that's good! But also trust your instincts.")
    
    if features.get('consistency_score', 0.5) < 0.3:
        recommendations.append("Your performance varied quite a bit. Try to maintain focus throughout the quiz.")
    
    if features.get('improvement_trend', 0) > 0.2:
        recommendations.append("Great! You improved as the quiz went on. This shows good learning!")
    
    if features.get('concept_mastery_score', 0.5) < 0.4:
        recommendations.append("Focus on understanding the fundamental concepts before moving to advanced topics.")
    
    return recommendations[:5]  # Return top 5 recommendations

def retrain_model():
    """Retrain the ML model with new data"""
    # Get all completed attempts with sufficient data
    attempts = QuizAttempt.query.filter(
        QuizAttempt.completed_at.isnot(None),
        QuizAttempt.predicted_performance.isnot(None)
    ).all()
    
    if len(attempts) < 100:  # Need sufficient data
        return False
    
    # Extract features and labels
    X = []
    y = []
    
    for attempt in attempts:
        features = extract_features(attempt)
        if features:
            feature_vector = [
                features.get('time_spent_seconds', 0),
                features.get('average_response_time', 0),
                features.get('correct_answers', 0),
                features.get('hints_used', 0),
                features.get('help_requests', 0),
                features.get('wrong_attempts_per_question', 0),
                features.get('consistency_score', 0.5),
                features.get('improvement_trend', 0),
                features.get('difficulty_adaptation', 0.5),
                features.get('mouse_movements', 0),
                features.get('clicks_per_question', 0),
                features.get('time_on_wrong_answers', 0),
                features.get('review_time_ratio', 0.5),
                features.get('concept_mastery_score', 0.5),
                features.get('retention_indicator', 0.5)
            ]
            X.append(feature_vector)
            y.append(attempt.predicted_performance)
    
    if len(X) < 100:
        return False
    
    # Train new model
    X = np.array(X)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_scaled, y)
    
    # Save updated model
    with open('models/performance_predictor.pkl', 'wb') as f:
        pickle.dump(model, f)
    with open('models/feature_scaler.pkl', 'wb') as f:
        pickle.dump(scaler, f)
    
    return True