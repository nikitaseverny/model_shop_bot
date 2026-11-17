"""Main entry point for the 3D Model Shop Bot."""

from __future__ import annotations

import logging
import sys

from config import Config
from handlers import create_application

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


def main() -> None:
    """Run the bot."""
    config = Config.from_env()
    logger.info("Starting 3D Model Shop Bot...")
    logger.info("Timezone: %s", config.timezone)
    logger.info("Data file: %s", config.data_file)
    logger.info("Admin chat IDs: %s", config.admin_chat_ids)

    application = create_application(config)

    # Run polling
    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()