#!/usr/bin/env bash
# Build script for Render deployment

# Exit on error
set -o errexit

echo "🚀 Starting build process for Educational Platform..."

# Upgrade pip to latest version
echo "📦 Upgrading pip..."
python -m pip install --upgrade pip

# Install Python dependencies
echo "📦 Installing dependencies from requirements.txt..."
pip install --no-cache-dir -r requirements.txt

# Verify critical packages
echo "🔍 Verifying installation..."
python -c "import flask; print(f'Flask version: {flask.__version__}')"
python -c "import sqlalchemy; print(f'SQLAlchemy version: {sqlalchemy.__version__}')"

echo "✅ Build completed successfully!"
echo "📊 Educational Platform is ready for deployment"
