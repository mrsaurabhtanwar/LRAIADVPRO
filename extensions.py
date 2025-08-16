"""Shared extensions for the Flask app.

Note: Celery is optional in this deployment. To avoid hard failures when the
celery package isn't installed, we import it lazily inside the factory.
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def make_celery(app):
    """Create a Celery instance bound to the Flask app.

    Raises a clear error if Celery isn't installed and this factory is called.
    """
    try:
        from celery import Celery  # Lazy import so app can start without celery
    except ImportError as exc:
        raise RuntimeError(
            "Celery is not installed. Add 'celery' to requirements and configure a broker to use background tasks."
        ) from exc

    celery_app = Celery(
        app.import_name,
        backend=app.config.get('CELERY_RESULT_BACKEND'),
        broker=app.config.get('CELERY_BROKER_URL'),
    )
    celery_app.conf.update(app.config)

    class ContextTask(celery_app.Task):
        """Make celery tasks work with Flask app context."""
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app.Task = ContextTask
    return celery_app
