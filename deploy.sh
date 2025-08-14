#!/bin/bash
# deploy.sh - Simple deployment script

echo "🚀 Starting Educational Platform Deployment..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install/update dependencies
echo "📚 Installing dependencies..."
pip install -r requirements.txt

# Set up environment file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "⚙️ Creating .env file from template..."
    cp .env.example .env
    echo "❗ Please edit .env file with your configuration before running the app"
fi

# Initialize database with test data
echo "🗄️ Setting up database..."
python populate_test_data.py

echo "✅ Deployment complete!"
echo ""
echo "🌐 To start the application:"
echo "   source venv/bin/activate"
echo "   python app.py"
echo ""
echo "🔗 Then visit: http://localhost:5001"
echo "👤 Test credentials: test@example.com / password123"
