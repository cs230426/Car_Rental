import logging
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime

import db
from config.config import ADMIN_GROUP_ID, logger
from utils.helpers import send_or_edit_message, is_admin_group
from utils.keyboards import KeyboardFactory
from messages import Messages

# Create a router for dealer handlers
router = Router()

# States for dealer interactions
class DealerStates(StatesGroup):
    adding_car = State()
    adding_car_model = State()
    adding_car_year = State()
    adding_car_photo = State()
    viewing_cars = State()
    confirming_delete_car = State()
    viewing_stats = State()
    refreshing_car_photo = State()

def is_dealer(user_id: int) -> bool:
    """Check if user is a registered dealer"""
    try:
        return db.is_dealer(user_id)
    except Exception as e:
        logger.error(f"Error checking dealer status: {e}")
        return False

# Dealer command - only works for registered dealers in admin group
@router.message(Command("dealer"))
async def dealer_command_handler(message: Message, state: FSMContext):
    """Handle /dealer command in admin group for dealers"""
    if not is_admin_group(message):
        await message.answer("❌ This command is only available in the admin group.")
        return
        
    try:
        user_id = message.from_user.id
        
        # Check if user is a dealer
        if not is_dealer(user_id):
            await message.answer("❌ You are not registered as a dealer. Please contact the administrator.")
            return
        
        # Set language to English for dealer panel
        msgs = Messages('en')
        kb = KeyboardFactory(msgs)
        
        # Store in state for use in other handlers
        await state.update_data(language='en', msgs=msgs)
        
        # Show dealer menu
        await message.answer(
            "🚗 Dealer Panel",
            reply_markup=kb.dealer_menu_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Error in dealer_command_handler: {e}")
        await message.answer("❌ An error occurred. Please try again later.")

# Dealer callbacks
@router.callback_query(lambda c: c.data.startswith("dealer_"))
async def dealer_callback_handler(callback_query: CallbackQuery, state: FSMContext):
    """Handle dealer menu callbacks"""
    if not is_admin_group(callback_query.message):
        await callback_query.answer("❌ This action is only available in the admin group.")
        return
        
    try:
        user_id = callback_query.from_user.id
        
        # Check if user is a dealer
        if not is_dealer(user_id):
            await callback_query.answer("❌ You are not registered as a dealer.")
            return
        
        # Get language configuration from state or create new
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
            
        action = callback_query.data.replace("dealer_", "")
        
        if action == "add_car":
            await start_add_car(callback_query, state, kb)
        elif action == "my_cars":
            await show_dealer_cars(callback_query, state, kb)
        elif action == "stats":
            await show_dealer_stats(callback_query, state, kb)
        elif action == "back":
            await back_to_dealer_menu(callback_query, state, kb)
        else:
            await callback_query.answer("Unknown action")
            
    except Exception as e:
        logger.error(f"Error in dealer_callback_handler: {e}")
        await callback_query.message.answer("❌ An error occurred. Please try again later.")

@router.callback_query(lambda c: c.data == "dealer_back")
async def dealer_back_handler(callback_query: CallbackQuery, state: FSMContext):
    """Handle dealer back button"""
    try:
        # Get language configuration from state
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        # Call back_to_dealer_menu function
        await back_to_dealer_menu(callback_query, state, kb)
        
    except Exception as e:
        logger.error(f"Error in dealer_back_handler: {e}")
        await callback_query.message.answer(
            "❌ An error occurred. Please try again later.",
            reply_markup=KeyboardFactory(Messages('en')).dealer_menu_keyboard()
        )

@router.callback_query(lambda c: c.data == "dealer_my_cars")
async def dealer_my_cars_handler(callback_query: CallbackQuery, state: FSMContext):
    """Handle dealer my cars button"""
    try:
        # Get language configuration from state
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        # Call show_dealer_cars function
        await show_dealer_cars(callback_query, state, kb)
        
    except Exception as e:
        logger.error(f"Error in dealer_my_cars_handler: {e}")
        await callback_query.message.answer(
            "❌ An error occurred. Please try again later.",
            reply_markup=KeyboardFactory(Messages('en')).dealer_menu_keyboard()
        )

async def start_add_car(callback_query: CallbackQuery, state: FSMContext, kb):
    """Start the process of adding a car"""
    try:
        # Ask for car make
        await send_or_edit_message(
            callback_query,
            "Please enter the car make (e.g., Toyota, Honda):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Cancel", callback_data="dealer_back")]
            ])
        )
        
        # Set state to adding car make
        await state.set_state(DealerStates.adding_car)
        
    except Exception as e:
        logger.error(f"Error in start_add_car: {e}")
        await callback_query.message.answer(
            "❌ An error occurred while preparing to add a car.",
            reply_markup=kb.dealer_menu_keyboard()
        )

@router.message(DealerStates.adding_car)
async def dealer_add_car_make_handler(message: Message, state: FSMContext):
    """Handle dealer adding car make"""
    if not is_admin_group(message):
        await message.answer("❌ This action is only available in the admin group.")
        return
        
    if not is_dealer(message.from_user.id):
        await message.answer("❌ You are not registered as a dealer.")
        return
        
    try:
        # Get state data
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        make = message.text.strip()
        
        # Input validation for make
        if not make or len(make) < 1 or len(make) > 50:
            await message.answer("❌ Invalid car make. Please enter a make between 1 and 50 characters.")
            return
            
        # Validate that the make contains only letters and spaces
        if not all(c.isalpha() or c.isspace() for c in make):
            await message.answer("❌ Car make should contain only letters and spaces.")
            return
        
        await state.update_data(car_make=make)
        
        # Ask for car model
        await state.set_state(DealerStates.adding_car_model)
        await message.answer(f"Great! Now please enter the model of the {make}:")
        
    except Exception as e:
        logger.error(f"Error in dealer_add_car_make_handler: {e}")
        state_data = await state.get_data()
        kb = KeyboardFactory(state_data.get('msgs', Messages('en')))
        await message.answer(
            "❌ An error occurred while processing the car make.",
            reply_markup=kb.dealer_menu_keyboard()
        )

@router.message(DealerStates.adding_car_model)
async def dealer_add_car_model_handler(message: Message, state: FSMContext):
    """Handle dealer adding car model"""
    if not is_admin_group(message):
        await message.answer("❌ This action is only available in the admin group.")
        return
        
    if not is_dealer(message.from_user.id):
        await message.answer("❌ You are not registered as a dealer.")
        return
        
    try:
        # Get state data
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        model = message.text.strip()
        
        # Input validation for model
        if not model or len(model) < 1 or len(model) > 50:
            await message.answer("❌ Invalid model name. Please enter a model name between 1 and 50 characters.")
            return
        
        # Get data from state
        data = await state.get_data()
        make = data.get('car_make')
        
        await state.update_data(car_model=model)
        
        # Ask for car year
        await state.set_state(DealerStates.adding_car_year)
        await message.answer(f"Great! Now please enter the year of the {make} {model} (e.g., 2022):")
        
    except Exception as e:
        logger.error(f"Error in dealer_add_car_model_handler: {e}")
        state_data = await state.get_data()
        kb = KeyboardFactory(state_data.get('msgs', Messages('en')))
        await message.answer(
            "❌ An error occurred while processing the car model.",
            reply_markup=kb.dealer_menu_keyboard()
        )

@router.message(DealerStates.adding_car_year)
async def dealer_add_car_year_handler(message: Message, state: FSMContext):
    """Handle dealer adding car year"""
    if not is_admin_group(message):
        await message.answer("❌ This action is only available in the admin group.")
        return
        
    if not is_dealer(message.from_user.id):
        await message.answer("❌ You are not registered as a dealer.")
        return
        
    try:
        # Get state data
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        year_text = message.text.strip()
        
        # Input validation for year
        try:
            year = int(year_text)
            current_year = datetime.now().year
            
            # Check if year is reasonable (between 1900 and current year + 1)
            if year < 1900 or year > current_year + 1:
                await message.answer(f"❌ Invalid year. Please enter a year between 1900 and {current_year + 1}.")
                return
                
        except ValueError:
            await message.answer("❌ Please enter a valid year (numbers only).")
            return
        
        # Get data from state
        data = await state.get_data()
        make = data.get('car_make')
        model = data.get('car_model')
        
        await state.update_data(car_year=year)
        
        # Ask for car photo
        await state.set_state(DealerStates.adding_car_photo)
        await message.answer(f"Great! Now please send a photo of the {make} {model} ({year}).")
        
    except Exception as e:
        logger.error(f"Error in dealer_add_car_year_handler: {e}")
        state_data = await state.get_data()
        kb = KeyboardFactory(state_data.get('msgs', Messages('en')))
        await message.answer(
            "❌ An error occurred while processing the car year.",
            reply_markup=kb.dealer_menu_keyboard()
        )

@router.message(DealerStates.adding_car_photo, F.photo)
async def dealer_add_car_photo_handler(message: Message, state: FSMContext):
    """Handle dealer adding car photo"""
    if not is_admin_group(message):
        await message.answer("❌ This action is only available in the admin group.")
        return
        
    if not is_dealer(message.from_user.id):
        await message.answer("❌ You are not registered as a dealer.")
        return
        
    try:
        # Get state data
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        # Get photo file ID (largest size)
        photo_id = message.photo[-1].file_id
        
        # Get data from state
        data = await state.get_data()
        make = data.get('car_make')
        model = data.get('car_model')
        year = data.get('car_year')
        
        # Get dealer ID from user ID
        dealer_id = db.get_dealer_id(message.from_user.id)
        
        if not dealer_id:
            await message.answer("❌ You are not registered as a dealer.")
            await state.clear()
            return
            
        # Add car to database
        success, result = db.add_dealer_car(dealer_id, make, model, year, photo_id)
        
        if success:
            # Show success message
            await message.answer(
                f"✅ Car added successfully!\n\n"
                f"Make: {make}\n"
                f"Model: {model}\n"
                f"Year: {year}",
                reply_markup=kb.dealer_menu_keyboard()
            )
            
            # Clear state
            await state.clear()
        else:
            # Show error message
            await message.answer(
                f"❌ Failed to add car: {result}",
                reply_markup=kb.dealer_menu_keyboard()
            )
            
    except Exception as e:
        logger.error(f"Error in dealer_add_car_photo_handler: {e}")
        state_data = await state.get_data()
        kb = KeyboardFactory(state_data.get('msgs', Messages('en')))
        await message.answer(
            "❌ An error occurred while processing the car photo.",
            reply_markup=kb.dealer_menu_keyboard()
        )

@router.message(DealerStates.adding_car_photo)
async def dealer_add_car_photo_text_handler(message: Message, state: FSMContext):
    """Handle text instead of photo"""
    await message.answer("❌ Please send a photo of the car. Text messages are not accepted here.")

@router.callback_query(lambda c: c.data.startswith("refresh_car_image_"))
async def refresh_car_image_handler(callback_query: CallbackQuery, state: FSMContext):
    """Handle refreshing a car's image when it becomes invalid"""
    if not is_admin_group(callback_query.message):
        await callback_query.answer("❌ This action is only available in the admin group.")
        return
        
    if not is_dealer(callback_query.from_user.id):
        await callback_query.answer("❌ You are not registered as a dealer.")
        return
        
    try:
        # Extract car_id from callback data
        car_id = int(callback_query.data.split('_')[-1])
        
        # Get dealer ID from user ID
        dealer_id = db.get_dealer_id(callback_query.from_user.id)
        
        # Get state data
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        # Verify the car belongs to this dealer
        cars = db.get_dealer_cars(dealer_id)
        car_ids = [car[0] for car in cars]
        
        if car_id not in car_ids:
            await callback_query.answer("❌ This car doesn't belong to you.")
            return
            
        # Ask user to upload a new photo
        await callback_query.message.answer(
            "Please upload a new photo for this car. The current image file ID is invalid.",
            reply_markup=kb.dealer_menu_keyboard()
        )
        
        # Store car_id in state
        await state.update_data(refresh_car_id=car_id)
        
        # Set state to refreshing car photo
        await state.set_state(DealerStates.refreshing_car_photo)
        
    except Exception as e:
        logger.error(f"Error in refresh_car_image_handler: {e}")
        state_data = await state.get_data()
        kb = KeyboardFactory(state_data.get('msgs', Messages('en')))
        await callback_query.message.answer(
            "❌ An error occurred while preparing to refresh car image.",
            reply_markup=kb.dealer_menu_keyboard()
        )

@router.message(DealerStates.refreshing_car_photo, F.photo)
async def process_refreshed_car_photo(message: Message, state: FSMContext):
    """Process the refreshed car photo"""
    if not is_admin_group(message):
        await message.answer("❌ This action is only available in the admin group.")
        return
        
    if not is_dealer(message.from_user.id):
        await message.answer("❌ You are not registered as a dealer.")
        return
        
    try:
        # Get state data
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        # Get car_id from state
        car_id = state_data.get('refresh_car_id')
        
        if not car_id:
            await message.answer(
                "❌ Car ID not found in state. Please try again.",
                reply_markup=kb.dealer_menu_keyboard()
            )
            await state.clear()
            return
            
        # Get photo file ID (largest size)
        photo_id = message.photo[-1].file_id
        
        # Update car image in database
        success, result = db.refresh_car_image(car_id, photo_id)
        
        if success:
            await message.answer(
                f"✅ Car image updated successfully!\n\n{result}",
                reply_markup=kb.dealer_menu_keyboard()
            )
        else:
            await message.answer(
                f"❌ Failed to update car image: {result}",
                reply_markup=kb.dealer_menu_keyboard()
            )
            
        # Clear state
        await state.clear()
            
    except Exception as e:
        logger.error(f"Error in process_refreshed_car_photo: {e}")
        state_data = await state.get_data()
        kb = KeyboardFactory(state_data.get('msgs', Messages('en')))
        await message.answer(
            "❌ An error occurred while processing the refreshed car photo.",
            reply_markup=kb.dealer_menu_keyboard()
        )
        await state.clear()

async def show_dealer_cars(callback_query: CallbackQuery, state: FSMContext, kb):
    """Show dealer's cars"""
    try:
        # Get dealer ID from user ID
        dealer_id = db.get_dealer_id(callback_query.from_user.id)
        
        if not dealer_id:
            await callback_query.answer("❌ You are not registered as a dealer.")
            return
            
        # Get cars from database
        cars = db.get_dealer_cars(dealer_id)
        
        if not cars or len(cars) == 0:
            # No cars found, show message with option to add one
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Add Car", callback_data="dealer_add_car")],
                [InlineKeyboardButton(text="🔙 Back", callback_data="dealer_back")]
            ])
            
            await send_or_edit_message(
                callback_query,
                "You have no cars in your inventory. You can add a new car.",
                reply_markup=keyboard
            )
            return
            
        # Create response text
        text = "🚗 Your Cars:\n\n"
        
        # Create keyboard with car actions
        keyboard = []
        
        for car in cars:
            car_id = car[0]
            make = car[1]
            model = car[2]
            year = car[3]
            available = "✅ Available" if car[4] else "❌ Booked"
            
            text += f"🔹 {make} {model} ({year})\n"
            text += f"Status: {available}\n\n"
            
            # Add view/delete buttons for this car
            keyboard.append([
                InlineKeyboardButton(
                    text=f"👁️ View {make} {model}",
                    callback_data=f"view_dealer_car_{car_id}"
                )
            ])
            keyboard.append([
                InlineKeyboardButton(
                    text=f"🗑️ Delete {make} {model}",
                    callback_data=f"delete_dealer_car_{car_id}"
                )
            ])
        
        # Add add car button
        keyboard.append([
            InlineKeyboardButton(text="➕ Add Car", callback_data="dealer_add_car")
        ])
        
        # Add back button
        keyboard.append([
            InlineKeyboardButton(text="🔙 Back", callback_data="dealer_back")
        ])
        
        # Send message with car list
        await send_or_edit_message(
            callback_query,
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        
        # Set state to viewing cars
        await state.set_state(DealerStates.viewing_cars)
        
    except Exception as e:
        logger.error(f"Error in show_dealer_cars: {e}")
        await callback_query.message.answer(
            "❌ An error occurred while retrieving your cars.",
            reply_markup=kb.dealer_menu_keyboard()
        )

async def show_dealer_stats(callback_query: CallbackQuery, state: FSMContext, kb):
    """Show dealer's booking statistics"""
    try:
        # Get dealer ID from user ID
        dealer_id = db.get_dealer_id(callback_query.from_user.id)
        
        if not dealer_id:
            await callback_query.answer("❌ You are not registered as a dealer.")
            return
            
        # Get stats from database
        stats = db.get_dealer_stats(dealer_id)
        
        if not stats:
            await send_or_edit_message(
                callback_query,
                "No statistics available. You may not have any bookings yet.",
                reply_markup=kb.dealer_menu_keyboard()
            )
            return
            
        # Create response text
        text = "📊 Your Booking Statistics:\n\n"
        
        # Add stats to text
        text += f"🚗 Total Cars: {stats['total_cars']}\n"
        text += f"📋 Total Bookings: {stats['total_bookings']}\n"
        text += f"✅ Active Bookings: {stats['active_bookings']}\n"
        text += f"🔄 Completed Bookings: {stats['completed_bookings']}\n\n"
        
        # Add car statistics
        if stats['car_stats']:
            text += "🚗 Car Performance:\n"
            for car_stat in stats['car_stats']:
                text += f"  • {car_stat['make']} {car_stat['model']} ({car_stat['year']}): {car_stat['bookings']} bookings\n"
        
        # Add back button
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back", callback_data="dealer_back")]
        ])
        
        # Send message with stats
        await send_or_edit_message(
            callback_query,
            text,
            reply_markup=keyboard
        )
        
        # Set state to viewing stats
        await state.set_state(DealerStates.viewing_stats)
        
    except Exception as e:
        logger.error(f"Error in show_dealer_stats: {e}")
        await callback_query.message.answer(
            "❌ An error occurred while retrieving your statistics.",
            reply_markup=kb.dealer_menu_keyboard()
        )

@router.callback_query(lambda c: c.data.startswith("delete_dealer_car_"))
async def delete_dealer_car_handler(callback_query: CallbackQuery, state: FSMContext):
    """Handle dealer car deletion"""
    if not is_admin_group(callback_query.message):
        await callback_query.answer("❌ This action is only available in the admin group.")
        return
        
    if not is_dealer(callback_query.from_user.id):
        await callback_query.answer("❌ You are not registered as a dealer.")
        return
        
    try:
        # Get state data
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        # Extract car ID from callback data
        car_id = int(callback_query.data.replace("delete_dealer_car_", ""))
        
        # Store car ID in state
        await state.update_data(car_id_to_delete=car_id)
        
        # Ask for confirmation
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Yes, delete", callback_data=f"confirm_delete_dealer_car_{car_id}"),
                InlineKeyboardButton(text="❌ No, cancel", callback_data="dealer_my_cars")
            ]
        ])
        
        await send_or_edit_message(
            callback_query,
            f"⚠️ Are you sure you want to delete this car? This action cannot be undone.",
            reply_markup=keyboard
        )
        
        # Set state to confirming delete
        await state.set_state(DealerStates.confirming_delete_car)
        
    except Exception as e:
        logger.error(f"Error in delete_dealer_car_handler: {e}")
        state_data = await state.get_data()
        kb = KeyboardFactory(state_data.get('msgs', Messages('en')))
        await callback_query.message.answer(
            "❌ An error occurred while preparing to delete the car.",
            reply_markup=kb.dealer_menu_keyboard()
        )

@router.callback_query(lambda c: c.data.startswith("confirm_delete_dealer_car_"))
async def confirm_delete_dealer_car_handler(callback_query: CallbackQuery, state: FSMContext):
    """Handle dealer car deletion confirmation"""
    if not is_admin_group(callback_query.message):
        await callback_query.answer("❌ This action is only available in the admin group.")
        return
        
    if not is_dealer(callback_query.from_user.id):
        await callback_query.answer("❌ You are not registered as a dealer.")
        return
        
    try:
        # Get state data
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        # Extract car ID from callback data
        car_id = int(callback_query.data.replace("confirm_delete_dealer_car_", ""))
        
        # Get dealer ID from user ID
        dealer_id = db.get_dealer_id(callback_query.from_user.id)
        
        if not dealer_id:
            await callback_query.answer("❌ You are not registered as a dealer.")
            return
            
        # Delete car in database
        success, message = db.delete_dealer_car(dealer_id, car_id)
        
        if success:
            # Notify dealer
            await callback_query.answer("✅ Car deleted successfully")
            
            # Show success message
            await send_or_edit_message(
                callback_query,
                f"✅ Car has been deleted successfully.",
                reply_markup=kb.dealer_menu_keyboard()
            )
            
            # Clear state
            await state.clear()
        else:
            await callback_query.answer(f"❌ Error: {message}")
            
            # Show error message
            await send_or_edit_message(
                callback_query,
                f"❌ Failed to delete car: {message}",
                reply_markup=kb.dealer_menu_keyboard()
            )
            
    except Exception as e:
        logger.error(f"Error in confirm_delete_dealer_car_handler: {e}")
        state_data = await state.get_data()
        kb = KeyboardFactory(state_data.get('msgs', Messages('en')))
        await callback_query.message.answer(
            "❌ An error occurred while deleting the car.",
            reply_markup=kb.dealer_menu_keyboard()
        )

async def back_to_dealer_menu(callback_query: CallbackQuery, state: FSMContext, kb):
    """Go back to dealer menu"""
    try:
        # Clear state
        await state.clear()
        
        # Show dealer menu
        await send_or_edit_message(
            callback_query,
            "🚗 Dealer Panel",
            reply_markup=kb.dealer_menu_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Error in back_to_dealer_menu: {e}")
        await callback_query.message.answer(
            "❌ An error occurred while returning to the dealer menu.",
            reply_markup=kb.dealer_menu_keyboard()
        )

@router.callback_query(lambda c: c.data.startswith("view_dealer_car_"))
async def view_dealer_car_handler(callback_query: CallbackQuery, state: FSMContext):
    """Handle viewing a dealer's car details"""
    if not is_admin_group(callback_query.message):
        await callback_query.answer("❌ This action is only available in the admin group.")
        return
        
    if not is_dealer(callback_query.from_user.id):
        await callback_query.answer("❌ You are not registered as a dealer.")
        return
        
    try:
        # Extract car_id from callback data
        car_id = int(callback_query.data.split('_')[-1])
        
        # Get dealer ID from user ID 
        dealer_id = db.get_dealer_id(callback_query.from_user.id)
        
        # Get state data
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        # Verify the car belongs to this dealer
        cars = db.get_dealer_cars(dealer_id)
        
        selected_car = None
        for car in cars:
            if car[0] == car_id:
                selected_car = car
                break
                
        if not selected_car:
            await callback_query.answer("❌ This car doesn't belong to you or doesn't exist.")
            return
            
        # Get car details with image
        car_details = db.get_car_details(car_id)
        if not car_details:
            await send_or_edit_message(
                callback_query,
                "❌ Car details could not be loaded.",
                reply_markup=kb.dealer_menu_keyboard()
            )
            return
            
        # Format car info
        make = selected_car[1]
        model = selected_car[2]
        year = selected_car[3]
        available = "✅ Available" if selected_car[4] else "❌ Currently Booked"
        
        car_info = f"🚗 {make} {model} ({year})\n"
        car_info += f"Status: {available}\n"
        
        # Get primary image
        images = car_details.get('images', [])
        photo = None
        for img in images:
            if img[1]:  # is_primary
                photo = img[0]
                break
                
        # Display car with image and keyboard with refresh/delete options
        await send_or_edit_message(
            callback_query,
            car_info,
            reply_markup=kb.dealer_car_keyboard(car_id),
            photo=photo,
            car_id=car_id  # Pass car_id for auto-refresh
        )
        
    except Exception as e:
        logger.error(f"Error in view_dealer_car_handler: {e}")
        state_data = await state.get_data()
        kb = KeyboardFactory(state_data.get('msgs', Messages('en')))
        await callback_query.message.answer(
            "❌ An error occurred while viewing car details.",
            reply_markup=kb.dealer_menu_keyboard()
        ) 