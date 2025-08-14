# 🎓 Educational Platform with AI-Powered Learning Analytics

A comprehensive Flask-based educational platform that uses Machine Learning to provide personalized learning experiences for students.

## 🌟 Features

### 📚 Student Portal
- **User Registration & Authentication** - Secure login system with password hashing
- **Interactive Dashboard** - Personalized recommendations and progress tracking
- **Dynamic Quiz System** - Adaptive quizzes with confidence tracking
- **ML-Powered Analytics** - Performance prediction and learning insights
- **Progress Tracking** - Comprehensive analytics and improvement suggestions

### 🤖 AI & Machine Learning
- **Performance Prediction** - 15-feature ML model for student performance analysis
- **Learning Style Analysis** - Personalized learning profile generation
- **Adaptive Recommendations** - Smart suggestions for study materials and difficulty levels
- **Real-time Analytics** - Live performance tracking and insights

### 👨‍🏫 Teacher Features (In Development)
- Teacher dashboard (placeholder)
- Student progress monitoring (planned)
- Quiz creation tools (planned)

## 🛠️ Technology Stack

- **Backend**: Flask 2.3.3, SQLAlchemy 3.0.5
- **Database**: SQLite (development), PostgreSQL ready
- **ML/AI**: scikit-learn, pandas, numpy
- **Task Queue**: Celery + Redis
- **Frontend**: HTML5, Bootstrap 5, JavaScript
- **Authentication**: Werkzeug security

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Redis server (for background tasks)
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/educational-platform.git
   cd educational-platform
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   
   # On Windows
   venv\Scripts\activate
   
   # On Linux/Mac
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   # Create .env file
   cp .env.example .env
   
   # Edit .env with your configurations
   SECRET_KEY=your-secret-key-here
   OPENAI_API_KEY=your-openai-api-key  # Optional
   REDIS_URL=redis://localhost:6379/0
   ```

5. **Initialize the database**
   ```bash
   python populate_test_data.py
   ```

6. **Start the application**
   ```bash
   python app.py
   ```

7. **Access the platform**
   - Open your browser to `http://127.0.0.1:5001`
   - Use test credentials: `test@example.com` / `password123`

## 📊 ML Features

The platform implements a sophisticated ML pipeline with 15 key features:

### Feature Set
- **Performance Metrics**: Score, confidence levels, efficiency indicators
- **Behavioral Patterns**: Hint usage, time management, attempt patterns  
- **Learning Analytics**: Historical performance, improvement trends, consistency scores
- **Engagement Data**: Session duration, question response times

### Prediction Categories
- **Struggling Students** (< 60%): Need additional support and guided practice
- **Average Performers** (60-85%): Standard difficulty with targeted improvements
- **Advanced Learners** (> 85%): Challenge problems and accelerated content

## 🏗️ Project Structure

```
educational-platform/
├── app.py                 # Main Flask application
├── models.py              # Database models
├── extensions.py          # Shared app extensions
├── ml_predictor.py        # ML prediction engine
├── requirements.txt       # Python dependencies
├── templates/             # HTML templates
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── quiz_question.html
│   └── ...
├── static/               # CSS, JS, images
├── instance/             # Database files (local)
└── populate_test_data.py # Database seeding script
```

## 🧪 Testing

### Run Tests
```bash
# Basic functionality test
python simple_test.py

# Database population (with test data)
python populate_test_data.py
```

### Test Credentials
- **Email**: test@example.com
- **Password**: password123

## 🔧 Configuration

### Environment Variables
```env
# Flask Configuration
SECRET_KEY=your-secret-key-here
FLASK_ENV=development
DEBUG=True

# Database
DATABASE_URL=sqlite:///educational_platform.db

# Redis/Celery (Optional)
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# OpenAI (Optional)
OPENAI_API_KEY=your-openai-api-key
```

## 🐳 Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up --build

# Access at http://localhost:5001
```

## 📈 ML Model Details

### Performance Prediction Model
- **Algorithm**: Random Forest Classifier (with XGBoost fallback)
- **Features**: 15 engineered features from user interaction data
- **Accuracy**: Tuned for educational context with confidence scoring
- **Fallback**: Graceful degradation when ML model is unavailable

### Recommendation Engine
- **Adaptive Difficulty**: Dynamic quiz difficulty adjustment
- **Study Materials**: Personalized content recommendations  
- **Learning Paths**: Customized progression based on performance
- **Hint Systems**: Intelligent hint delivery based on learning style

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔮 Future Enhancements

- [ ] **Teacher Dashboard** - Complete implementation
- [ ] **Advanced Analytics** - Real-time learning dashboards
- [ ] **Mobile App** - React Native companion app
- [ ] **Video Integration** - Embedded learning videos
- [ ] **Collaborative Features** - Study groups and peer learning
- [ ] **Advanced ML** - Deep learning models for content generation
- [ ] **API Integration** - RESTful API for third-party integrations

## 💡 Support

- 📧 Email: support@yourplatform.com
- 📖 Documentation: [Wiki](https://github.com/yourusername/educational-platform/wiki)
- 🐛 Issues: [GitHub Issues](https://github.com/yourusername/educational-platform/issues)

## 🙏 Acknowledgments

- Flask community for excellent documentation
- scikit-learn for robust ML algorithms
- Bootstrap for responsive UI components
- OpenAI for AI integration possibilities

---

⭐ **Star this repository if it helped you!**

Built with ❤️ for education and powered by AI 🤖
