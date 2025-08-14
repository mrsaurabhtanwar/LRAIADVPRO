# models.py - Updated models to support ML predictions
from extensions import db
from datetime import datetime
import json

class Student(db.Model):
    __tablename__ = 'students'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    student_id = db.Column(db.String(50), unique=True, nullable=False)
    class_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    profile = db.relationship('StudentProfile', backref='student', uselist=False)
    quiz_attempts = db.relationship('QuizAttempt', backref='student', lazy='dynamic')
    ml_predictions = db.relationship('MLPrediction', backref='student', lazy='dynamic')

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
    
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Topic(db.Model):
    __tablename__ = 'topics'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    difficulty_level = db.Column(db.String(20), default='medium')  # easy/medium/hard
    subject = db.Column(db.String(50), nullable=False)
    
    # Relationships
    quizzes = db.relationship('Quiz', backref='topic', lazy='dynamic')

class Quiz(db.Model):
    __tablename__ = 'quizzes'
    
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    questions_json = db.Column(db.Text, nullable=False)  # JSON string of questions
    difficulty_level = db.Column(db.String(20), default='medium')
    max_score = db.Column(db.Integer, default=100)
    time_limit = db.Column(db.Integer)  # in seconds
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    attempts = db.relationship('QuizAttempt', backref='quiz', lazy='dynamic')

class QuizAttempt(db.Model):
    __tablename__ = 'quiz_attempts'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False)
    
    # Basic attempt info
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    score = db.Column(db.Float)
    max_score = db.Column(db.Float, default=100)
    
    # ML Feature fields (matching your 15 features)
    hints_used = db.Column(db.Integer, default=0)
    reached_final_hint = db.Column(db.Boolean, default=False)
    attempt_number = db.Column(db.Integer, default=1)
    time_to_first_answer = db.Column(db.Float)  # seconds
    average_confidence = db.Column(db.Float, default=0.5)  # 0-1
    
    # Detailed responses for analysis
    responses_json = db.Column(db.Text)  # JSON of question responses
    timing_data_json = db.Column(db.Text)  # JSON of timing per question
    
    # Status
    is_completed = db.Column(db.Boolean, default=False)
    
    # Relationships
    ml_prediction = db.relationship('MLPrediction', backref='quiz_attempt', uselist=False)
    recommendations = db.relationship('StudentRecommendation', backref='quiz_attempt', lazy='dynamic')

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
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
            profile.last_prediction_update = datetime.utcnow()
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