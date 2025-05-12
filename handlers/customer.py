import logging
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import db
from config.config import logger
from utils.helpers import send_or_edit_message, format_car_info, format_booking_info
from utils.keyboards import KeyboardFactory
from messages import Messages

# Create a router for customer handlers
router = Router()

# States for customer interactions
class CustomerStates(StatesGroup):
    selecting_language = State()
    viewing_cars = State()
    booking_select_start_date = State()
    booking_select_start_time = State()
    booking_select_end_date = State()
    booking_select_end_time = State()
    confirming_booking = State()
    viewing_booking = State()
    confirming_return = State()

@router.message(Command('start'))
async def start_handler(message: Message, state: FSMContext):
    """Handle /start command - first entry point for users"""
    try:
        # Create initial messages and keyboard factory in English
        msgs = Messages('en')
        kb = KeyboardFactory(msgs)
        
        # Store in state
        await state.update_data(msgs=msgs, language='en')
        
        # Check if user is already in the database
        telegram_id = message.from_user.id
        customer_id = db.get_customer_id(telegram_id)
        
        if not customer_id:
            # New user, register them
            name = message.from_user.full_name
            success = db.register_customer(telegram_id, name)
            if not success:
                await message.answer("❌ Registration failed. Please try again later.")
                return
            
            welcome_text = msgs.get('welcome_new', name=name)
        else:
            # Existing user
            name = message.from_user.full_name
            welcome_text = msgs.get('welcome_back', name=name)
        
        # Ask user to select language
        await message.answer(welcome_text)
        await message.answer(msgs.get('select_language'), reply_markup=kb.language_keyboard())
        
        # Set state to language selection
        await state.set_state(CustomerStates.selecting_language)
        
    except Exception as e:
        logger.error(f"Error in start_handler: {e}")
        await message.answer("❌ An error occurred. Please try again later.")


@router.callback_query(lambda c: c.data.startswith("lang_"))
async def language_callback_handler(callback_query: CallbackQuery, state: FSMContext):
    """Handle language selection callback"""
    try:
        # Get language from callback data
        lang_code = callback_query.data.split('_')[1]
        
        # Update language
        msgs = Messages(lang_code)
        kb = KeyboardFactory(msgs)
        
        # Store language in state
        await state.update_data(language=lang_code, msgs=msgs)
        
        # Send confirmation and show main menu
        await callback_query.answer(msgs.get('language_changed'))
        
        # Show main menu
        await send_or_edit_message(
            callback_query, 
            msgs.get('main_menu'),
            reply_markup=kb.main_menu_keyboard()
        )
        
        # Clear state
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error in language_callback_handler: {e}")
        await callback_query.message.answer("❌ An error occurred. Please try again later.")


@router.callback_query(lambda c: c.data == "list_cars_command")
async def list_cars_command_handler(callback_query: CallbackQuery, state: FSMContext):
    """Handle listing available cars from main menu"""
    try:
        logger.info("list_cars_command handler called")
        # Get language configuration from state or create new
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        # Get available cars - we'll store them in state for pagination
        cars = db.get_available_cars(limit=100)  # Fetch more cars
        logger.info(f"Found {len(cars)} available cars")
        
        if not cars:
            await send_or_edit_message(
                callback_query,
                msgs.get('no_cars'),
                reply_markup=kb.main_menu_keyboard()
            )
            return
            
        # Store cars in state for pagination
        await state.update_data(cars=cars, current_page=0)
        
        # Show first page of cars
        await send_or_edit_message(
            callback_query,
            msgs.get('select_car'),
            reply_markup=kb.car_list_keyboard(cars, page=0)
        )
        
        # Set state to viewing cars
        await state.set_state(CustomerStates.viewing_cars)
        logger.info("State set to viewing_cars")
        
    except Exception as e:
        logger.error(f"Error in list_cars_command_handler: {e}", exc_info=True)
        state_data = await state.get_data()
        kb = KeyboardFactory(state_data.get('msgs', Messages('en')))
        await callback_query.message.answer(
            "❌ An error occurred while listing cars. Please try again later.",
            reply_markup=kb.main_menu_keyboard()
        )


@router.callback_query(lambda c: c.data == "list_cars")
async def back_to_car_list_handler(callback_query: CallbackQuery, state: FSMContext):
    """Handle going back to car list from car details"""
    try:
        # Get language configuration from state
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        # Get the cars from state that were previously loaded
        cars = state_data.get('cars', [])
        current_page = state_data.get('current_page', 0)
        
        if not cars:
            # If no cars in state, fetch them again
            cars = db.get_available_cars(limit=100)  # Fetch more cars
            current_page = 0
            await state.update_data(cars=cars, current_page=current_page)
            
            if not cars:
                await send_or_edit_message(
                    callback_query,
                    msgs.get('no_cars'),
                    reply_markup=kb.main_menu_keyboard()
                )
                return
        
        # Show cars for the current page
        await send_or_edit_message(
            callback_query,
            msgs.get('select_car'),
            reply_markup=kb.car_list_keyboard(cars, page=current_page)
        )
        
        # Set state to viewing cars
        await state.set_state(CustomerStates.viewing_cars)
        
    except Exception as e:
        logger.error(f"Error in back_to_car_list_handler: {e}")
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        await callback_query.message.answer(
            "❌ An error occurred. Going back to main menu.",
            reply_markup=kb.main_menu_keyboard()
        )


@router.callback_query(lambda c: c.data.startswith("car_page_"))
async def car_page_handler(callback_query: CallbackQuery, state: FSMContext):
    """Handle car listing pagination"""
    try:
        # Get language configuration from state
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        # Extract page number from callback data
        page = int(callback_query.data.replace("car_page_", ""))
        
        # Get cars from state
        cars = state_data.get('cars', [])
        
        if not cars:
            await send_or_edit_message(
                callback_query,
                msgs.get('no_cars'),
                reply_markup=kb.main_menu_keyboard()
            )
            return
            
        # Update current page in state
        await state.update_data(current_page=page)
        
        # Show cars for the selected page
        await send_or_edit_message(
            callback_query,
            msgs.get('select_car'),
            reply_markup=kb.car_list_keyboard(cars, page=page)
        )
        
    except Exception as e:
        logger.error(f"Error in car_page_handler: {e}")
        state_data = await state.get_data()
        kb = KeyboardFactory(state_data.get('msgs', Messages('en')))
        await callback_query.message.answer(
            "❌ An error occurred while changing pages. Please try again later.",
            reply_markup=kb.main_menu_keyboard()
        )


@router.callback_query(lambda c: c.data.startswith("car_") and not c.data.startswith("car_page_"))
async def car_details_handler(callback_query: CallbackQuery, state: FSMContext):
    """Handle car selection to show details"""
    try:
        logger.info(f"Car details handler called with data: {callback_query.data}")
        
        # Acknowledge the callback immediately
        await callback_query.answer("Loading car details...")
        
        # Get language configuration from state
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        # Extract car_id from callback data
        car_id = int(callback_query.data.split('_')[1])
        logger.info(f"Showing details for car ID: {car_id}")
        
        # Store the current car_id in state for potential booking
        await state.update_data(current_car_id=car_id)
        
        # Get car details
        car_details = db.get_car_details(car_id)
        
        if not car_details:
            logger.warning(f"Car not found: {car_id}")
            await send_or_edit_message(
                callback_query,
                msgs.get('car_not_found'),
                reply_markup=kb.main_menu_keyboard()
            )
            return
        
        car = car_details['car']
        images = car_details['images']
        
        # Format car details
        car_info = msgs.get('car_details', 
                           make=car[1], 
                           model=car[2], 
                           year=car[3], 
                           dealer=car[4])
        
        # Get primary image if available
        photo = None
        for img in images:
            if img[1]:  # is_primary
                photo = img[0]  # image_url
                break
        
        logger.info(f"Generating car details keyboard for car ID: {car_id}")
        
        # Build the car details keyboard
        details_keyboard = kb.car_details_keyboard(car_id)
        
        # Delete any previous message to ensure clean display
        try:
            if hasattr(callback_query.message, 'photo'):
                logger.info("Previous message has photo, deleting to avoid conflicts")
                await callback_query.message.delete()
                
                if photo:
                    logger.info("Sending new photo message")
                    await callback_query.message.answer_photo(
                        photo=photo,
                        caption=car_info,
                        reply_markup=details_keyboard
                    )
                else:
                    logger.info("Sending text message (no photo available)")
                    await callback_query.message.answer(
                        car_info,
                        reply_markup=details_keyboard
                    )
                return
        except Exception as e:
            logger.warning(f"Error during message cleanup: {e}")
        
        # Show car details with photo if available
        if photo:
            await send_or_edit_message(
                callback_query,
                car_info,
                reply_markup=details_keyboard,
                photo=photo,
                car_id=car_id  # Pass car_id for image error handling
            )
        else:
            await send_or_edit_message(
                callback_query,
                car_info,
                reply_markup=details_keyboard
            )
        
    except Exception as e:
        logger.error(f"Error in car_details_handler: {e}", exc_info=True)
        state_data = await state.get_data()
        kb = KeyboardFactory(state_data.get('msgs', Messages('en')))
        await callback_query.message.answer(
            "❌ An error occurred while getting car details. Please try again later.",
            reply_markup=kb.main_menu_keyboard()
        )


@router.callback_query(lambda c: c.data.startswith("book_"))
async def direct_book_car_handler(callback_query: CallbackQuery, state: FSMContext):
    """Direct handler for book car buttons - more reliable implementation"""
    try:
        # Log and acknowledge
        logger.info(f"DIRECT book car handler triggered with data: {callback_query.data}")
        await callback_query.answer("Processing booking request...")
        
        # Get car_id from callback data
        car_id = int(callback_query.data.split('_')[1])
        logger.info(f"DIRECT booking car ID: {car_id}")
        
        # Store in state
        await state.update_data(car_id=car_id)
        
        # First check if the car exists and is available
        car_details = db.get_car_details(car_id)
        if not car_details:
            logger.warning(f"DIRECT: Car {car_id} not found or not available")
            state_data = await state.get_data()
            msgs = state_data.get('msgs', Messages('en'))
            kb = KeyboardFactory(msgs)
            
            # Send error message
            await callback_query.message.reply(
                msgs.get('car_not_found'),
                reply_markup=kb.main_menu_keyboard()
            )
            return
            
        # Get language data
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        # Create date keyboard
        date_keyboard = kb.generate_date_keyboard(for_start=True)
        
        # Delete the current message (which has car details)
        logger.info("DIRECT: Deleting car details message")
        try:
            await callback_query.message.delete()
        except Exception as e:
            logger.warning(f"DIRECT: Could not delete message: {e}")
            
        # Send a completely new message with date selection
        logger.info("DIRECT: Sending new date selection message")
        new_msg = await callback_query.message.answer(
            "Please select the rental start date:",
            reply_markup=date_keyboard
        )
        
        logger.info(f"DIRECT: New message sent with ID: {new_msg.message_id}")
        
        # Set state
        await state.set_state(CustomerStates.booking_select_start_date)
        logger.info("DIRECT: State set to booking_select_start_date")
        
    except Exception as e:
        logger.error(f"DIRECT ERROR in direct_book_car_handler: {e}", exc_info=True)
        try:
            # Always try to send a new message in case of error
            await callback_query.message.reply(
                "❌ An error occurred. Please try again.",
                reply_markup=KeyboardFactory(Messages('en')).main_menu_keyboard()
            )
        except Exception as final_e:
            logger.error(f"Failed to send error message: {final_e}")
            # Last resort
            await callback_query.answer("Error occurred. Please restart with /start")


@router.callback_query(lambda c: c.data == "my_booking")
async def my_booking_handler(callback_query: CallbackQuery, state: FSMContext):
    """Handle viewing user's active booking"""
    try:
        # Get language configuration from state
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        # Get customer ID
        telegram_id = callback_query.from_user.id
        customer_id = db.get_customer_id(telegram_id)
        
        if not customer_id:
            await send_or_edit_message(
                callback_query,
                msgs.get('customer_not_found'),
                reply_markup=kb.main_menu_keyboard()
            )
            return
        
        # Get active booking
        booking = db.get_active_booking(customer_id)
        
        if not booking:
            await send_or_edit_message(
                callback_query,
                msgs.get('no_active_booking'),
                reply_markup=kb.main_menu_keyboard()
            )
            return
        
        # Format booking info
        booking_info = format_booking_info(booking)
        message = msgs.get('active_booking', booking_info=booking_info)
        
        # Show booking details
        await send_or_edit_message(
            callback_query,
            message,
            reply_markup=kb.booking_details_keyboard(booking[0])  # booking[0] is booking_id
        )
        
        # Set state to viewing booking
        await state.set_state(CustomerStates.viewing_booking)
        
    except Exception as e:
        logger.error(f"Error in my_booking_handler: {e}")
        state_data = await state.get_data()
        kb = KeyboardFactory(state_data.get('msgs', Messages('en')))
        await callback_query.message.answer(
            "❌ An error occurred while retrieving your booking. Please try again later.",
            reply_markup=kb.main_menu_keyboard()
        )


@router.callback_query(lambda c: c.data.startswith("return_"))
async def return_car_handler(callback_query: CallbackQuery, state: FSMContext):
    """Handle car return"""
    try:
        # Get language configuration from state
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        # Extract booking_id from callback data
        booking_id = int(callback_query.data.split('_')[1])
        
        # Return the car
        success, message = db.return_car(booking_id)
        
        if success:
            await callback_query.answer(msgs.get('return_success'))
            await send_or_edit_message(
                callback_query,
                msgs.get('return_success'),
                reply_markup=kb.main_menu_keyboard()
            )
        else:
            await send_or_edit_message(
                callback_query,
                msgs.get('return_failed', reason=message),
                reply_markup=kb.main_menu_keyboard()
            )
        
        # Clear state
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error in return_car_handler: {e}")
        state_data = await state.get_data()
        kb = KeyboardFactory(state_data.get('msgs', Messages('en')))
        await callback_query.message.answer(
            "❌ An error occurred while returning the car. Please try again later.",
            reply_markup=kb.main_menu_keyboard()
        )


@router.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu_handler(callback_query: CallbackQuery, state: FSMContext):
    """Handle going back to main menu"""
    try:
        # Get language configuration from state
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        # Show main menu
        await send_or_edit_message(
            callback_query,
            msgs.get('main_menu'),
            reply_markup=kb.main_menu_keyboard()
        )
        
        # Clear state
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error in back_to_menu_handler: {e}")
        await callback_query.message.answer(
            "❌ An error occurred. Please try again later.",
            reply_markup=kb.main_menu_keyboard()
        )


@router.message(Command('cancel'))
async def cancel_handler(message: Message, state: FSMContext):
    """Handle /cancel command - reset user state"""
    try:
        # Get current state
        current_state = await state.get_state()
        
        if current_state is None:
            # No active state, nothing to cancel
            await message.answer("Nothing to cancel. Send /start to begin using the bot.")
            return
        
        # Clear state
        await state.clear()
        
        # Confirm cancellation
        await message.answer("✅ Operation cancelled. Send /start to begin again.")
        
    except Exception as e:
        logger.error(f"Error in cancel_handler: {e}")
        await message.answer("❌ An error occurred while cancelling. Please try again later.")


@router.callback_query(lambda c: c.data.startswith("start_date_"))
async def start_date_handler(callback_query: CallbackQuery, state: FSMContext):
    """Handle booking start date selection"""
    try:
        # Get language configuration from state
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        # Extract date from callback data
        date_str = callback_query.data.replace("start_date_", "")
        
        # Store date in state
        await state.update_data(start_date=date_str)
        
        # Notify user selection was received
        await callback_query.answer(f"Selected start date: {date_str}")
        
        # Ask for starting time
        await send_or_edit_message(
            callback_query,
            f"Please select the rental start time for {date_str}:",
            reply_markup=kb.generate_time_keyboard(for_start=True)
        )
        
        # Set state to booking start time selection
        await state.set_state(CustomerStates.booking_select_start_time)
        
    except Exception as e:
        logger.error(f"Error in start_date_handler: {e}", exc_info=True)
        state_data = await state.get_data()
        kb = KeyboardFactory(state_data.get('msgs', Messages('en')))
        await callback_query.message.answer(
            "❌ An error occurred while selecting the date. Please try again later.",
            reply_markup=kb.main_menu_keyboard()
        )


@router.callback_query(lambda c: c.data.startswith("start_time_"))
async def start_time_handler(callback_query: CallbackQuery, state: FSMContext):
    """Handle booking start time selection"""
    try:
        # Get language configuration from state
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        # Extract time from callback data
        time_str = callback_query.data.replace("start_time_", "")
        
        # Get state data
        start_date = state_data.get('start_date')
        
        # Store complete start datetime
        await state.update_data(start_time=time_str, start_datetime=f"{start_date} {time_str}")
        
        # Ask for end date
        await send_or_edit_message(
            callback_query,
            f"Please select the rental end date:",
            reply_markup=kb.generate_date_keyboard(for_start=False)
        )
        
        # Set state to booking end date selection
        await state.set_state(CustomerStates.booking_select_end_date)
        
    except Exception as e:
        logger.error(f"Error in start_time_handler: {e}")
        state_data = await state.get_data()
        kb = KeyboardFactory(state_data.get('msgs', Messages('en')))
        await callback_query.message.answer(
            "❌ An error occurred while selecting the time. Please try again later.",
            reply_markup=kb.main_menu_keyboard()
        )


@router.callback_query(lambda c: c.data.startswith("end_date_"))
async def end_date_handler(callback_query: CallbackQuery, state: FSMContext):
    """Handle booking end date selection"""
    try:
        # Get language configuration from state
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        # Extract date from callback data
        date_str = callback_query.data.replace("end_date_", "")
        
        # Store date in state
        await state.update_data(end_date=date_str)
        
        # Ask for end time
        await send_or_edit_message(
            callback_query,
            f"Please select the rental end time for {date_str}:",
            reply_markup=kb.generate_time_keyboard(for_start=False)
        )
        
        # Set state to booking end time selection
        await state.set_state(CustomerStates.booking_select_end_time)
        
    except Exception as e:
        logger.error(f"Error in end_date_handler: {e}")
        state_data = await state.get_data()
        kb = KeyboardFactory(state_data.get('msgs', Messages('en')))
        await callback_query.message.answer(
            "❌ An error occurred while selecting the date. Please try again later.",
            reply_markup=kb.main_menu_keyboard()
        )


@router.callback_query(lambda c: c.data.startswith("end_time_"))
async def end_time_handler(callback_query: CallbackQuery, state: FSMContext):
    """Handle booking end time selection"""
    try:
        # Get language configuration from state
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        # Extract time from callback data
        time_str = callback_query.data.replace("end_time_", "")
        
        # Get state data
        end_date = state_data.get('end_date')
        start_datetime = state_data.get('start_datetime')
        car_id = state_data.get('car_id')
        
        # Store complete end datetime
        end_datetime = f"{end_date} {time_str}"
        await state.update_data(end_time=time_str, end_datetime=end_datetime)
        
        # Get car details for confirmation
        car_details = db.get_car_details(car_id)
        if not car_details:
            await send_or_edit_message(
                callback_query,
                msgs.get('car_not_found'),
                reply_markup=kb.main_menu_keyboard()
            )
            return
            
        car = car_details['car']
        
        # Create confirmation message
        confirmation_message = f"""
📋 Please confirm your booking:

🚗 {car[1]} {car[2]} ({car[3]})
📅 From: {start_datetime}
📅 To: {end_datetime}

Do you want to proceed with this booking?
"""
        
        # Show confirmation
        confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Confirm Booking", callback_data=f"confirm_booking_{car_id}")],
            [InlineKeyboardButton(text="❌ Cancel", callback_data="back_to_menu")]
        ])
        
        await send_or_edit_message(
            callback_query,
            confirmation_message,
            reply_markup=confirm_keyboard
        )
        
        # Set state to confirming booking
        await state.set_state(CustomerStates.confirming_booking)
        
    except Exception as e:
        logger.error(f"Error in end_time_handler: {e}")
        state_data = await state.get_data()
        kb = KeyboardFactory(state_data.get('msgs', Messages('en')))
        await callback_query.message.answer(
            "❌ An error occurred while selecting the time. Please try again later.",
            reply_markup=kb.main_menu_keyboard()
        )


@router.callback_query(lambda c: c.data.startswith("confirm_booking_"))
async def confirm_booking_handler(callback_query: CallbackQuery, state: FSMContext):
    """Handle booking confirmation"""
    try:
        # Get language configuration from state
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        # Extract car_id from callback data
        car_id = int(callback_query.data.replace("confirm_booking_", ""))
        
        # Get customer ID
        telegram_id = callback_query.from_user.id
        customer_id = db.get_customer_id(telegram_id)
        
        if not customer_id:
            await send_or_edit_message(
                callback_query,
                msgs.get('customer_not_found'),
                reply_markup=kb.main_menu_keyboard()
            )
            return
        
        # Book the car
        success, result = db.book_car(customer_id, car_id)
        
        if success:
            # Store booking data
            start_datetime = state_data.get('start_datetime')
            end_datetime = state_data.get('end_datetime')
            
            # Here you would update the booking with start and end times
            # This is a placeholder for the actual booking update
            
            await callback_query.answer(msgs.get('booking_success'))
            await send_or_edit_message(
                callback_query,
                msgs.get('booking_success'),
                reply_markup=kb.main_menu_keyboard()
            )
        else:
            await send_or_edit_message(
                callback_query,
                msgs.get('booking_failed', reason=result),
                reply_markup=kb.main_menu_keyboard()
            )
        
        # Clear state
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error in confirm_booking_handler: {e}")
        state_data = await state.get_data()
        kb = KeyboardFactory(state_data.get('msgs', Messages('en')))
        await callback_query.message.answer(
            "❌ An error occurred while confirming the booking. Please try again later.",
            reply_markup=kb.main_menu_keyboard()
        )


@router.callback_query(lambda c: c.data == "change_language")
async def change_language_handler(callback_query: CallbackQuery, state: FSMContext):
    """Handle language change request"""
    try:
        # Get language configuration from state
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        # Show language selection keyboard
        await send_or_edit_message(
            callback_query,
            msgs.get('select_language'),
            reply_markup=kb.language_keyboard(show_back_button=True)
        )
        
        # Set state to selecting language
        await state.set_state(CustomerStates.selecting_language)
        
    except Exception as e:
        logger.error(f"Error in change_language_handler: {e}")
        state_data = await state.get_data()
        kb = KeyboardFactory(state_data.get('msgs', Messages('en')))
        await callback_query.message.answer(
            "❌ An error occurred. Please try again later.",
            reply_markup=kb.main_menu_keyboard()
        )


@router.callback_query(lambda c: c.data == "contact_admin")
async def contact_admin_handler(callback_query: CallbackQuery, state: FSMContext):
    """Handle contact admin request"""
    try:
        # Get language configuration from state
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        # Show contact admin message
        await send_or_edit_message(
            callback_query,
            msgs.get('contact_admin_msg'),
            reply_markup=kb.main_menu_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Error in contact_admin_handler: {e}")
        state_data = await state.get_data()
        kb = KeyboardFactory(state_data.get('msgs', Messages('en')))
        await callback_query.message.answer(
            "❌ An error occurred. Please try again later.",
            reply_markup=kb.main_menu_keyboard()
        )


@router.callback_query(lambda c: c.data == "start_date_back")
async def start_date_back_handler(callback_query: CallbackQuery, state: FSMContext):
    """Handle going back from time selection to date selection"""
    try:
        # Get language configuration from state
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        # Get car_id from state
        car_id = state_data.get('car_id')
        
        if not car_id:
            # If car_id is missing, go back to list
            await back_to_car_list_handler(callback_query, state)
            return
        
        # Get car details again
        car_details = db.get_car_details(car_id)
        if not car_details:
            await callback_query.answer("❌ Car no longer available")
            await back_to_car_list_handler(callback_query, state)
            return
        
        # Show date selection again
        await send_or_edit_message(
            callback_query,
            "Please select the rental start date:",
            reply_markup=kb.generate_date_keyboard(for_start=True)
        )
        
        # Set state back to start date selection
        await state.set_state(CustomerStates.booking_select_start_date)
        
    except Exception as e:
        logger.error(f"Error in start_date_back_handler: {e}", exc_info=True)
        state_data = await state.get_data()
        kb = KeyboardFactory(state_data.get('msgs', Messages('en')))
        await callback_query.message.answer(
            "❌ An error occurred. Going back to main menu.",
            reply_markup=kb.main_menu_keyboard()
        )


@router.callback_query(lambda c: c.data == "end_date_back")
async def end_date_back_handler(callback_query: CallbackQuery, state: FSMContext):
    """Handle going back from end time selection to end date selection"""
    try:
        # Get language configuration from state
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        # Show end date selection again
        await send_or_edit_message(
            callback_query,
            "Please select the rental end date:",
            reply_markup=kb.generate_date_keyboard(for_start=False)
        )
        
        # Set state back to end date selection
        await state.set_state(CustomerStates.booking_select_end_date)
        
    except Exception as e:
        logger.error(f"Error in end_date_back_handler: {e}", exc_info=True)
        state_data = await state.get_data()
        kb = KeyboardFactory(state_data.get('msgs', Messages('en')))
        await callback_query.message.answer(
            "❌ An error occurred. Going back to main menu.",
            reply_markup=kb.main_menu_keyboard()
        ) 