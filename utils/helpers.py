import logging
import aiohttp
import asyncio
from aiogram.types import Message, CallbackQuery, URLInputFile, BufferedInputFile
from aiogram.exceptions import TelegramAPIError

logger = logging.getLogger(__name__)
# Import admin group ID at module level to avoid circular imports
from config.config import ADMIN_GROUP_ID

# Import db when needed to avoid circular imports
import db

async def download_image(url, timeout=10):
    """Download image from URL with timeout
    
    Args:
        url: Image URL
        timeout: Timeout in seconds
        
    Returns:
        Image bytes or None if failed
    """
    try:
        # Use shorter timeout to avoid long waits
        timeout_obj = aiohttp.ClientTimeout(total=timeout)
        
        async with aiohttp.ClientSession(timeout=timeout_obj) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    logger.warning(f"Failed to download image, status code: {response.status}")
                    return None
    except asyncio.TimeoutError:
        logger.warning(f"Timeout while downloading image from {url}")
        return None
    except Exception as e:
        logger.warning(f"Error downloading image from {url}: {e}")
        return None

async def send_or_edit_message(message, text: str, reply_markup=None, photo=None, car_id=None):
    """Helper function to handle message sending/editing with error handling
    
    Args:
        message: Message or CallbackQuery object
        text: Text to send
        reply_markup: Keyboard markup to attach
        photo: Photo to send (if any) - can be a Telegram file_id or a URL
        car_id: ID of the car (for auto-refreshing image file IDs)
        
    Returns:
        The sent or edited message object
    """
    try:
        logger.info(f"send_or_edit_message called with photo={bool(photo)}, reply_markup={bool(reply_markup)}")
        
        # Handle CallbackQuery vs Message object
        is_callback = isinstance(message, CallbackQuery)
        msg_obj = message.message if is_callback else message
        
        # Check if current message has photo (if we're editing a message with photo)
        has_photo = hasattr(msg_obj, 'photo') and bool(msg_obj.photo)
        logger.info(f"Current message has photo: {has_photo}")
        
        # Special case: switching from photo to text or text to photo
        # In this case, we need to delete the old message and send a new one
        if (has_photo and not photo) or (not has_photo and photo):
            logger.info("Message type changing (photo <-> text), deleting old message")
            try:
                await msg_obj.delete()
            except Exception as e:
                logger.warning(f"Could not delete old message: {e}")
            
            # Send as a new message
            if photo:
                # Handle photo case
                if isinstance(photo, str) and photo.startswith('http'):
                    photo_file = URLInputFile(photo)
                else:
                    photo_file = photo
                
                logger.info("Sending new photo message")
                return await msg_obj.answer_photo(photo=photo_file, caption=text, reply_markup=reply_markup)
            else:
                # Handle text case
                logger.info("Sending new text message")
                return await msg_obj.answer(text, reply_markup=reply_markup)
        
        # Normal flow continues
        if photo:
            try:
                # Check if the photo is a URL (starts with http)
                if isinstance(photo, str) and photo.startswith('http'):
                    # Create a URLInputFile for the photo URL
                    photo_file = URLInputFile(photo)
                else:
                    # Use as is (assuming it's a valid Telegram file_id)
                    photo_file = photo
                
                # For messages with photos, always send new message if not already
                # a callback (because we can't edit a text message to be a photo)
                if not is_callback:
                    logger.info("Direct photo message")
                    return await msg_obj.answer_photo(photo=photo_file, caption=text, reply_markup=reply_markup)
                else:
                    # For callback queries with photo messages
                    if has_photo:
                        # If current message already has photo, we should send a new one
                        # because we can't edit photo messages
                        try:
                            logger.info("Replacing photo message")
                            await msg_obj.delete()
                        except Exception as e:
                            logger.warning(f"Could not delete old photo message: {e}")
                    
                    logger.info("Sending new photo message from callback")
                    return await msg_obj.answer_photo(photo=photo_file, caption=text, reply_markup=reply_markup)
            except TelegramAPIError as e:
                error_str = str(e).lower()
                
                # Handle Telegram file ID errors specifically
                if "wrong remote file identifier" in error_str and car_id is not None:
                    logger.warning(f"Invalid file ID detected for car #{car_id}. Error: {e}")
                    logger.info(f"Invalid file ID value: {photo}")
                
                # Fall back to text message
                logger.warning(f"Failed to send photo, falling back to text: {e}")
                return await msg_obj.answer(f"{text}\n\n⚠️ Image could not be displayed.", reply_markup=reply_markup)
        else:
            # For text messages, try to edit if possible
            try:
                if is_callback and not has_photo:
                    logger.info("Editing existing text message")
                    return await msg_obj.edit_text(text, reply_markup=reply_markup)
                else:
                    # Otherwise, send new message
                    logger.info("Sending new text message")
                    return await msg_obj.answer(text, reply_markup=reply_markup)
            except TelegramAPIError as e:
                error_str = str(e).lower()
                if "message is not modified" in error_str:
                    # Message is the same, ignore this error
                    logger.info("Message not modified, ignoring")
                    return msg_obj
                elif "there is no text in the message to edit" in error_str:
                    # Message was probably deleted or is media, send new one
                    logger.info("Cannot edit, sending new message")
                    return await msg_obj.answer(text, reply_markup=reply_markup)
                else:
                    logger.error(f"Telegram API error: {e}")
                    # Try one more time with a direct answer
                    return await msg_obj.answer(text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error in send_or_edit_message: {e}", exc_info=True)
        # Try to send a fallback message
        try:
            if isinstance(message, CallbackQuery):
                return await message.message.answer(f"❌ Error in message handling. Please try again.", reply_markup=reply_markup)
            else:
                return await message.answer(f"❌ Error in message handling. Please try again.", reply_markup=reply_markup)
        except Exception as final_error:
            logger.critical(f"Failed to send fallback error message: {final_error}")
            return None

def is_admin_group(message):
    """Check if the message is from the admin group
    
    Args:
        message: Message object
        
    Returns:
        bool: True if message is from admin group
    """
    try:
        chat_id = message.chat.id
        logger.info(f"Checking admin group: message chat_id={chat_id}, ADMIN_GROUP_ID={ADMIN_GROUP_ID}")
        return chat_id == ADMIN_GROUP_ID
    except Exception as e:
        logger.error(f"Error in is_admin_group check: {e}")
        return False

def format_car_info(car):
    """Format car information for display
    
    Args:
        car: Car tuple from database
        
    Returns:
        str: Formatted car information
    """
    return f"🚗 {car[1]} {car[2]} ({car[3]})\n👤 Dealer: {car[4]}"

def format_booking_info(booking):
    """Format booking information for display
    
    Args:
        booking: Booking tuple from database
        
    Returns:
        str: Formatted booking information
    """
    if not booking:
        return "No active booking found."
    
    start_date = booking[2].strftime("%Y-%m-%d %H:%M")
    end_date = booking[3].strftime("%Y-%m-%d %H:%M") if booking[3] else "Active"
    return f"🚗 {booking[4]} {booking[5]} ({booking[6]})\n📅 From: {start_date}\n📅 To: {end_date}" 