import json
import os
from .models import db, Schedule

def load_schedule_data():
    """
    Loads garbage schedule data from schedule.json into the database.
    This function is idempotent: it updates existing entries and adds new ones.
    """
    from flask import current_app
    
    json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'schedule.json')

    with open(json_path, 'r', encoding='utf-8') as f:
        schedules_from_json = json.load(f)

    with current_app.app_context():
        for item in schedules_from_json:
            schedule = db.session.query(Schedule).filter_by(name=item['name']).first()
            
            if schedule:
                # Update existing schedule if data differs
                if (schedule.resources != item['resources'] or
                    schedule.burnable != item['burnable'] or
                    schedule.ceramic_glass_metal != item['ceramic_glass_metal']):
                    schedule.resources = item['resources']
                    schedule.burnable = item['burnable']
                    schedule.ceramic_glass_metal = item['ceramic_glass_metal']
            else:
                # Add new schedule
                schedule = Schedule(
                    name=item['name'],
                    resources=item['resources'],
                    burnable=item['burnable'],
                    ceramic_glass_metal=item['ceramic_glass_metal']
                )
                db.session.add(schedule)
        
        db.session.commit()
        print(f"Updated/loaded {len(schedules_from_json)} schedule records into the database.")

def register_cli_command(app):
    @app.cli.command('init-db')
    def init_db_command():
        """Clears the existing data and creates new tables."""
        with app.app_context():
            db.drop_all()
            db.create_all()
            print("Initialized the database.")
            load_schedule_data()
