# ui_qt/base.py
from __future__ import annotations

# Central theme palette for the entire Qt UI.
# Keep this stable so pages don't break with KeyErrors.

palette = {
    # Backgrounds
    "bg_dark": "#0F1E1A",          # app background (deep green-black)
    "bg_medium": "rgba(0,0,0,0.28)",  # panels / columns background
    "panel": "rgba(0,0,0,0.22)",   # inner panels / cards
    "panel_2": "rgba(255,255,255,0.06)",

    # Text
    "text": "#E9F3EE",
    "muted": "#9FB6AE",

    # Accents (card-gold theme)
    "accent": "#E7C35B",
    "accent_hover": "#F0D073",
    "accent2": "#7FE6D6",  # teal-ish (clubs vibe)

    # Status / semantic
    "success": "#43D17A",
    "warning": "#F2A65A",
    "danger": "#FF5C5C",

    # Borders / shadows
    "border": "rgba(255,255,255,0.10)",
    "border_soft": "rgba(255,255,255,0.07)",
    
    "bg_dark": "#0F1E1A",        # table felt
    "bg_medium": "rgba(255,255,255,0.06)",  # trays / panels
    "panel": "rgba(0,0,0,0.25)", # inner panel
    "text": "#E9F3EE",
    "muted": "#9FB6AE",

    "accent": "#E7C35B",         # gold
    "accent2": "#49C6B6",        # teal (club vibe)
    "danger": "#E74C3C",
}
