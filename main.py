import os
import asyncio
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramAPIError
from dotenv import load_dotenv

# Import utilities and configuration
from utils.logger import setup_logger, log_critical_error
from handlers.customer import router as customer_router
from handlers.admin import router as admin_router
from handlers.dealer import router as dealer_router

# Load environment variables
load_dotenv()

# Set up enhanced logging
logger = setup_logger()

# Get bot token from environment
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TELEGRAM_BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN not found in environment variables!")
    raise ValueError("TELEGRAM_BOT_TOKEN is required to run the bot")

# Development mode flag - set to True to skip database connection check
DEVELOPMENT_MODE = False

# Error handling middleware
class ErrorHandlingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        try:
            return await handler(event, data)
        except TelegramAPIError as telegram_error:
            # Handle Telegram API errors
            error_msg = f"Telegram API Error: {telegram_error}"
            logger.error(error_msg)
            
            # Log critical errors
            log_critical_error("Telegram API Error", telegram_error)
            
            # Try to notify user
            try:
                if hasattr(event, 'answer'):
                    await event.answer("❌ A Telegram error occurred. Please try again later.")
                elif hasattr(event, 'message'):
                    await event.message.answer("❌ A Telegram error occurred. Please try again later.")
            except Exception as notify_error:
                logger.error(f"Failed to notify user about error: {notify_error}")
                
            # Clear user state
            state = data.get('state')
            if state:
                await state.clear()
                
        except Exception as e:
            # Handle other unexpected errors
            error_msg = f"Unexpected error in {handler.__name__}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            # Log critical errors
            log_critical_error("Unexpected Error", e)
            
            try:
                if hasattr(event, 'answer'):
                    await event.answer("❌ An unexpected error occurred. Please try /cancel to reset and start over.")
                elif hasattr(event, 'message'):
                    await event.message.answer("❌ An unexpected error occurred. Please try /cancel to reset and start over.")
            except Exception as notify_error:
                logger.error(f"Failed to notify user about error: {notify_error}")
            
            # Clear user state
            state = data.get('state')
            if state:
                await state.clear()

async def main():
    """Main function to start the bot"""
    # Initialize bot and dispatcher
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Register middleware
    dp.message.middleware(ErrorHandlingMiddleware())
    dp.callback_query.middleware(ErrorHandlingMiddleware())
    
    # Register routers
    dp.include_router(customer_router)
    dp.include_router(admin_router)
    dp.include_router(dealer_router)
    
    # Start polling
    logger.info("Starting the Car Rental Bot...")
    
    try:
        # Notify about successful startup
        logger.info("Bot startup successful!")
        
        # Start polling
        await dp.start_polling(bot)
    except Exception as e:
        logger.critical(f"Error during bot polling: {e}", exc_info=True)
        log_critical_error("Error during bot polling", e)

if __name__ == "__main__":
    try:
        # Check database connection at startup
        if not DEVELOPMENT_MODE:
            import db
            try:
                with db.get_connection() as conn:
                    logger.info("Database connection test successful")
            except Exception as db_error:
                logger.critical(f"Database connection test failed: {db_error}", exc_info=True)
                log_critical_error("Database connection test failed", db_error)
                raise
        else:
            logger.warning("Running in DEVELOPMENT MODE - database connection check skipped")
        
        # Run the bot
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped!")
    except Exception as e:
        log_critical_error("Critical error during bot startup", e)
        logger.critical(f"Critical error during bot startup: {e}", exc_info=True) 