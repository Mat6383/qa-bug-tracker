import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    GITLAB_URL = os.getenv("GITLAB_URL", "https://gitlab.example.com")
    GITLAB_TOKEN = os.getenv("GITLAB_TOKEN", "")
    GITLAB_PROJECT_ID = os.getenv("GITLAB_PROJECT_ID", "")

    APP_MODE = os.getenv("APP_MODE", "local")
    APP_PORT = int(os.getenv("APP_PORT", 5000))
    APP_HOST = os.getenv("APP_HOST", "127.0.0.1")

    DATABASE_PATH = os.path.join(os.path.dirname(__file__), "qa_bug_tracker.db")
    OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

    # Date de debut de collecte
    DATA_START_DATE = "2023-01-01"
    GITLAB_VERIFY_SSL = os.getenv("GITLAB_VERIFY_SSL", "true").lower() != "false"

    @classmethod
    def is_gitlab_configured(cls):
        return bool(cls.GITLAB_TOKEN) and cls.GITLAB_TOKEN != "your_private_token_here"

    @classmethod
    def is_server_mode(cls):
        return cls.APP_MODE == "server"
