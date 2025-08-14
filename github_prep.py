# github_prep.py - Final preparation script for GitHub
import os
import shutil
import subprocess

def clean_project():
    """Clean up temporary files and prepare for GitHub"""
    
    print("🧹 Cleaning project for GitHub...")
    
    # Files and directories to remove
    cleanup_items = [
        '__pycache__',
        '*.pyc',
        '*.pyo', 
        '*.pyd',
        'instance/',
        '.pytest_cache',
        'test_login.py',  # Remove test files
        'simple_test.py',
        'student_model.pkl'  # Remove sample model (too large for git)
    ]
    
    for item in cleanup_items:
        if os.path.exists(item):
            if os.path.isdir(item):
                shutil.rmtree(item)
                print(f"   ✅ Removed directory: {item}")
            else:
                os.remove(item)
                print(f"   ✅ Removed file: {item}")
    
    # Clean up __pycache__ directories recursively
    for root, dirs, files in os.walk('.'):
        if '__pycache__' in dirs:
            pycache_path = os.path.join(root, '__pycache__')
            shutil.rmtree(pycache_path)
            print(f"   ✅ Removed: {pycache_path}")

def check_requirements():
    """Check if all required files exist"""
    
    print("\n📋 Checking required files...")
    
    required_files = [
        'README.md',
        'requirements.txt', 
        'app.py',
        'models.py',
        'extensions.py',
        '.gitignore',
        '.env.example',
        'LICENSE'
    ]
    
    missing_files = []
    for file in required_files:
        if os.path.exists(file):
            print(f"   ✅ {file}")
        else:
            print(f"   ❌ {file} - MISSING")
            missing_files.append(file)
    
    return len(missing_files) == 0

def run_final_tests():
    """Run final tests before GitHub push"""
    
    print("\n🧪 Running final tests...")
    
    try:
        # Test imports
        subprocess.run(['python', '-c', 'import app; print("✅ App imports successfully")'], check=True)
        
        # Test database creation
        subprocess.run(['python', '-c', '''
import app
with app.app.app_context():
    from extensions import db
    db.create_all()
    print("✅ Database creation works")
'''], check=True)
        
        print("✅ All tests passed!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Test failed: {e}")
        return False

def show_git_commands():
    """Show Git commands for pushing to GitHub"""
    
    print("\n🚀 Ready for GitHub! Run these commands:")
    print()
    print("   # Initialize Git repository (if not done)")
    print("   git init")
    print()
    print("   # Add all files")
    print("   git add .")
    print()
    print("   # Create initial commit")
    print('   git commit -m "Initial commit: Educational Platform with ML"')
    print()
    print("   # Add GitHub remote (replace with your repository URL)")
    print("   git remote add origin https://github.com/yourusername/educational-platform.git")
    print()
    print("   # Push to GitHub")
    print("   git branch -M main")
    print("   git push -u origin main")
    print()
    print("🌟 Don't forget to:")
    print("   • Create .env file from .env.example")
    print("   • Set up your repository secrets for CI/CD")
    print("   • Update README.md with your GitHub username")

def main():
    """Main preparation function"""
    
    print("🎯 Educational Platform - GitHub Preparation")
    print("=" * 50)
    
    # Clean the project
    clean_project()
    
    # Check requirements
    if not check_requirements():
        print("\n❌ Missing required files. Please create them first.")
        return False
    
    # Run tests
    if not run_final_tests():
        print("\n❌ Tests failed. Please fix issues before pushing to GitHub.")
        return False
    
    # Show Git commands
    show_git_commands()
    
    print("\n🎉 Project is ready for GitHub!")
    return True

if __name__ == "__main__":
    main()
