# careerbuddy/config/settings.py
import sqlite3
from pathlib import Path
from typing import Optional

# The DB lives one level **above** the package (next to the repo root)
DB_PATH = Path(__file__).resolve().parents[2] / "career_buddy.db"

def _conn():
    return sqlite3.connect(DB_PATH)

def get_api_key() -> Optional[str]:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key='gemini_api_key'")
        row = cur.fetchone()
        return row[0] if row else None

def save_api_key(key: str) -> None:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('gemini_api_key', ?)",
            (key,),
        )
        conn.commit()

def get_theme_mode() -> str:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key='theme_mode'")
        row = cur.fetchone()
        return row[0] if row else "Dark"

def save_theme_mode(mode: str) -> None:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('theme_mode', ?)",
            (mode,),
        )
        conn.commit()
