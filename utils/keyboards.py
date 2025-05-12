from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class KeyboardFactory:
    """Factory class for keyboard generation"""
    
    def __init__(self, messages):
        self.msgs = messages
    
    def language_keyboard(self, show_back_button: bool = False):
        """Generate language selection keyboard
        
        Args:
            show_back_button: Whether to show the back button (only for language change, not initial selection)
        """
        keyboard = [
            [
                InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en"),
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")
            ]
        ]
        
        if show_back_button:
            keyboard.append([InlineKeyboardButton(text=self.msgs.get('back_btn'), callback_data="back_to_menu")])
        
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    def main_menu_keyboard(self):
        """Generate main menu keyboard"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=self.msgs.get('list_cars_btn'), callback_data="list_cars_command")],
            [InlineKeyboardButton(text=self.msgs.get('my_booking_btn'), callback_data="my_booking")],
            [InlineKeyboardButton(text=self.msgs.get('contact_admin_btn'), callback_data="contact_admin")],
            [InlineKeyboardButton(text=self.msgs.get('change_language_btn'), callback_data="change_language")]
        ])
    
    def car_list_keyboard(self, cars, page=0, page_size=5):
        """Generate keyboard for car list with pagination
        
        Args:
            cars: List of car tuples from database
            page: Current page number (0-based)
            page_size: Number of cars per page
            
        Returns:
            InlineKeyboardMarkup: Keyboard with car buttons and pagination controls
        """
        keyboard = []
        
        # Calculate pagination
        total_cars = len(cars)
        total_pages = (total_cars + page_size - 1) // page_size
        start_idx = page * page_size
        end_idx = min(start_idx + page_size, total_cars)
        
        # Add car buttons for current page
        for i in range(start_idx, end_idx):
            car = cars[i]
            keyboard.append([
                InlineKeyboardButton(
                    text=f"{car[1]} {car[2]} ({car[3]})",
                    callback_data=f"car_{car[0]}"
                )
            ])
        
        # Add pagination controls if needed
        if total_pages > 1:
            pagination_row = []
            
            # Previous page button
            if page > 0:
                pagination_row.append(
                    InlineKeyboardButton(text="⬅️ Prev", callback_data=f"car_page_{page-1}")
                )
                
            # Page indicator
            pagination_row.append(
                InlineKeyboardButton(text=f"📄 {page+1}/{total_pages}", callback_data="noop")
            )
            
            # Next page button
            if page < total_pages - 1:
                pagination_row.append(
                    InlineKeyboardButton(text="Next ➡️", callback_data=f"car_page_{page+1}")
                )
                
            keyboard.append(pagination_row)
        
        # Add back button
        keyboard.append([InlineKeyboardButton(text=self.msgs.get('back_btn'), callback_data="back_to_menu")])
        
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    def car_details_keyboard(self, car_id):
        """Generate keyboard for car details with cancel option"""
        # Ensure car_id is correctly formatted
        car_id_str = str(car_id)
        logger.info(f"Creating car details keyboard for car ID: {car_id_str}")
        
        # Create buttons with clear IDs
        book_button = InlineKeyboardButton(
            text=self.msgs.get('book_car_btn'), 
            callback_data=f"book_{car_id_str}"
        )
        back_button = InlineKeyboardButton(
            text=self.msgs.get('back_btn'), 
            callback_data="list_cars"
        )
        
        return InlineKeyboardMarkup(inline_keyboard=[
            [book_button],
            [back_button]
        ])
    
    def booking_details_keyboard(self, booking_id):
        """Generate keyboard for booking details with cancel option"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=self.msgs.get('return_car_btn'), callback_data=f"return_{booking_id}")],
            [InlineKeyboardButton(text=self.msgs.get('back_btn'), callback_data="back_to_menu")]
        ])
    
    def admin_menu_keyboard(self):
        """Generate admin menu keyboard"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 View Bookings", callback_data="admin_all_bookings")],
            [InlineKeyboardButton(text="👥 View Dealers", callback_data="admin_dealers")]
        ])
    
    def dealer_menu_keyboard(self):
        """Generate dealer menu keyboard"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add New Car", callback_data="dealer_add_car")],
            [InlineKeyboardButton(text="🚗 My Cars", callback_data="dealer_my_cars")],
            [InlineKeyboardButton(text="📊 Booking Statistics", callback_data="dealer_stats")]
        ])
    
    def generate_date_keyboard(self, for_start=True):
        """Generate keyboard with dates for booking"""
        keyboard = []
        today = datetime.now()
        
        # Generate dates for next 7 days
        for i in range(7):
            date = today + timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            display_str = date.strftime("%d %b")
            
            # Add readable prefixes
            if i == 0:
                display_str = "Today, " + display_str
            elif i == 1:
                display_str = "Tomorrow, " + display_str
                
            prefix = "start_date_" if for_start else "end_date_"
            keyboard.append([InlineKeyboardButton(text=display_str, callback_data=f"{prefix}{date_str}")])
            
        # Add back button
        keyboard.append([
            InlineKeyboardButton(text="🔙 Back", callback_data="list_cars"),
            InlineKeyboardButton(text="❌ Cancel", callback_data="back_to_menu")
        ])
        
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    def generate_time_keyboard(self, for_start=True):
        """Generate keyboard with time slots for booking"""
        keyboard = []
        now = datetime.now()
        start_hour = now.hour if for_start and now.hour >= 8 else 8
        
        # Generate time slots from start_hour to 20:00
        for hour in range(start_hour, 21):
            for minute in [0, 30]:
                # Skip times in the past for today
                if for_start and hour == now.hour and minute <= now.minute:
                    continue
                    
                time_str = f"{hour:02d}:{minute:02d}"
                display_str = time_str
                prefix = "start_time_" if for_start else "end_time_"
                keyboard.append([InlineKeyboardButton(text=display_str, callback_data=f"{prefix}{time_str}")])
        
        # Add back button and cancel button
        back_callback = "start_date_back" if for_start else "end_date_back"
        keyboard.append([
            InlineKeyboardButton(text="🔙 Back", callback_data=back_callback),
            InlineKeyboardButton(text="❌ Cancel", callback_data="back_to_menu")
        ])
        
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    def dealer_car_keyboard(self, car_id):
        """Keyboard for dealer car actions"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=self.msgs.get('delete_car'), callback_data=f"delete_dealer_car_{car_id}")],
            [InlineKeyboardButton(text="🔄 Refresh Image", callback_data=f"refresh_car_image_{car_id}")],
            [InlineKeyboardButton(text=self.msgs.get('back'), callback_data="dealer_my_cars")]
        ]) 