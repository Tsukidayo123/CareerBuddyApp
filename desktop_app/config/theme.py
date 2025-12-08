# careerbuddy/config/theme.py
from dataclasses import dataclass

@dataclass(frozen=True)
class Palette:
    bg_dark: str = "#1a1a2e"
    bg_medium: str = "#16213e"
    accent: str = "#e94560"
    accent_hover: str = "#c73e54"
    secondary: str = "#0f3460"
    text: str = "#eaeaea"
    success: str = "#4ecca3"
    warning: str = "#ffc107"
    purple: str = "#7b2cbf"
    purple_hover: str = "#5a189a"

# The *current* theme – we’ll later allow toggling Light/Dark
CURRENT = Palette()

def get(name: str) -> str:
    """Convenient `theme.get('accent')` used throughout the UI."""
    return getattr(CURRENT, name)
