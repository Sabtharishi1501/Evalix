"""
Local development entry point.

    python run.py

For production, use wsgi.py with a real WSGI server (see README).
"""

import os

from dotenv import load_dotenv

load_dotenv()  # loads .env into os.environ if present, before create_app reads config

from app import create_app  # noqa: E402  (import after load_dotenv on purpose)

app = create_app("development")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)