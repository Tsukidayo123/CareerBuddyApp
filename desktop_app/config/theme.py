# careerbuddy/config/theme.py
from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    # 🎴 Core felt / table colors
    bg_dark: str = "#0F1F17"        # Deep casino green felt
    bg_medium: str = "#162B22"     # Slightly lighter felt texture

    # 🟥 Wood / velvet trim
    secondary: str = "#2E1A12"     # Dark burgundy wood

    # ✨ Gold accents (foil look)
    accent: str = "#D4AF37"        # Metallic gold
    accent_hover: str = "#E6C36A"  # Lighter gold on hover

    # 🧾 Card parchment text
    text: str = "#F5E6C8"          # Warm ivory parchment

    # ✅ Positive / negative states
    success: str = "#2ECC71"       # Win green
    warning: str = "#C0392B"       # Red heart warning

    # ♠♣ Accent suits
    purple: str = "#5B2A86"        # Royal card purple
    purple_hover: str = "#7B38B2"  # Brighter royal hover


# Current theme instance
CURRENT = Palette()


def get(name: str) -> str:
    """Convenient `theme.get('accent')` used throughout the UI."""
    return getattr(CURRENT, name)
