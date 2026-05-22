"""Translation service for English to Chinese translation."""

import hashlib
import logging
import re
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)

# Translation API endpoints (fallback list)
TRANSLATION_APIS = [
    # Google Translate Unofficial API
    (
        "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=zh-CN&dt=t&q=",
        "google",
    ),
    # MyMemory API
    ("https://api.mymemory.translated.net/get?langpair=en|zh-CN&q=", "mymemory"),
]


class Translator:
    """Translation service with caching and English detection."""

    def __init__(self):
        """Initialize Translator."""
        self._cache: Dict[str, str] = {}

    def translate(self, text: str, target_lang: str = "zh-CN") -> str:
        """
        Translate text to target language.

        Args:
            text: Text to translate
            target_lang: Target language code (default: zh-CN for Chinese)

        Returns:
            Translated text, or original text if translation fails
        """
        if not text or not text.strip():
            return text

        # Check cache first
        cache_key = self._get_cache_key(text)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Translate
        translated = self._call_api(text, target_lang)
        if translated is None:
            return text

        # Cache result
        self._cache[cache_key] = translated
        return translated

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key from text hash."""
        return hashlib.md5(text.encode()).hexdigest()

    def _call_api(self, text: str, target_lang: str) -> Optional[str]:
        """
        Call translation API with fallback.

        Args:
            text: Text to translate
            target_lang: Target language code

        Returns:
            Translated text, or None if failed
        """
        # Try Google Translate API
        try:
            url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=zh-CN&dt=t&q="
            encoded_text = requests.utils.quote(text[:1000])  # Limit text length
            response = requests.get(f"{url}{encoded_text}", timeout=10)
            if response.status_code == 200:
                data = response.json()
                # Google returns: [[translated_text_parts], original_text, language, ...]
                # translated_text_parts = [[translated_text, original_text, ...], ...]
                if isinstance(data, list) and len(data) > 0:
                    translated_list = data[0]
                    if isinstance(translated_list, list) and len(translated_list) > 0:
                        translated_parts = []
                        for item in translated_list:
                            if item and item[0]:
                                translated_parts.append(item[0])
                        if translated_parts:
                            return "".join(translated_parts)
        except requests.exceptions.RequestException as e:
            logger.warning(f"Google Translate API failed: {e}")

        # Try MyMemory API as fallback
        try:
            response = requests.get(
                "https://api.mymemory.translated.net/get",
                params={"q": text[:500], "langpair": "en|zh-CN"},
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("responseStatus") == 200:
                    return data.get("responseData", {}).get("translatedText", None)
        except requests.exceptions.RequestException as e:
            logger.warning(f"MyMemory API failed: {e}")

        logger.warning("All translation APIs failed, returning original text")
        return None

    @staticmethod
    def should_translate(text: str) -> bool:
        """
        Detect if text should be translated (English content).

        Args:
            text: Text to check

        Returns:
            True if text appears to be English, False otherwise
        """
        if not text or not text.strip():
            return False

        # Count English characters vs total
        english_chars = len(re.findall(r"[a-zA-Z]", text))
        total_chars = len(re.sub(r"\s", "", text))

        if total_chars == 0:
            return False

        english_ratio = english_chars / total_chars
        return english_ratio > 0.5
