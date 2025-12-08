# careerbuddy/services/gemini.py
import logging
from typing import Any, Dict, Optional

import ollama                       # pip install ollama
try:
    import google.generativeai as genai
    GEMINI_INSTALLED = True
except Exception:
    GEMINI_INSTALLED = False

from config.settings import get_api_key
from config.theme import get as theme

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are CareerBuddy, a friendly and supportive AI career advisor designed specifically for students and recent graduates looking for jobs and internships.

Your personality:
- Encouraging and positive, but realistic
- Knowledgeable about job searching, CVs, cover letters, interviews, and career development
- Empathetic when users face rejection or feel discouraged
- Practical and actionable in your advice

Guidelines:
- Keep responses concise but helpful (2‑4 paragraphs max)
- Use emojis sparingly 🎯
- Be specific and actionable
- Celebrate wins and provide encouragement
- Suggest using the app's features when relevant

Remember: You're talking to anxious students. Be supportive!"""

class LLMClient:
    """Unified interface – Gemini if an API key exists, otherwise Ollama."""
    def __init__(self):
        self._use_gemini = False
        self._init_backend()

    # -----------------------------------------------------------------
    def _init_backend(self) -> None:
        api_key = get_api_key()
        if api_key and GEMINI_INSTALLED:
            try:
                genai.configure(api_key=api_key)
                self._gemini_model = genai.GenerativeModel(
                    model_name="gemini-2.0-flash",
                    system_instruction=SYSTEM_PROMPT,
                )
                self._use_gemini = True
                log.info("LLMClient → using Google Gemini")
                return
            except Exception as exc:
                log.warning("Gemini init failed (%s). Falling back to Ollama.", exc)

        # Fallback → Ollama
        self._ollama_model = "phi:2.7b"   # tiny, works on CPU
        self._use_gemini = False
        log.info("LLMClient → using Ollama model %s", self._ollama_model)

    # -----------------------------------------------------------------
    def generate(
        self,
        user_message: str,
        *,
        max_tokens: int = 300,
        temperature: float = 0.7,
    ) -> str:
        """Send a message to the active LLM and return plain text."""
        # ========== Gemini ==========
        if self._use_gemini:
            try:
                resp = self._gemini_model.generate_content(
                    user_message,
                    max_output_tokens=max_tokens,
                    temperature=temperature,
                )
                return resp.text
            except Exception as exc:
                log.exception("Gemini request failed")
                raise

        # ========== Ollama ==========
        payload: Dict[str, Any] = {
            "model": self._ollama_model,
            "messages": [{"role": "user", "content": user_message}],
            "system": SYSTEM_PROMPT,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            response = ollama.chat(**payload)
            return response["message"]["content"]
        except Exception as exc:
            log.exception("Ollama request failed")
            raise
