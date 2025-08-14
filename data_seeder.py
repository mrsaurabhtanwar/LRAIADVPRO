from app import app, db
from models import *
from werkzeug.security import generate_password_hash
import json

def seed_database():
    """Populate database with sample data for testing"""
    with app.app_context():
        # Clear existing data (be careful in production!)
        db.drop_all()
        db.create_all()
        
        print("Creating sample topics...")
        
        # Mathematics Topics
        math_topics = [
            {
                'name': 'Algebra Basics',
                'subject': 'Mathematics',
                'difficulty_level': 'easy',
                'description': 'Introduction to algebraic expressions and equations',
                'content': """
                Algebra is the branch of mathematics that uses letters and symbols to represent numbers and quantities in formulas and equations.
                
                Key concepts:
                - Variables: Letters that represent unknown numbers (x, y, z)
                - Expressions: Combinations of numbers, variables, and operations (2x + 3)
                - Equations: Mathematical statements showing equality (2x + 3 = 7)
                - Solving equations: Finding the value of variables that make equations true
                
                Basic operations:
                - Addition and subtraction of like terms
                - Multiplication and division of variables
                - Distributive property: a(b + c) = ab + ac
                - Combining like terms: 3x + 2x = 5x
                """
            },
            {
                'name': 'Geometry Fundamentals',
                'subject': 'Mathematics', 
                'difficulty_level': 'medium',
                'description': 'Basic geometric shapes, properties, and calculations',
                'content': """
                Geometry is the study of shapes, sizes, positions, and properties of space.
                
                Basic shapes:
                - Point: A location with no dimension
                - Line: Extends infinitely in both directions
                - Ray: Has one endpoint and extends infinitely
                - Line segment: Has two endpoints
                
                Angles:
                - Acute angle: Less than 90 degrees
                - Right angle: Exactly 90 degrees  
                - Obtuse angle: Greater than 90 degrees but less than 180 degrees
                - Straight angle: Exactly 180 degrees
                
                Polygons:
                - Triangle: 3 sides, angles sum to 180°
                - Square: 4 equal sides, 4 right angles
                - Rectangle: 4 sides, opposite sides equal, 4 right angles
                - Circle: All points equidistant from center
                """
            }
        ]
        
        # Science Topics
        science_topics = [
            {
                'name': 'Introduction to Physics',
                'subject': 'Physics',
                'difficulty_level': 'medium',
                'description': 'Basic concepts of motion, forces, and energy',
                'content': """
                Physics is the science that studies matter, motion, energy, and forces.
                
                Motion:
                - Distance: How far an object travels
                - Speed: Distance traveled per unit time (v = d/t)
                - Velocity: Speed with direction
                - Acceleration: Change in velocity over time
                
                Forces:
                - Force causes objects to accelerate
                - Newton's First Law: Objects at rest stay at rest unless acted upon by force
                - Newton's Second Law: F = ma (Force = mass × acceleration)
                - Newton's Third Law: For every action, there's an equal and opposite reaction
                
                Energy:
                - Kinetic energy: Energy of motion (KE = ½mv²)
                - Potential energy: Stored energy
                - Conservation of energy: Energy cannot be created or destroyed
                """
            },
            {
                'name': 'Basic Chemistry',
                'subject': 'Chemistry',
                'difficulty_level': 'medium',
                'description': 'Atoms, elements, and chemical reactions',
                'content': """
                Chemistry is the study of matter and the changes it undergoes.
                
                Atoms:
                - Smallest unit of matter
                - Contains protons, neutrons, and electrons
                - Protons have positive charge
                - Electrons have negative charge
                - Neutrons have no charge
                
                Elements:
                - Pure substances made of one type of atom
                - Organized in the Periodic Table
                - Examples: Hydrogen (H), Carbon (C), Oxygen (O)
                
                Chemical Reactions:
                - Process where substances change into different substances
                - Reactants → Products
                - Mass is conserved in chemical reactions
                - Types: synthesis, decomposition, single replacement, double replacement
                """
            }
        ]
        
        # Programming Topics  
        programming_topics = [
            {
                'name': 'Python Basics',
                'subject': 'Computer Science',
                'difficulty_level': 'easy',
                'description': 'Introduction to Python programming language',
                'content': """
                Python is a high-level, interpreted programming language known for its simplicity and readability.
                
                Basic Concepts:
                - Variables: Store data (name = "John", age = 25)
                - Data Types: int, float, string, boolean, list, dict
                - Print function: print("Hello World")
                - Input function: input("Enter your name: ")
                
                Control Structures:
                - If statements: Execute code based on conditions
                - Loops: Repeat code (for loop, while loop)
                - Functions: Reusable blocks of code
                
                Basic Operations:
                - Arithmetic: +, -, *, /, %, **
                - Comparison: ==, !=, <, >, <=, >=
                - Logical: and, or, not
                
                Example:
                if age >= 18:
                    print("You are an adult")
                else:
                    print("You are a minor")
                """
            }
        ]
        
        all_topics = math_topics + science_topics + programming_topics
        
        for topic_data in all_topics:
            topic = Topic(**topic_data)
            db.session.add(topic)
        
        print("Creating sample teachers...")
        
        # Create sample teachers
        teachers = [
            Teacher(
                name="Dr. Sarah Johnson",
                email="sarah.johnson@school.edu",
                password_hash=generate_password_hash("teacher123"),
                subject="Mathematics"
            ),
            Teacher(
                name="Prof. Michael Chen", 
                email="michael.chen@school.edu",
                password_hash=generate_password_hash("teacher123"),
                subject="Physics"
            ),
            Teacher(
                name="Ms. Lisa Rodriguez",
                email="lisa.rodriguez@school.edu", 
                password_hash=generate_password_hash("teacher123"),
                subject="Computer Science"
            )
        ]
        
        for teacher in teachers:
            db.session.add(teacher)
        
        print("Creating sample students...")
        
        # Create sample students
        students = [
            Student(
                name="Alice Smith",
                student_id="STU001", 
                class_name="Grade 10",
                email="alice@student.edu",
                password_hash=generate_password_hash("student123")
            ),
            Student(
                name="Bob Wilson",
                student_id="STU002",
                class_name="Grade 10", 
                email="bob@student.edu",
                password_hash=generate_password_hash("student123")
            ),
            Student(
                name="Carol Davis",
                student_id="STU003",
                class_name="Grade 11",
                email="carol@student.edu", 
                password_hash=generate_password_hash("student123")
            )
        ]
        
        for student in students:
            db.session.add(student)
        
        db.session.commit()
        
        # Create student profiles
        print("Creating student profiles...")
        for student in Student.query.all():
            profile = StudentProfile(student_id=student.id)
            db.session.add(profile)
        
        db.session.commit()
        
        print("Database seeded successfully!")
        print("\nLogin credentials:")
        print("Teachers:")
        print("- sarah.johnson@school.edu / teacher123")
        print("- michael.chen@school.edu / teacher123") 
        print("- lisa.rodriguez@school.edu / teacher123")
        print("\nStudents:")
        print("- STU001 / student123 (Alice Smith)")
        print("- STU002 / student123 (Bob Wilson)")
        print("- STU003 / student123 (Carol Davis)")

if __name__ == '__main__':
    seed_database()
