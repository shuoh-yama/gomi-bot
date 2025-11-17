from app import create_app
from app.scheduler import daily_notification_job

print("Running daily notification task...")

# Create the app object to establish context and run the job
app = create_app()
daily_notification_job(app)

print("Task finished.")
