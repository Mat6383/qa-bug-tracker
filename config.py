"""Configuration de l'application QA Bug Tracker."""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuration de base."""
    GITLAB_URL = os.getenv("GITLAB_URL", "https://gitlab.example.fr")
    GITLAB_TOKEN = os.getenv("GITLAB_TOKEN", "")
    GITLAB_PROJECT_ID = os.getenv("GITLAB_PROJECT_ID", "")
    APP_MODE = os.getenv("APP_MODE", "local")
    APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
    APP_PORT = int(os.getenv("APP_PORT", 5000))
    DATABASE_PATH = os.path.join(os.path.dirname(__file__), "qa_bug_tracker.db")
    SECRET_KEY = os.getenv("SECRET_KEY", "qa-bug-tracker-secret-key-change-me")

    @property
    def is_mock_mode(self):
        """Mode mock si pas de token GitLab."""
        return not self.GITLAB_TOKEN

    @property
    def is_local(self):
        return self.APP_MODE == "local"


config = Config()
