"""
Cliente de OpenAI — Wrapper para llamadas de IA.
"""
import json
import logging
from typing import Any, Dict, Optional

from openai import OpenAI
from config.settings import config

logger = logging.getLogger("cleanflow.ai")


class AIClient:
    """Wrapper sobre OpenAI con parsing de JSON integrado."""

    def __init__(self):
        if not config.openai.api_key:
            raise ValueError("OPENAI_API_KEY es requerido")
        self.client = OpenAI(api_key=config.openai.api_key)
        self.model = config.openai.model
        self.temperature = config.openai.temperature

    def ask(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: int = 2000,
    ) -> str:
        """Llamada simple que retorna texto."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=temperature or self.temperature,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            raise

    def ask_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Llamada que parsea la respuesta como JSON."""
        full_system = (
            system_prompt
            + "\n\nIMPORTANT: Respond ONLY with valid JSON. "
            "No markdown, no backticks, no explanation."
        )
        raw = self.ask(full_system, user_prompt, temperature)
        # Limpiar posibles backticks
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}\nRaw: {raw[:500]}")
            return {"error": "json_parse_failed", "raw": raw[:500]}


# Singleton
ai = AIClient()
