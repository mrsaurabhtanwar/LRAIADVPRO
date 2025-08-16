from __future__ import annotations

# models.py - Enhanced database models for quiz system

from extensions import db
from sqlalchemy.orm import relationship, RelationshipProperty
from sqlalchemy.dialects.postgresql import JSON
from datetime import datetime, timezone
import enum
import json
from typing import List, Optional

class TaskStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class DifficultyLevel(enum.Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

class ContentSource(enum.Enum):
    UPLOADED_FILE = "uploaded_file"
    URL = "url"
    PLAIN_TEXT = "plain_text"

# Legacy Student model for backward compatibility with existing app
class Student(db.Model):
    __tablename__ = 'students'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    student_id = db.Column(db.String(50), unique=True, nullable=False)
    class_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    profile = db.relationship('StudentProfile', backref='student', uselist=False)
    quiz_attempts_old = db.relationship('QuizAttempt', foreign_keys='QuizAttempt.student_id', backref='student_old', lazy='dynamic')
    ml_predictions = db.relationship('MLPrediction', backref='student', lazy='dynamic')

# Enhanced User model for new quiz system
class User(db.Model):
    __tablename__ = "users"
    
    id = db.Column(db.Integer, primary_key=True, index=True)
    email = db.Column(db.String(120), unique=True, index=True)
    username = db.Column(db.String(80), unique=True, index=True)
    hashed_password = db.Column(db.String(255))
    is_teacher = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    quizzes = relationship("Quiz", back_populates="creator")
    quiz_attempts = relationship("QuizAttempt", back_populates="user")

class Task(db.Model):
    __tablename__ = "tasks"
    
    id = db.Column(db.String(50), primary_key=True, index=True)  # UUID
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    task_type = db.Column(db.String(50))  # 'quiz_generation'
    status = db.Column(db.Enum(TaskStatus), default=TaskStatus.PENDING)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    result = db.Column(db.Text)  # JSON string for SQLite compatibility
    error_message = db.Column(db.Text)
    progress = db.Column(db.Float, default=0.0)
    
    # Task-specific parameters
    parameters = db.Column(db.Text)  # JSON string for SQLite compatibility

class Quiz(db.Model):
    __tablename__ = "quizzes"
    
    id = db.Column(db.Integer, primary_key=True, index=True)
    title = db.Column(db.String(200), index=True)
    description = db.Column(db.Text)
    topic = db.Column(db.String(100), index=True)
    difficulty = db.Column(db.String(20))  # Use String instead of Enum to avoid crashes
    content_source_type = db.Column(db.String(20))  # Use String instead of Enum
    content_source_data = db.Column(db.Text)  # JSON string for SQLite compatibility
    creator_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    task_id = db.Column(db.String(50), db.ForeignKey("tasks.id"))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    is_active = db.Column(db.Boolean, default=True)
    time_limit = db.Column(db.Integer)  # in minutes
    
    # Legacy fields for backward compatibility
    questions_json = db.Column(db.Text)  # JSON string of questions (legacy)
    max_score = db.Column(db.Integer, default=100)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'))  # Legacy foreign key
    
    # Relationships
    creator = relationship("User", back_populates="quizzes")
    questions = relationship("Question", back_populates="quiz", cascade="all, delete-orphan")
    quiz_attempts = relationship("QuizAttempt", back_populates="quiz")

class Question(db.Model):
    __tablename__ = "questions"
    
    id = db.Column(db.Integer, primary_key=True, index=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quizzes.id"))
    question_text = db.Column(db.Text)
    question_type = db.Column(db.String(50), default="multiple_choice")
    points = db.Column(db.Float, default=1.0)
    order_index = db.Column(db.Integer)
    explanation = db.Column(db.Text)  # Explanation for the correct answer
    
    # Relationships
    quiz = relationship("Quiz", back_populates="questions")
    options = relationship("QuestionOption", back_populates="question", cascade="all, delete-orphan")
    answers = relationship("Answer", back_populates="question")

class QuestionOption(db.Model):
    __tablename__ = "question_options"
    
    id = db.Column(db.Integer, primary_key=True, index=True)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"))
    option_text = db.Column(db.Text)
    is_correct = db.Column(db.Boolean, default=False)
    order_index = db.Column(db.Integer)
    
    # Relationships
    question = relationship("Question", back_populates="options")

class QuizAttempt(db.Model):
    __tablename__ = "quiz_attempts"
    
    id = db.Column(db.Integer, primary_key=True, index=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quizzes.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    started_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime)
    score = db.Column(db.Float)
    max_score = db.Column(db.Float)
    is_completed = db.Column(db.Boolean, default=False)
    time_taken = db.Column(db.Integer)  # in seconds
    
    # Legacy fields for backward compatibility with existing ML system
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'))  # Legacy foreign key
    hints_used = db.Column(db.Integer, default=0)
    reached_final_hint = db.Column(db.Boolean, default=False)
    attempt_number = db.Column(db.Integer, default=1)
    time_to_first_answer = db.Column(db.Float)  # seconds
    average_confidence = db.Column(db.Float, default=0.5)  # 0-1
    responses_json = db.Column(db.Text)  # JSON of question responses
    timing_data_json = db.Column(db.Text)  # JSON of timing per question
    detailed_analysis_json = db.Column(db.Text)  # JSON of detailed question analysis
    
    # Relationships
    quiz = relationship("Quiz", back_populates="quiz_attempts")
    user = relationship("User", back_populates="quiz_attempts")
    answers = relationship("Answer", back_populates="quiz_attempt")
    ml_prediction = db.relationship('MLPrediction', backref='quiz_attempt', uselist=False)
    recommendations = db.relationship('StudentRecommendation', backref='quiz_attempt', lazy='dynamic')
    
    @property
    def time_spent_seconds(self):
        """Alias for time_taken to maintain backward compatibility"""
        return self.time_taken

class Answer(db.Model):
    __tablename__ = "answers"
    
    id = db.Column(db.Integer, primary_key=True, index=True)
    quiz_attempt_id = db.Column(db.Integer, db.ForeignKey("quiz_attempts.id"))
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"))
    selected_option_id = db.Column(db.Integer, db.ForeignKey("question_options.id"))
    is_correct = db.Column(db.Boolean)
    points_earned = db.Column(db.Float, default=0.0)
    answered_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    quiz_attempt = relationship("QuizAttempt", back_populates="answers")
    question = relationship("Question", back_populates="answers")
    selected_option = relationship("QuestionOption")

class ContentChunk(db.Model):
    __tablename__ = "content_chunks"
    
    id = db.Column(db.Integer, primary_key=True, index=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quizzes.id"))
    chunk_text = db.Column(db.Text)
    chunk_index = db.Column(db.Integer)
    topic_keywords = db.Column(db.Text)  # JSON string for SQLite compatibility
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

# ===================== LEGACY MODELS FOR BACKWARD COMPATIBILITY =====================

class StudentProfile(db.Model):
    __tablename__ = 'student_profiles'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    
    # Learning analytics fields
    current_level = db.Column(db.String(20), default='beginner')  # beginner/intermediate/advanced
    learning_style = db.Column(db.String(50))  # visual/auditory/kinesthetic/mixed
    preferred_difficulty = db.Column(db.String(20), default='medium')
    
    # Performance tracking
    total_quizzes_completed = db.Column(db.Integer, default=0)
    average_score = db.Column(db.Float, default=0.0)
    improvement_rate = db.Column(db.Float, default=0.0)
    
    # ML-derived insights
    predicted_category = db.Column(db.String(20))  # struggling/average/advanced
    confidence_level = db.Column(db.Float)  # Model confidence in predictions
    last_prediction_update = db.Column(db.DateTime)
    
    # Serialized learner profile from ML
    learner_profile_json = db.Column(db.Text)  # JSON string of learner profile
    
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class Topic(db.Model):
    __tablename__ = 'topics'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    difficulty_level = db.Column(db.String(20), default='medium')  # easy/medium/hard
    subject = db.Column(db.String(50), nullable=False)
    
    # Relationships - Legacy quizzes that use topic_id
    legacy_quizzes = db.relationship('Quiz', foreign_keys='Quiz.topic_id', backref='topic_legacy', lazy='dynamic')

class MLPrediction(db.Model):
    __tablename__ = 'ml_predictions'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    quiz_attempt_id = db.Column(db.Integer, db.ForeignKey('quiz_attempts.id'), nullable=False)
    
    # Prediction results (matching your diagram output)
    predicted_score = db.Column(db.Float)  # 0-100
    category = db.Column(db.String(20))  # 'struggling'/'average'/'advanced'
    confidence_level = db.Column(db.Float)  # Model certainty 0-1
    
    # Learner profile as JSON
    learner_profile_json = db.Column(db.Text)
    
    # Features used for prediction
    features_json = db.Column(db.Text)  # JSON of the 15 features
    
    # Metadata
    model_version = db.Column(db.String(50), default='v1.0')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    @property
    def learner_profile(self):
        """Parse learner profile JSON"""
        if self.learner_profile_json:
            return json.loads(self.learner_profile_json)
        return {}
    
    @learner_profile.setter
    def learner_profile(self, value):
        """Store learner profile as JSON"""
        self.learner_profile_json = json.dumps(value)
    
    @property
    def features(self):
        """Parse features JSON"""
        if self.features_json:
            return json.loads(self.features_json)
        return {}
    
    @features.setter
    def features(self, value):
        """Store features as JSON"""
        self.features_json = json.dumps(value)

class StudentRecommendation(db.Model):
    __tablename__ = 'student_recommendations'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    quiz_attempt_id = db.Column(db.Integer, db.ForeignKey('quiz_attempts.id'), nullable=True)
    
    # Recommendation details
    recommendation_type = db.Column(db.String(50))  # 'quiz_difficulty', 'study_material', etc.
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    priority = db.Column(db.Integer, default=1)  # 1=high, 2=medium, 3=low
    
    # Settings/parameters as JSON
    settings_json = db.Column(db.Text)
    
    # Status tracking
    is_active = db.Column(db.Boolean, default=True)
    is_completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime)
    
    # Foreign keys
    student = db.relationship('Student', backref='recommendations')
    
    @property
    def settings(self):
        """Parse settings JSON"""
        if self.settings_json:
            return json.loads(self.settings_json)
        return {}
    
    @settings.setter
    def settings(self, value):
        """Store settings as JSON"""
        self.settings_json = json.dumps(value)

# Helper functions for database operations
class MLDataManager:
    """Helper class for ML-related database operations"""
    
    @staticmethod
    def save_prediction(quiz_attempt_id, prediction_result):
        """Save ML prediction to database"""
        try:
            prediction = MLPrediction(
                student_id=QuizAttempt.query.get(quiz_attempt_id).student_id,
                quiz_attempt_id=quiz_attempt_id,
                predicted_score=prediction_result['predicted_score'],
                category=prediction_result['category'],
                confidence_level=prediction_result['confidence_level']
            )
            
            # Store complex data as JSON
            prediction.learner_profile = prediction_result['learner_profile']
            prediction.features = prediction_result['features_used']
            
            db.session.add(prediction)
            db.session.commit()
            
            return prediction
            
        except Exception as e:
            db.session.rollback()
            raise e
    
    @staticmethod
    def save_recommendations(student_id, quiz_attempt_id, recommendations):
        """Save recommendations to database"""
        try:
            recommendation_records = []
            
            # Next quiz difficulty
            if recommendations.get('next_quiz_difficulty'):
                rec = StudentRecommendation(
                    student_id=student_id,
                    quiz_attempt_id=quiz_attempt_id,
                    recommendation_type='quiz_difficulty',
                    title=f"Recommended Quiz Level: {recommendations['next_quiz_difficulty'].title()}",
                    description=f"Based on your performance, try {recommendations['next_quiz_difficulty']} level quizzes next.",
                    priority=1
                )
                rec.settings = {'difficulty': recommendations['next_quiz_difficulty']}
                recommendation_records.append(rec)
            
            # Study materials
            for i, material in enumerate(recommendations.get('study_materials', [])):
                rec = StudentRecommendation(
                    student_id=student_id,
                    quiz_attempt_id=quiz_attempt_id,
                    recommendation_type='study_material',
                    title=f"Study Recommendation: {material}",
                    description=f"Focus on: {material}",
                    priority=i + 1
                )
                rec.settings = {'material_type': material}
                recommendation_records.append(rec)
            
            # Focus areas
            for area in recommendations.get('focus_areas', []):
                rec = StudentRecommendation(
                    student_id=student_id,
                    quiz_attempt_id=quiz_attempt_id,
                    recommendation_type='focus_area',
                    title=f"Focus Area: {area.replace('_', ' ').title()}",
                    description=f"Concentrate on improving: {area.replace('_', ' ')}",
                    priority=2
                )
                rec.settings = {'focus_area': area}
                recommendation_records.append(rec)
            
            # Hint settings
            if recommendations.get('hint_settings'):
                rec = StudentRecommendation(
                    student_id=student_id,
                    quiz_attempt_id=quiz_attempt_id,
                    recommendation_type='hint_settings',
                    title=f"Hint Setting: {recommendations['hint_settings'].title()}",
                    description=f"Your hint availability is set to {recommendations['hint_settings']} level.",
                    priority=3
                )
                rec.settings = {'hint_level': recommendations['hint_settings']}
                recommendation_records.append(rec)
            
            # Save all recommendations
            for rec in recommendation_records:
                db.session.add(rec)
            
            db.session.commit()
            return recommendation_records
            
        except Exception as e:
            db.session.rollback()
            raise e
    
    @staticmethod
    def update_student_profile(student_id, prediction_result):
        """Update student profile with latest ML insights"""
        try:
            profile = StudentProfile.query.filter_by(student_id=student_id).first()
            if not profile:
                profile = StudentProfile(student_id=student_id)
                db.session.add(profile)
            
            # Update ML-derived fields
            profile.predicted_category = prediction_result['category']
            profile.confidence_level = prediction_result['confidence_level']
            profile.last_prediction_update = datetime.now(timezone.utc)
            profile.learner_profile_json = json.dumps(prediction_result['learner_profile'])
            
            # Update counters
            profile.total_quizzes_completed += 1
            
            # Calculate new average score
            attempts = QuizAttempt.query.filter_by(
                student_id=student_id, 
                is_completed=True
            ).all()
            
            if attempts:
                scores = [a.score for a in attempts if a.score is not None]
                if scores:
                    profile.average_score = sum(scores) / len(scores)
            
            db.session.commit()
            return profile
            
        except Exception as e:
            db.session.rollback()
            raise e

# ===================== AI CHAT MODELS =====================

class ChatSession(db.Model):
    __tablename__ = 'chat_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    started_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    ended_at = db.Column(db.DateTime)
    topic_focus = db.Column(db.String(100))  # Subject the chat focused on
    
    # Relationships
    student = db.relationship('Student', backref='chat_sessions')
    messages = db.relationship('ChatMessage', backref='chat_session', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<ChatSession {self.id} - Student {self.student_id}>'

class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_sessions.id'), nullable=False)
    sender = db.Column(db.String(20), nullable=False)  # 'student' or 'ai'
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # AI-specific fields
    confidence_score = db.Column(db.Float)  # AI confidence in response (0-1)
    response_time_ms = db.Column(db.Integer)  # Time taken to generate response
    
    def __repr__(self):
        return f'<ChatMessage {self.id} - {self.sender}: {self.message[:50]}>'

class Teacher(db.Model):
    __tablename__ = 'teachers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    subject_specialization = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<Teacher {self.name}>'
