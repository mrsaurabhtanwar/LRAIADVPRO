# extensions.py - shared objects for app
from flask_sqlalchemy import SQLAlchemy
from celery import Celery

db = SQLAlchemy()

def make_celery(app):
    """Factory function to create Celery instance"""
    celery_app = Celery(
        app.import_name,
        backend=app.config.get('CELERY_RESULT_BACKEND'),
        broker=app.config.get('CELERY_BROKER_URL')
    )
    celery_app.conf.update(app.config)
    
    class ContextTask(celery_app.Task):
        """Make celery tasks work with Flask app context."""
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    celery_app.Task = ContextTask
    return celery_app
