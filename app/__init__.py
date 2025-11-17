import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi
)
from linebot.v3.webhook import WebhookHandler

# Create LINE API client and handler here to avoid circular import
configuration = Configuration(access_token=os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
api_client = ApiClient(configuration)
line_bot_api = MessagingApi(api_client)
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))

db = SQLAlchemy()

def create_app():
    """Flask application factory."""
    load_dotenv()

    app = Flask(__name__, instance_relative_config=True)
    
    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Get database URL from environment variable, fallback to SQLite for local dev
    database_url = os.getenv('DATABASE_URL', f"sqlite:///{os.path.join(app.instance_path, 'app.sqlite')}")
    # Render uses postgres:// but SQLAlchemy needs postgresql://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    app.config.from_mapping(
        SECRET_KEY=os.getenv('SECRET_KEY', 'dev'),
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    db.init_app(app)

    with app.app_context():
        # Register blueprints and commands
        from . import bot
        app.register_blueprint(bot.bp)
        from . import data
        data.register_cli_command(app)

        # Create database tables and load data if they don't exist
        from .data import load_schedule_data
        db.create_all()
        load_schedule_data()

    return app
