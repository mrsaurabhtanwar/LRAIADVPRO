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

echo "✅ Build completed successfully!"
echo "Note: Database will be initialized automatically when the app starts"
