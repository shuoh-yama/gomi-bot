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

    print(f"--- DATABASE_URL IN USE: {database_url} ---")

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

        # --- Database Initialization ---
        # This logic runs only if the 'users' table doesn't exist,
        # preventing data wipes on server restarts (e.g., Render sleep).
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        if not inspector.has_table("users"):
            print("--- 'users' table not found. Initializing database... ---")
            db.create_all()
            
            from .data import load_schedule_data
            load_schedule_data()
            print("--- Database initialized. ---")
        else:
            print("--- Database already initialized. Skipping. ---")

    return app
