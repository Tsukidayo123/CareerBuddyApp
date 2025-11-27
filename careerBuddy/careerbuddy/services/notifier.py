# careerbuddy/services/notifier.py
import platform
from plyer import notification

def notify_user(title: str, message: str) -> None:
    """
    Cross‑platform desktop notification.
    Plyer works on Windows, macOS, and most Linux distros.
    """
    notification.notify(
        title=title,
        message=message,
        app_name="CareerBuddy",
        timeout=10,
    )
