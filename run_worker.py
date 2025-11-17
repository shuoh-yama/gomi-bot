import time
from app import create_app
from app.scheduler import start_scheduler

print("Starting background worker...")

# Create the app object to establish context
app = create_app()

# The scheduler runs in a background thread.
# The main thread needs to be kept alive for the process to continue running.
start_scheduler(app)

print("Worker started. Scheduler is running in the background.")

# Keep the main thread alive
while True:
    time.sleep(3600)
