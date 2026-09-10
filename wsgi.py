"""
Production WSGI entry point.

    gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app

`load_dotenv()` is a no-op if no .env file exists (e.g. in a real deployment
where env vars are injected by the platform instead) so this is safe either way.
"""

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402

app = create_app("production")