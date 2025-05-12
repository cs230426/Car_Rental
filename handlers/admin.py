import logging
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import db
from config.config import ADMIN_GROUP_ID, logger
from utils.helpers import send_or_edit_message, is_admin_group, format_booking_info
from utils.keyboards import KeyboardFactory
from messages import Messages

# Create a router for admin handlers
router = Router()

# States for admin interactions
class AdminStates(StatesGroup):
    viewing_bookings = State()
    confirming_delete_booking = State()
    managing_dealers = State()
    confirming_delete_dealer = State()
    adding_dealer = State()
    adding_dealer_name = State()
    adding_dealer_telegram_id = State()

# Admin command - only works in admin group
@router.message(Command("admin"))
async def admin_command_handler(message: Message, state: FSMContext):
    """Handle /admin command in admin group"""
    if not is_admin_group(message):
        await message.answer("❌ This command is only available in the admin group.")
        return
        
    try:
        # Set language to English for admin panel
        msgs = Messages('en')
        kb = KeyboardFactory(msgs)
        
        # Store in state for use in other handlers
        await state.update_data(language='en', msgs=msgs)
        
        # Show admin menu
        await message.answer(
            "🔐 Admin Panel",
            reply_markup=kb.admin_menu_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Error in admin_command_handler: {e}")
        await message.answer("❌ An error occurred. Please try again later.")

# Admin callbacks
@router.callback_query(lambda c: c.data.startswith("admin_"))
async def admin_callback_handler(callback_query: CallbackQuery, state: FSMContext):
    """Handle admin menu callbacks"""
    if not is_admin_group(callback_query.message):
        await callback_query.answer("❌ This action is only available in the admin group.")
        return
        
    try:
        # Get language configuration from state or create new
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        action = callback_query.data.replace("admin_", "")
        
        if action == "all_bookings":
            await show_all_bookings(callback_query, state, kb)
        elif action == "dealers":
            await show_all_dealers(callback_query, state, kb)
        elif action == "add_dealer":
            await start_add_dealer(callback_query, state, kb)
        elif action == "pending_bookings":
            await show_pending_bookings(callback_query, state, kb)
        elif action == "active_bookings":
            await show_active_bookings(callback_query, state, kb)
        elif action == "back":
            await back_to_admin_menu(callback_query, state, kb)
        else:
            await callback_query.answer("Unknown action")
            
    except Exception as e:
        logger.error(f"Error in admin_callback_handler: {e}")
        await callback_query.message.answer("❌ An error occurred. Please try again later.")

@router.callback_query(lambda c: c.data == "admin_back")
async def admin_back_handler(callback_query: CallbackQuery, state: FSMContext):
    """Handle admin back button"""
    try:
        # Get language configuration from state
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        # Call back_to_admin_menu function
        await back_to_admin_menu(callback_query, state, kb)
        
    except Exception as e:
        logger.error(f"Error in admin_back_handler: {e}")
        await callback_query.message.answer(
            "❌ An error occurred. Please try again later."
        )

async def show_all_bookings(callback_query: CallbackQuery, state: FSMContext, kb):
    """Show all bookings for admin"""
    try:
        # Get bookings from database
        bookings = db.get_all_bookings()
        
        if not bookings or len(bookings) == 0:
            await send_or_edit_message(
                callback_query,
                "No bookings found.",
                reply_markup=kb.admin_menu_keyboard()
            )
            return
            
        # Create response text
        text = "📋 All Bookings:\n\n"
        
        # Create keyboard with booking actions
        keyboard = []
        
        for booking in bookings[:10]:  # Limit to first 10 bookings
            booking_id = booking[0]
            start_date = booking[1].strftime("%Y-%m-%d %H:%M") if booking[1] else "N/A"
            end_date = booking[2].strftime("%Y-%m-%d %H:%M") if booking[2] else "Active"
            active = "✅ Active" if booking[3] else "❌ Completed"
            customer = booking[4]
            car_info = f"{booking[6]} {booking[7]} ({booking[8]})"
            
            text += f"🔹 Booking #{booking_id}\n"
            text += f"👤 Customer: {customer}\n"
            text += f"🚗 Car: {car_info}\n"
            text += f"📅 From: {start_date}\n"
            text += f"📅 To: {end_date}\n"
            text += f"Status: {active}\n\n"
            
            # Add action buttons for this booking
            keyboard.append([
                InlineKeyboardButton(
                    text=f"🗑️ Delete #{booking_id}",
                    callback_data=f"delete_booking_{booking_id}"
                )
            ])
        
        # Add navigation buttons
        keyboard.append([
            InlineKeyboardButton(text="📱 Pending", callback_data="admin_pending_bookings"),
            InlineKeyboardButton(text="✅ Active", callback_data="admin_active_bookings")
        ])
        
        # Add back button
        keyboard.append([
            InlineKeyboardButton(text="🔙 Back", callback_data="admin_back")
        ])
        
        # Send message with booking list
        await send_or_edit_message(
            callback_query,
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        
        # Set state to viewing bookings
        await state.set_state(AdminStates.viewing_bookings)
        
    except Exception as e:
        logger.error(f"Error in show_all_bookings: {e}")
        await callback_query.message.answer(
            "❌ An error occurred while retrieving bookings.",
            reply_markup=kb.admin_menu_keyboard()
        )

async def show_pending_bookings(callback_query: CallbackQuery, state: FSMContext, kb):
    """Show pending bookings for admin to approve/reject"""
    try:
        # Get pending bookings from database
        pending_bookings = db.get_pending_bookings()
        
        if not pending_bookings or len(pending_bookings) == 0:
            await send_or_edit_message(
                callback_query,
                "No pending bookings found.",
                reply_markup=kb.admin_menu_keyboard()
            )
            return
            
        # Create response text
        text = "📱 Pending Bookings:\n\n"
        
        # Create keyboard with approve/reject actions
        keyboard = []
        
        for booking in pending_bookings:
            booking_id = booking[0]
            start_date = booking[1].strftime("%Y-%m-%d %H:%M") if booking[1] else "N/A"
            customer = booking[4]
            car_info = f"{booking[6]} {booking[7]} ({booking[8]})"
            
            text += f"🔹 Booking #{booking_id}\n"
            text += f"👤 Customer: {customer}\n"
            text += f"🚗 Car: {car_info}\n"
            text += f"📅 From: {start_date}\n\n"
            
            # Add approve/reject buttons for this booking
            keyboard.append([
                InlineKeyboardButton(
                    text=f"✅ Approve #{booking_id}",
                    callback_data=f"approve_booking_{booking_id}"
                ),
                InlineKeyboardButton(
                    text=f"❌ Reject #{booking_id}",
                    callback_data=f"reject_booking_{booking_id}"
                )
            ])
        
        # Add back button
        keyboard.append([
            InlineKeyboardButton(text="🔙 Back", callback_data="admin_all_bookings")
        ])
        
        # Send message with pending booking list
        await send_or_edit_message(
            callback_query,
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        
    except Exception as e:
        logger.error(f"Error in show_pending_bookings: {e}")
        await callback_query.message.answer(
            "❌ An error occurred while retrieving pending bookings.",
            reply_markup=kb.admin_menu_keyboard()
        )

async def show_active_bookings(callback_query: CallbackQuery, state: FSMContext, kb):
    """Show active bookings for admin to manage"""
    try:
        # Get active bookings from database
        active_bookings = db.get_active_bookings()
        
        if not active_bookings or len(active_bookings) == 0:
            await send_or_edit_message(
                callback_query,
                "No active bookings found.",
                reply_markup=kb.admin_menu_keyboard()
            )
            return
            
        # Create response text
        text = "✅ Active Bookings:\n\n"
        
        # Create keyboard with booking actions
        keyboard = []
        
        for booking in active_bookings:
            booking_id = booking[0]
            start_date = booking[1].strftime("%Y-%m-%d %H:%M") if booking[1] else "N/A"
            customer = booking[4]
            car_info = f"{booking[6]} {booking[7]} ({booking[8]})"
            
            text += f"🔹 Booking #{booking_id}\n"
            text += f"👤 Customer: {customer}\n"
            text += f"🚗 Car: {car_info}\n"
            text += f"📅 From: {start_date}\n\n"
            
            # Add action buttons for this booking
            keyboard.append([
                InlineKeyboardButton(
                    text=f"🗑️ Cancel #{booking_id}",
                    callback_data=f"delete_booking_{booking_id}"
                )
            ])
        
        # Add back button
        keyboard.append([
            InlineKeyboardButton(text="🔙 Back", callback_data="admin_all_bookings")
        ])
        
        # Send message with active booking list
        await send_or_edit_message(
            callback_query,
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        
    except Exception as e:
        logger.error(f"Error in show_active_bookings: {e}")
        await callback_query.message.answer(
            "❌ An error occurred while retrieving active bookings.",
            reply_markup=kb.admin_menu_keyboard()
        )

@router.callback_query(lambda c: c.data.startswith("approve_booking_"))
async def approve_booking_handler(callback_query: CallbackQuery, state: FSMContext):
    """Handle booking approval"""
    if not is_admin_group(callback_query.message):
        await callback_query.answer("❌ This action is only available in the admin group.")
        return
        
    try:
        # Get keyboard factory
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        # Extract booking ID from callback data
        booking_id = int(callback_query.data.replace("approve_booking_", ""))
        
        # Approve booking in database
        success, message = db.approve_booking(booking_id)
        
        if success:
            # Notify admin
            await callback_query.answer("✅ Booking approved")
            
            # Refresh pending bookings list
            await show_pending_bookings(callback_query, state, kb)
        else:
            await callback_query.answer(f"❌ Error: {message}")
            
    except Exception as e:
        logger.error(f"Error in approve_booking_handler: {e}")
        state_data = await state.get_data()
        kb = KeyboardFactory(state_data.get('msgs', Messages('en')))
        await callback_query.message.answer(
            "❌ An error occurred while approving the booking.",
            reply_markup=kb.admin_menu_keyboard()
        )

@router.callback_query(lambda c: c.data.startswith("reject_booking_"))
async def reject_booking_handler(callback_query: CallbackQuery, state: FSMContext):
    """Handle booking rejection"""
    if not is_admin_group(callback_query.message):
        await callback_query.answer("❌ This action is only available in the admin group.")
        return
        
    try:
        # Get keyboard factory
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        # Extract booking ID from callback data
        booking_id = int(callback_query.data.replace("reject_booking_", ""))
        
        # Reject booking in database
        success, message = db.reject_booking(booking_id)
        
        if success:
            # Notify admin
            await callback_query.answer("❌ Booking rejected")
            
            # Refresh pending bookings list
            await show_pending_bookings(callback_query, state, kb)
        else:
            await callback_query.answer(f"❌ Error: {message}")
            
    except Exception as e:
        logger.error(f"Error in reject_booking_handler: {e}")
        state_data = await state.get_data()
        kb = KeyboardFactory(state_data.get('msgs', Messages('en')))
        await callback_query.message.answer(
            "❌ An error occurred while rejecting the booking.",
            reply_markup=kb.admin_menu_keyboard()
        )

@router.callback_query(lambda c: c.data.startswith("delete_booking_"))
async def delete_booking_handler(callback_query: CallbackQuery, state: FSMContext):
    """Handle booking deletion"""
    if not is_admin_group(callback_query.message):
        await callback_query.answer("❌ This action is only available in the admin group.")
        return
        
    try:
        # Extract booking ID from callback data
        booking_id = int(callback_query.data.replace("delete_booking_", ""))
        
        # Store booking ID in state
        await state.update_data(booking_id_to_delete=booking_id)
        
        # Ask for confirmation
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Yes, delete", callback_data=f"confirm_delete_booking_{booking_id}"),
                InlineKeyboardButton(text="❌ No, cancel", callback_data="admin_all_bookings")
            ]
        ])
        
        await send_or_edit_message(
            callback_query,
            f"⚠️ Are you sure you want to delete booking #{booking_id}? This action cannot be undone.",
            reply_markup=keyboard
        )
        
        # Set state to confirming delete
        await state.set_state(AdminStates.confirming_delete_booking)
        
    except Exception as e:
        logger.error(f"Error in delete_booking_handler: {e}")
        state_data = await state.get_data()
        kb = KeyboardFactory(state_data.get('msgs', Messages('en')))
        await callback_query.message.answer(
            "❌ An error occurred while preparing to delete the booking.",
            reply_markup=kb.admin_menu_keyboard()
        )

@router.callback_query(lambda c: c.data.startswith("confirm_delete_booking_"))
async def confirm_delete_booking_handler(callback_query: CallbackQuery, state: FSMContext):
    """Handle booking deletion confirmation"""
    if not is_admin_group(callback_query.message):
        await callback_query.answer("❌ This action is only available in the admin group.")
        return
        
    try:
        # Get keyboard factory
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        # Extract booking ID from callback data
        booking_id = int(callback_query.data.replace("confirm_delete_booking_", ""))
        
        # Delete booking in database
        success, message = db.admin_delete_booking(booking_id)
        
        if success:
            # Notify admin
            await callback_query.answer("✅ Booking deleted successfully")
            
            # Show success message
            await send_or_edit_message(
                callback_query,
                f"✅ Booking #{booking_id} has been deleted successfully.",
                reply_markup=kb.admin_menu_keyboard()
            )
            
            # Clear state
            await state.clear()
        else:
            await callback_query.answer(f"❌ Error: {message}")
            
            # Show error message
            await send_or_edit_message(
                callback_query,
                f"❌ Failed to delete booking: {message}",
                reply_markup=kb.admin_menu_keyboard()
            )
            
    except Exception as e:
        logger.error(f"Error in confirm_delete_booking_handler: {e}")
        state_data = await state.get_data()
        kb = KeyboardFactory(state_data.get('msgs', Messages('en')))
        await callback_query.message.answer(
            "❌ An error occurred while deleting the booking.",
            reply_markup=kb.admin_menu_keyboard()
        )

async def show_all_dealers(callback_query: CallbackQuery, state: FSMContext, kb):
    """Show all dealers for admin"""
    try:
        # Get dealers from database
        dealers = db.get_all_dealers()
        
        if not dealers or len(dealers) == 0:
            # No dealers found, show message with option to add one
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Add Dealer", callback_data="admin_add_dealer")],
                [InlineKeyboardButton(text="🔙 Back", callback_data="admin_back")]
            ])
            
            await send_or_edit_message(
                callback_query,
                "No dealers found. You can add a new dealer.",
                reply_markup=keyboard
            )
            return
            
        # Create response text
        text = "👥 Dealers:\n\n"
        
        # Create keyboard with dealer actions
        keyboard = []
        
        for dealer in dealers:
            dealer_id = dealer[0]
            telegram_id = dealer[1]
            name = dealer[2]
            
            text += f"🔹 {name} (ID: {dealer_id})\n"
            text += f"Telegram ID: {telegram_id}\n\n"
            
            # Add delete button for this dealer
            keyboard.append([
                InlineKeyboardButton(
                    text=f"🗑️ Delete {name}",
                    callback_data=f"delete_dealer_{dealer_id}"
                )
            ])
        
        # Add add dealer button
        keyboard.append([
            InlineKeyboardButton(text="➕ Add Dealer", callback_data="admin_add_dealer")
        ])
        
        # Add back button
        keyboard.append([
            InlineKeyboardButton(text="🔙 Back", callback_data="admin_back")
        ])
        
        # Send message with dealer list
        await send_or_edit_message(
            callback_query,
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        
        # Set state to managing dealers
        await state.set_state(AdminStates.managing_dealers)
        
    except Exception as e:
        logger.error(f"Error in show_all_dealers: {e}")
        await callback_query.message.answer(
            "❌ An error occurred while retrieving dealers.",
            reply_markup=kb.admin_menu_keyboard()
        )

async def start_add_dealer(callback_query: CallbackQuery, state: FSMContext, kb):
    """Start the process of adding a dealer"""
    try:
        # Ask for dealer name
        await send_or_edit_message(
            callback_query,
            "Please enter the dealer's name:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Cancel", callback_data="admin_dealers")]
            ])
        )
        
        # Set state to adding dealer name
        await state.set_state(AdminStates.adding_dealer_name)
        
    except Exception as e:
        logger.error(f"Error in start_add_dealer: {e}")
        await callback_query.message.answer(
            "❌ An error occurred while preparing to add a dealer.",
            reply_markup=kb.admin_menu_keyboard()
        )

@router.message(AdminStates.adding_dealer_name)
async def add_dealer_name_handler(message: Message, state: FSMContext):
    """Handle dealer name input"""
    if not is_admin_group(message):
        await message.answer("❌ This action is only available in the admin group.")
        return
        
    try:
        # Get keyboard factory
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        # Get dealer name from message
        dealer_name = message.text.strip()
        
        # Validate dealer name
        if not dealer_name or len(dealer_name) < 2 or len(dealer_name) > 50:
            await message.answer(
                "❌ Invalid dealer name. Please enter a name between 2 and 50 characters.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Cancel", callback_data="admin_dealers")]
                ])
            )
            return
        
        # Store dealer name in state
        await state.update_data(dealer_name=dealer_name)
        
        # Ask for dealer Telegram ID
        await message.answer(
            "Please enter the dealer's Telegram ID (must be a number):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Cancel", callback_data="admin_dealers")]
            ])
        )
        
        # Set state to adding dealer Telegram ID
        await state.set_state(AdminStates.adding_dealer_telegram_id)
        
    except Exception as e:
        logger.error(f"Error in add_dealer_name_handler: {e}")
        state_data = await state.get_data()
        kb = KeyboardFactory(state_data.get('msgs', Messages('en')))
        await message.answer(
            "❌ An error occurred while processing the dealer name.",
            reply_markup=kb.admin_menu_keyboard()
        )

@router.message(AdminStates.adding_dealer_telegram_id)
async def add_dealer_telegram_id_handler(message: Message, state: FSMContext):
    """Handle dealer Telegram ID input"""
    if not is_admin_group(message):
        await message.answer("❌ This action is only available in the admin group.")
        return
        
    try:
        # Get keyboard factory
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        # Get dealer Telegram ID from message
        telegram_id_str = message.text.strip()
        
        # Validate dealer Telegram ID
        try:
            telegram_id = int(telegram_id_str)
        except ValueError:
            await message.answer(
                "❌ Invalid Telegram ID. Please enter a valid number.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Cancel", callback_data="admin_dealers")]
                ])
            )
            return
        
        # Get dealer name from state
        data = await state.get_data()
        dealer_name = data.get('dealer_name')
        
        # Add dealer to database
        success, result = db.add_dealer(telegram_id, dealer_name)
        
        if success:
            # Show success message
            await message.answer(
                f"✅ Dealer {dealer_name} (Telegram ID: {telegram_id}) added successfully.",
                reply_markup=kb.admin_menu_keyboard()
            )
            
            # Clear state
            await state.clear()
        else:
            # Show error message
            await message.answer(
                f"❌ Failed to add dealer: {result}",
                reply_markup=kb.admin_menu_keyboard()
            )
        
    except Exception as e:
        logger.error(f"Error in add_dealer_telegram_id_handler: {e}")
        state_data = await state.get_data()
        kb = KeyboardFactory(state_data.get('msgs', Messages('en')))
        await message.answer(
            "❌ An error occurred while processing the dealer Telegram ID.",
            reply_markup=kb.admin_menu_keyboard()
        )

@router.callback_query(lambda c: c.data.startswith("delete_dealer_"))
async def delete_dealer_handler(callback_query: CallbackQuery, state: FSMContext):
    """Handle dealer deletion"""
    if not is_admin_group(callback_query.message):
        await callback_query.answer("❌ This action is only available in the admin group.")
        return
        
    try:
        # Extract dealer ID from callback data
        dealer_id = int(callback_query.data.replace("delete_dealer_", ""))
        
        # Store dealer ID in state
        await state.update_data(dealer_id_to_delete=dealer_id)
        
        # Ask for confirmation
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Yes, delete", callback_data=f"confirm_delete_dealer_{dealer_id}"),
                InlineKeyboardButton(text="❌ No, cancel", callback_data="admin_dealers")
            ]
        ])
        
        await send_or_edit_message(
            callback_query,
            f"⚠️ Are you sure you want to delete dealer #{dealer_id}? All cars associated with this dealer will also be deleted. This action cannot be undone.",
            reply_markup=keyboard
        )
        
        # Set state to confirming delete
        await state.set_state(AdminStates.confirming_delete_dealer)
        
    except Exception as e:
        logger.error(f"Error in delete_dealer_handler: {e}")
        state_data = await state.get_data()
        kb = KeyboardFactory(state_data.get('msgs', Messages('en')))
        await callback_query.message.answer(
            "❌ An error occurred while preparing to delete the dealer.",
            reply_markup=kb.admin_menu_keyboard()
        )

@router.callback_query(lambda c: c.data.startswith("confirm_delete_dealer_"))
async def confirm_delete_dealer_handler(callback_query: CallbackQuery, state: FSMContext):
    """Handle dealer deletion confirmation"""
    if not is_admin_group(callback_query.message):
        await callback_query.answer("❌ This action is only available in the admin group.")
        return
        
    try:
        # Get keyboard factory
        state_data = await state.get_data()
        msgs = state_data.get('msgs', Messages('en'))
        kb = KeyboardFactory(msgs)
        
        # Extract dealer ID from callback data
        dealer_id = int(callback_query.data.replace("confirm_delete_dealer_", ""))
        
        # Delete dealer in database
        success, message = db.delete_dealer(dealer_id)
        
        if success:
            # Notify admin
            await callback_query.answer("✅ Dealer deleted successfully")
            
            # Show success message
            await send_or_edit_message(
                callback_query,
                f"✅ Dealer #{dealer_id} has been deleted successfully.",
                reply_markup=kb.admin_menu_keyboard()
            )
            
            # Clear state
            await state.clear()
        else:
            await callback_query.answer(f"❌ Error: {message}")
            
            # Show error message
            await send_or_edit_message(
                callback_query,
                f"❌ Failed to delete dealer: {message}",
                reply_markup=kb.admin_menu_keyboard()
            )
            
    except Exception as e:
        logger.error(f"Error in confirm_delete_dealer_handler: {e}")
        state_data = await state.get_data()
        kb = KeyboardFactory(state_data.get('msgs', Messages('en')))
        await callback_query.message.answer(
            "❌ An error occurred while deleting the dealer.",
            reply_markup=kb.admin_menu_keyboard()
        )

async def back_to_admin_menu(callback_query: CallbackQuery, state: FSMContext, kb):
    """Go back to admin menu"""
    try:
        # Clear state
        await state.clear()
        
        # Show admin menu
        await send_or_edit_message(
            callback_query,
            "🔐 Admin Panel",
            reply_markup=kb.admin_menu_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Error in back_to_admin_menu: {e}")
        await callback_query.message.answer(
            "❌ An error occurred while returning to the admin menu.",
            reply_markup=kb.admin_menu_keyboard()
        ) 