from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .models import db, User, Schedule
from .bot import line_bot_api
from linebot.v3.messaging import (
    PushMessageRequest,
    TextMessage
)

# --- Date Calculation Helpers ---
JST = timezone(timedelta(hours=+9), 'JST')
DAY_MAP = {0: '月', 1: '火', 2: '水', 3: '木', 4: '金', 5: '土', 6: '日'}

def get_nth_weekday_of_month(date_obj):
    """Calculates if the date is the 1st, 2nd, 3rd, 4th, or 5th occurrence of its weekday in the month."""
    return (date_obj.day - 1) // 7 + 1

def check_schedule(schedule_str, tomorrow):
    """
    Checks if a given schedule string matches the given date (tomorrow).
    e.g., schedule_str="月・木", tomorrow=datetime_object
    e.g., schedule_str="第1・3火", tomorrow=datetime_object
    """
    if not schedule_str:
        return False
    
    tomorrow_weekday_jp = DAY_MAP[tomorrow.weekday()]

    # Case 1: Weekly schedule (e.g., "月・木", "月・水・金")
    if '第' not in schedule_str:
        return tomorrow_weekday_jp in schedule_str

    # Case 2: Bi-weekly schedule (e.g., "第1・3火")
    try:
        parts = schedule_str.replace('第', '').split('・') # "1・3火" -> ["1", "3火"]
        target_day = parts[-1][-1] # "3火" -> "火"
        
        if tomorrow_weekday_jp != target_day:
            return False

        target_weeks_str = [p.replace(target_day, '') for p in parts] # ["1", "3"]
        target_weeks = [int(w) for w in target_weeks_str]
        nth_week = get_nth_weekday_of_month(tomorrow)
        
        return nth_week in target_weeks
    except (ValueError, IndexError) as e:
        # Log the error for debugging
        print(f"Error parsing schedule string '{schedule_str}': {e}")
        return False

# --- Scheduler Job ---

def daily_notification_job(app):
    """
    This job runs every day to check for tomorrow's garbage collection
    and sends notifications to the relevant users.
    It runs within a dedicated app context.
    """
    with app.app_context():
        app.logger.info("Running daily notification job...")
        
        tomorrow = datetime.now(JST).date() + timedelta(days=1)
        
        schedules = db.session.query(Schedule).all()
        notifications_to_send = {} # Key: user_id, Value: list of garbage types

        for schedule in schedules:
            collection_types = []
            if check_schedule(schedule.resources, tomorrow):
                collection_types.append("資源")
            if check_schedule(schedule.burnable, tomorrow):
                collection_types.append("燃やすごみ")
            if check_schedule(schedule.ceramic_glass_metal, tomorrow):
                collection_types.append("陶器・ガラス・金属ごみ")

            if not collection_types:
                continue

            # If there's a collection, find users for this schedule
            users = db.session.query(User).filter_by(area_name=schedule.name).all()
            for user in users:
                # Use a consistent message format for each user
                if user.line_user_id not in notifications_to_send:
                    notifications_to_send[user.line_user_id] = []
                notifications_to_send[user.line_user_id].extend(collection_types)

        # Send notifications
        for user_id, types in notifications_to_send.items():
            # Remove duplicates and create message
            unique_types = sorted(list(set(types)))
            full_message = f"【ゴミ出し通知】\n明日は「{'、'.join(unique_types)}」の収集日です。"
            try:
                line_bot_api.push_message(
                    PushMessageRequest(
                        to=user_id,
                        messages=[TextMessage(text=full_message)]
                    )
                )
                app.logger.info(f"Sent notification to {user_id} for types: {unique_types}")
            except Exception as e:
                app.logger.error(f"Failed to send notification to {user_id}: {e}")

def start_scheduler(app):
    """Starts the background scheduler."""
    scheduler = BackgroundScheduler(timezone=JST)
    
    # Schedule the job to run every day at 20:00 (8 PM) JST
    scheduler.add_job(
        daily_notification_job,
        trigger=CronTrigger(hour=20, minute=0, timezone=JST),
        id='daily_notification_job',
        name='Send daily garbage collection reminders',
        replace_existing=True,
        args=[app] # Pass the app instance to the job
    )
    
    try:
        scheduler.start()
        app.logger.info("Scheduler started successfully. Notifications will be sent daily at 8 PM JST.")
    except Exception as e:
        app.logger.error(f"Scheduler failed to start: {e}")