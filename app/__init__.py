import logging
import os

from dotenv import load_dotenv

load_dotenv()

from flask import Flask, jsonify, request, send_from_directory

from .config import get_config

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")


def create_app(config_name=None):
    app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")
    app.config.from_object(get_config(config_name)())

    logging.basicConfig(level=logging.INFO)

    _register_rate_limiter(app)

    from .routes import bp as api_bp

    app.register_blueprint(api_bp)

    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.errorhandler(404)
    def not_found(_err):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Not found"}), 404
        return "Not found", 404

    @app.errorhandler(500)
    def server_error(_err):
        return jsonify({"error": "Internal server error"}), 500

    return app


def _register_rate_limiter(app):
    """
    Best-effort in-memory rate limit on the API, mainly to stop accidental
    hammering of the paid AI endpoints from a single client. NOTE: in-memory
    storage means this resets per worker process and does not coordinate
    across multiple app instances — fine for a single dev/demo instance, not
    sufficient for real multi-instance production (see README).
    """
    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address

        limiter = Limiter(
            get_remote_address,
            app=app,
            default_limits=[app.config.get("RATELIMIT_DEFAULT", "30 per minute")],
            enabled=app.config.get("RATELIMIT_ENABLED", True),
        )
        app.extensions["limiter"] = limiter
    except ImportError:
        logging.getLogger(__name__).warning(
            "flask-limiter not installed — running without rate limiting."
        )