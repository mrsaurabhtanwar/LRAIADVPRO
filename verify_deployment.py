#!/usr/bin/env python3
"""
Deployment Verification Script for Educational Platform
Checks if all required components are properly set up for deployment
"""

import os
import sys
import importlib.util

def check_file_exists(file_path, description):
    """Check if a file exists and return status"""
    exists = os.path.exists(file_path)
    status = "✅" if exists else "❌"
    print(f"{status} {description}: {file_path}")
    return exists

def check_package(package_name):
    """Check if a Python package can be imported"""
    try:
        spec = importlib.util.find_spec(package_name)
        exists = spec is not None
        status = "✅" if exists else "❌"
        print(f"{status} Package '{package_name}' available")
        return exists
    except Exception:
        print(f"❌ Package '{package_name}' not available")
        return False

def main():
    print("🚀 Educational Platform - Deployment Verification")
    print("=" * 50)
    
    all_checks_passed = True
    
    # Essential files check
    print("\n📁 Essential Files:")
    essential_files = [
        ("app.py", "Main Flask application"),
        ("requirements.txt", "Python dependencies"),
        ("runtime.txt", "Python version specification"),
        ("Procfile", "Process configuration"),
        ("build.sh", "Build script"),
        ("render.yaml", "Render configuration"),
        ("models.py", "Database models"),
        ("config.py", "Application configuration"),
        ("extensions.py", "Flask extensions")
    ]
    
    for file_path, description in essential_files:
        if not check_file_exists(file_path, description):
            all_checks_passed = False
    
    # Template files check
    print("\n🎨 Template Files:")
    template_files = [
        ("templates/base.html", "Base template"),
        ("templates/index.html", "Landing page"),
        ("templates/login.html", "Login page"),
        ("templates/register.html", "Registration page"),
        ("templates/dashboard.html", "Dashboard"),
        ("templates/chat.html", "Chat interface")
    ]
    
    for file_path, description in template_files:
        if not check_file_exists(file_path, description):
            all_checks_passed = False
    
    # Static files check
    print("\n🎭 Static Files:")
    static_files = [
        ("static/css/custom.css", "Custom CSS"),
        ("static/js/app.js", "JavaScript")
    ]
    
    for file_path, description in static_files:
        check_file_exists(file_path, description)  # Not critical for deployment
    
    # Environment files check
    print("\n🔧 Environment Configuration:")
    env_files = [
        (".gitignore", "Git ignore rules"),
        (".env.production", "Production environment template")
    ]
    
    for file_path, description in env_files:
        check_file_exists(file_path, description)
    
    print(f"\n{'='*50}")
    if all_checks_passed:
        print("✅ All essential files are present!")
        print("🚀 Ready for deployment to Render!")
        print("\n📋 Next steps:")
        print("1. Push code to GitHub repository")
        print("2. Connect repository to Render")
        print("3. Set environment variables in Render dashboard")
        print("4. Deploy!")
        return 0
    else:
        print("❌ Some essential files are missing!")
        print("Please ensure all required files are present before deployment.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
