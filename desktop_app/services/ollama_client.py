# careerbuddy/services/ollama_client.py
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, Generator, List, Optional

import requests


@dataclass
class OllamaModel:
    name: str


class OllamaClient:
    """
    Minimal Ollama HTTP client (local-first).
    Default Ollama host: http://localhost:11434
    """
    def __init__(self, base_url: str = "http://localhost:11434", timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ----------------------------
    # Health / models
    # ----------------------------
    def is_running(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=self.timeout)
            return r.status_code == 200
        except Exception:
            return False

    def list_models(self) -> List[str]:
        """
        Returns model names like ["deepseek-r1:8b", "llama3.1:8b", ...]
        """
        r = requests.get(f"{self.base_url}/api/tags", timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        models = data.get("models", []) or []
        names: List[str] = []
        for m in models:
            n = m.get("name")
            if n:
                names.append(str(n))
        return names

    # ----------------------------
    # Chat (streaming)
    # ----------------------------
    def chat_stream(
        self,
        model: str,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        options: Optional[Dict] = None,
        keep_alive: str = "5m",
    ) -> Generator[str, None, None]:
        """
        Streams tokens (strings) from Ollama /api/chat.

        messages: [{"role":"user","content":"..."}, ...]
        system: optional system prompt
        options: Ollama options e.g. {"temperature":0.7}
        """
        payload: Dict = {
            "model": model,
            "messages": messages,
            "stream": True,
            "keep_alive": keep_alive,
        }
        if system:
            payload["system"] = system
        if options:
            payload["options"] = options

        with requests.post(
            f"{self.base_url}/api/chat",
            json=payload,
            stream=True,
            timeout=300,  # generation time
        ) as r:
            r.raise_for_status()

            for line in r.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue

                # Standard shape: {"message":{"role":"assistant","content":"..."}, "done":false}
                msg = obj.get("message") or {}
                chunk = msg.get("content")
                if chunk:
                    yield str(chunk)

                if obj.get("done") is True:
                    break
