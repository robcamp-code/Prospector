"""Configuration settings loaded from environment."""

import logging
import os

from dotenv import load_dotenv
from openai import RateLimitError
from tenacity import (
    retry,
    wait_exponential,
    stop_after_attempt,
    before_sleep_log,
    retry_if_exception_type,
)

load_dotenv()

# Default settings
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-5")
DEFAULT_LOCATION = os.getenv("DEFAULT_LOCATION", "Atlanta, GA")

# API keys (auto-detected by clients, but available if needed)
APIFY_API_KEY = os.getenv("APIFY_API_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

# Retry logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING)


def invoke_with_retry(agent, inputs, config):
    """Invoke an agent with retry logic for rate limits."""

    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=10),
        stop=stop_after_attempt(7),
        retry=retry_if_exception_type(RateLimitError),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _invoke():
        return agent.invoke(inputs, config=config)

    return _invoke()
