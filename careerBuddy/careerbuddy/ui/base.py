# careerbuddy/ui/base.py
import customtkinter as ctk
from typing import Dict, Any
from careerbuddy.config.theme import get as theme

DEFAULT_PAD = {"padx": 20, "pady": 10}


class BaseCTkFrame(ctk.CTkFrame):
    """
    All UI screens inherit from this class so they automatically get:
    * the package‑wide background colour (theme('bg_medium'))
    * a convenient ``padded()`` method for ``.pack()`` / ``.grid()`` calls
    """
    def __init__(self, master, **kwargs):
        fg = kwargs.pop("fg_color", theme("bg_medium"))
        super().__init__(master, fg_color=fg, **kwargs)

    @staticmethod
    def padded(**extra) -> Dict[str, Any]:
        """Return a dict that mixes the default padding with any overrides."""
        return {**DEFAULT_PAD, **extra}
