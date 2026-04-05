"""
Configuration settings for the Healmate app.

This module contains all configuration constants and credentials.
"""

import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration."""

    # Login credentials (consider using environment variables for security)
    HEALMATE_EMAIL = "youcan9160@gmail.com"
    HEALMATE_PASSWORD = "oy19740619"

    # OpenAI configuration
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    # URLs
    LOGIN_URL = "https://healmate.jp/login"
    MY_PROFILE_URL = (
        "https://my.healmate.jp/detail?" "code=iz3v8aswptmuunp&backpage=profile"
    )

    # Selectors
    PROFILE_SELECTOR = (
        "p.detailNickname, p.detailText, div.detailFlaxBetween, "
        "div.detailNickname, div.detailTitle, div.detailText"
    )

    # Model settings
    LLM_MODEL = "gpt-4o-mini"

    @classmethod
    def validate(cls) -> bool:
        """
        Validate that required configuration is present.

        Returns:
            bool: True if configuration is valid, False otherwise
        """
        if not cls.OPENAI_API_KEY:
            print("Warning: OPENAI_API_KEY not found in environment variables")
            return False
        return True
