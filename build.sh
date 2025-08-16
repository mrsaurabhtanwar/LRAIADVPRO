#!/usr/bin/env bash
# Build script for Render deployment

# Exit on error
set -o errexit

echo "🚀 Starting build process..."

# Upgrade pip to latest version
echo "📦 Upgrading pip..."
python -m pip install --upgrade pip

# Install Python dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Initialize database
echo "🗄️  Initializing database..."
python -c "
import os
import sys

# Add current directory to Python path
sys.path.insert(0, os.getcwd())

try:
    from app import app, db
    with app.app_context():
        db.create_all()
        print('✅ Database tables created successfully')
except ImportError as e:
    print(f'❌ Import error: {e}')
    print('📝 Available files:', os.listdir('.'))
    sys.exit(1)
except Exception as e:
    print(f'❌ Database initialization error: {e}')
    sys.exit(1)
"

echo "✅ Build completed successfully!"
