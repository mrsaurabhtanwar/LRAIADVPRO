# 🎓 Educational Platform with AI-Powered Learning Analytics

A comprehensive Flask-based edu6. **Ini7. **Start the application**
   ```bash
   python app.py
   ```

8. **Optional: Start background worker for large files**
   ```bash
   # In a new terminal window (for processing large PDFs/documents)
   python start_celery_worker.py
   ```ize the database**
   ```bash
   python populate_test_data.py
   ```platform that uses Machine Learning and AI to provide personalized learning experiences for students and intelligent quiz generation for educators.

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

### 🧠 AI-Powered Quiz Generation (NEW!)
- **Multi-Source Content Processing** - Extract content from PDFs, DOCX files, web URLs, and plain text
- **GitHub AI Integration** - Uses GitHub's FREE AI models (perfect for students!)
- **Multiple Question Types** - Support for multiple choice, true/false, fill-in-the-blank, and short answer
- **Smart Content Analysis** - Automatic keyword extraction and content chunking
- **Real-time Generation Tracking** - Live progress updates during quiz creation
- **Modern Web Interface** - Bootstrap-based responsive quiz creator and management dashboard
- **Cost-Effective** - 15,000 free requests per month with GitHub AI models

### 👨‍🏫 Teacher Features
- **Enhanced Quiz Creation Tools** - AI-powered quiz generation from various content sources
- **Quiz Management Dashboard** - Organize and manage all generated quizzes
- **File Upload Support** - Drag-and-drop uploading for documents
- **Content Processing Pipeline** - Automated extraction and analysis of educational content
- Student progress monitoring (enhanced)
- Background task processing for large documents

## 🛠️ Technology Stack

- **Backend**: Flask 2.3.3, SQLAlchemy 3.0.5
- **Database**: SQLite (development), PostgreSQL ready
- **ML/AI**: scikit-learn, pandas, numpy
- **AI Content Processing**: GitHub AI Models (FREE for students!), NLTK for natural language processing
- **Content Extraction**: PyPDF2 (PDFs), python-docx (Word docs), BeautifulSoup4 (web content)
- **Task Queue**: Celery + Redis (background processing)
- **Frontend**: HTML5, Bootstrap 5, JavaScript (with real-time updates)
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
   GITHUB_TOKEN=your-github-personal-access-token  # FREE for students!
   REDIS_URL=redis://localhost:6379/0
   ```

5. **Run the setup script**
   ```bash
   python setup.py
   ```
   This will test all dependencies and download required NLTK data.

6. **Initialize the database**
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
├── app.py                     # Main Flask application
├── models.py                  # Database models
├── extensions.py              # Shared app extensions
├── ml_predictor.py            # ML prediction engine
├── content_processor.py       # AI-powered content processing (NEW!)
├── quiz_generator.py          # Quiz generation service (NEW!)
├── enhanced_quiz_routes.py    # Quiz generation API endpoints (NEW!)
├── celery_tasks.py            # Background task processing (NEW!)
├── start_celery_worker.py     # Celery worker launcher (NEW!)
├── chat_and_teacher_routes.py # Teacher and chat features
├── quiz_routes.py             # Original quiz system
├── requirements.txt           # Python dependencies
├── setup.py                   # System setup and testing script (NEW!)
├── test_github_ai.py          # GitHub AI integration test (NEW!)
├── templates/                 # HTML templates
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── quiz_question.html
│   ├── create_quiz.html       # AI quiz creation interface (NEW!)
│   ├── manage_quizzes.html    # Quiz management dashboard (NEW!)
│   └── ...
├── static/                    # CSS, JS, images
├── uploads/                   # File upload directory (NEW!)
├── instance/                  # Database files (local)
└── populate_test_data.py      # Database seeding script
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
