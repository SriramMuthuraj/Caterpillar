"""Flask application entry point for the CAT_SRTS backend."""

from pathlib import Path
import sys

from flask import Flask
from flask_cors import CORS

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import Config
from routes.alerts_routes import alerts_bp
from routes.assignment_routes import assignment_bp
from routes.dashboard_routes import dashboard_bp
from routes.equipment_routes import equipment_bp
from routes.health import health_bp
from routes.operator_routes import operator_bp
from routes.usage_routes import usage_bp


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app)
    app.register_blueprint(health_bp)
    app.register_blueprint(equipment_bp)
    app.register_blueprint(operator_bp)
    app.register_blueprint(assignment_bp)
    app.register_blueprint(usage_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(alerts_bp)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        host=app.config["HOST"],
        port=app.config["PORT"],
        debug=app.config["DEBUG"],
    )
