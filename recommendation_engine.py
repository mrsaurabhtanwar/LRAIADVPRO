class RecommendationEngine:
    def __init__(self):
        self.analytics = LearningAnalytics()
    
    def generate_recommendations(self, prediction_result, student_id):
        """
        Generate recommendations based on ML prediction
        Following the logic from your diagram
        """
        score = prediction_result['predicted_score']
        category = prediction_result['category']
        profile = prediction_result['learner_profile']
        
        recommendations = {
            'next_quiz_difficulty': 'medium',
            'hint_settings': 'default',
            'study_materials': [],
            'focus_areas': [],
            'learning_path': 'continue'
        }
        
        if score < 60:  # Struggling students
            recommendations.update({
                'next_quiz_difficulty': 'easy',
                'hint_settings': 'generous',
                'study_materials': [
                    'Basic concept review',
                    'Step-by-step tutorials',
                    'Practice exercises with solutions'
                ],
                'focus_areas': ['fundamental_concepts', 'basic_problem_solving'],
                'learning_path': 'remediation'
            })
            
        elif score > 85:  # Advanced students
            recommendations.update({
                'next_quiz_difficulty': 'hard',
                'hint_settings': 'minimal',
                'study_materials': [
                    'Advanced topics',
                    'Challenge problems',
                    'Real-world applications'
                ],
                'focus_areas': ['advanced_concepts', 'application_skills'],
                'learning_path': 'acceleration'
            })
            
        else:  # Average students
            recommendations.update({
                'next_quiz_difficulty': 'medium',
                'hint_settings': 'moderate',
                'study_materials': [
                    'Targeted practice',
                    'Concept reinforcement',
                    'Mixed difficulty exercises'
                ],
                'focus_areas': self.identify_weak_areas(prediction_result),
                'learning_path': 'standard'
            })
        
        # Adjust based on learner profile
        if profile.get('support_needed') == 'high':
            recommendations['hint_settings'] = 'generous'
            recommendations['study_materials'].append('Interactive tutorials')
        
        if profile.get('learning_pace') == 'fast':
            recommendations['study_materials'].append('Self-paced modules')
        elif profile.get('learning_pace') == 'deliberate':
            recommendations['study_materials'].append('Detailed explanations')
        
        return recommendations
    
    def identify_weak_areas(self, prediction_result):
        """Identify areas needing improvement"""
        features = prediction_result.get('features_used', {})
        weak_areas = []
        
        if features.get('average_confidence', 1) < 0.6:
            weak_areas.append('confidence_building')
        
        if features.get('efficiency_indicator', 1) < 0.05:
            weak_areas.append('problem_solving_speed')
        
        if features.get('hint_count', 0) > 3:
            weak_areas.append('independent_thinking')
        
        return weak_areas if weak_areas else ['general_review']