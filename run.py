from app import app, db
from models import *

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Create sample data if database is empty
        if not Topic.query.first():
            # Create sample topics
            topics = [
                Topic(name="Algebra Basics", subject="Mathematics", description="Basic algebraic concepts", difficulty_level="easy"),
                Topic(name="Python Programming", subject="Computer Science", description="Introduction to Python", difficulty_level="medium"),
                Topic(name="World History", subject="History", description="Major historical events", difficulty_level="medium"),
            ]
            
            for topic in topics:
                db.session.add(topic)
            
            # Create sample teacher
            from werkzeug.security import generate_password_hash
            teacher = Teacher(
                name="John Doe",
                email="teacher@example.com",
                password_hash=generate_password_hash("password123"),
                subject="Mathematics"
            )
            db.session.add(teacher)
            
            db.session.commit()
            print("Sample data created!")
    
    app.run(debug=True, host='0.0.0.0', port=5000)