#!/usr/bin/env bash
# Build script for Render deployment

# Exit on error
set -o errexit

echo "Starting build process..."

# Upgrade pip and install build tools
echo "Upgrading pip and installing build tools..."
python -m pip install --upgrade pip
python -m pip install wheel setuptools

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Initialize database
echo "Initializing database..."
python -c "
import sys
sys.path.append('.')
try:
    from app import app, db
    with app.app_context():
        db.create_all()
        print('✅ Database initialized successfully')
except Exception as e:
    print(f'❌ Database initialization failed: {e}')
    sys.exit(1)
"

echo "✅ Build completed successfully!"
