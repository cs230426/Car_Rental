import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TELEGRAM_BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN not found in environment variables!")
    raise ValueError("TELEGRAM_BOT_TOKEN is required to run the bot")

# Admin configuration
ADMIN_GROUP_ID = os.getenv('ADMIN_GROUP_ID')
try:
    if ADMIN_GROUP_ID:
        ADMIN_GROUP_ID = int(ADMIN_GROUP_ID)
    else:
        logger.warning("ADMIN_GROUP_ID not found in environment variables!")
except ValueError:
    logger.error("ADMIN_GROUP_ID must be an integer!")
    raise ValueError("ADMIN_GROUP_ID must be an integer")

# Database Configuration
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'car_rental')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD')

if not DB_PASSWORD:
    logger.error("DB_PASSWORD not found in environment variables!")
    raise ValueError("DB_PASSWORD is required to connect to the database")

# Other Configuration
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds
CONNECT_TIMEOUT = 5  # seconds 