import json
import os
from .models import db, Schedule

def load_schedule_data():
    """
    Loads garbage schedule data from schedule.json into the database.
    This function is idempotent and can be run multiple times without creating duplicates.
    """
    from flask import current_app
    
    # Get the absolute path to the schedule.json file
    json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'schedule.json')

    with open(json_path, 'r', encoding='utf-8') as f:
        schedules = json.load(f)

    with current_app.app_context():
        for item in schedules:
            # Check if the schedule already exists
            exists = db.session.query(Schedule.id).filter_by(name=item['name']).first() is not None
            if not exists:
                schedule = Schedule(
                    name=item['name'],
                    resources=item['resources'],
                    burnable=item['burnable'],
                    ceramic_glass_metal=item['ceramic_glass_metal']
                )
                db.session.add(schedule)
        
        db.session.commit()
        print(f"Loaded {len(schedules)} schedule records into the database.")

def register_cli_command(app):
    @app.cli.command('init-db')
    def init_db_command():
        """Clears the existing data and creates new tables."""
        with app.app_context():
            db.drop_all()
            db.create_all()
            print("Initialized the database.")
            load_schedule_data()
