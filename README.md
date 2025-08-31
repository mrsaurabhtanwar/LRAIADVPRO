# AI-Enhanced Educational Platform

An advanced educational platform that uses AI and machine learning to provide personalized quiz experiences and intelligent tutoring.

## Features

- **AI-Powered Quiz Generation**: Automatically generates quizzes based on topics with adaptive difficulty
- **Intelligent Tutoring System**: AI-driven chat interface for personalized learning assistance
- **Machine Learning Insights**: Real-time analysis of student performance and learning patterns
- **Adaptive Learning**: Adjusts content difficulty based on student performance
- **Progress Tracking**: Comprehensive analytics and progress visualization
- **Hint System**: Smart hint generation based on student learning patterns

## Technology Stack

- **Backend**: Python/Flask
- **Database**: SQLAlchemy with SQLite (production: PostgreSQL)
- **Frontend**: HTML5, Bootstrap 5, JavaScript
- **AI Integration**: Custom RAG (Retrieval-Augmented Generation) models
- **Machine Learning**: Student performance prediction and behavior analysis
- **API Integration**: External AI services for quiz generation and tutoring

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/mrsaurabhtanwar/LRAIADVPRO.git
   cd LRAIADVPRO
   ```

2. Create and activate virtual environment:
   ```bash
   python -m venv myenv
   source myenv/bin/activate  # Unix/macOS
   myenv\Scripts\activate     # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. Initialize the database:
   ```bash
   flask db upgrade
   ```

## Usage

1. Start the development server:
   ```bash
   python app.py
   ```

2. Access the platform at `http://localhost:5001`

3. Register a new account and start learning!

## System Architecture

### Components

- **Quiz Generation System**: Generates personalized quizzes using AI and fallback mechanisms
- **Student Profiling**: ML-based analysis of learning patterns and performance
- **AI Tutor**: Real-time intelligent tutoring using RAG models
- **Progress Analytics**: Comprehensive tracking and visualization of learning progress
- **Recommendation Engine**: Smart content and difficulty recommendations

### Data Flow

1. User takes quizzes and interacts with AI tutor
2. System collects behavioral and performance data
3. ML models analyze patterns and generate insights
4. Platform adapts content and difficulty dynamically
5. Personalized recommendations are provided

## API Integration

The platform integrates with two main external AI services:

1. **Quiz Generation API**: 
   - Endpoint: `https://rag-tutor-quiz-generator.onrender.com`
   - Fallback: Local CSV question bank

2. **AI Tutor API**:
   - Endpoint: `https://rag-tutor-chatbot.onrender.com`
   - Features: Real-time tutoring and hint generation

## Deployment

The platform is configured for deployment on Render.com:

1. Set up a Render account
2. Configure the PostgreSQL database
3. Set environment variables
4. Deploy using the `render.yaml` configuration

## File Structure

```
LRAIADVPRO/
├── app.py              # Main application file
├── models.py           # Database models
├── extensions.py       # Flask extensions
├── config.py          # Configuration settings
├── static/            # Static files (CSS, JS)
│   ├── css/
│   └── js/
├── templates/         # HTML templates
├── quiz_questions.csv # Fallback question bank
└── requirements.txt   # Python dependencies
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Flask Team for the excellent web framework
- Render.com for hosting support
- All contributors and testers

## Support

For support and questions, please open an issue on the GitHub repository.
