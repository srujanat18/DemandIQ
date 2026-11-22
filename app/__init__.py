"""
Flask Application Factory for DemandIQ
"""
from flask import Flask
import config

def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "demandiq-enterprise-key-2026"
    
    # Register blueprints
    from app.routes.main_routes import main_bp
    app.register_blueprint(main_bp)

    return app
