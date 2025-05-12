from typing import Dict, Any

class Messages:
    def __init__(self, language: str = 'en'):
        self.language = language.lower()
        
    def get(self, key: str, **kwargs: Any) -> str:
        """Get message by key and format it with kwargs"""
        message = MESSAGES.get(self.language, {}).get(key, MESSAGES['en'][key])
        return message.format(**kwargs) if kwargs else message

# Message templates for different languages
MESSAGES = {
    'en': {
        # Start messages
        'welcome_new': "👋 Welcome, {name}! You have been registered as a customer.",
        'welcome_back': "👋 Welcome back, {name}!",
        'admin_restriction': "❌ Customer actions are not available in the admin group.",
        'select_language': "Please select your language / Пожалуйста, выберите язык:",
        'language_changed': "✅ Language changed to English",
        
        # Main menu
        'main_menu': "Main Menu:",
        'list_cars_btn': "🚗 List Cars",
        'my_booking_btn': "📄 My Booking",
        'contact_admin_btn': "📞 Contact Admin",
        'change_language_btn': "🌐 Change Language",
        
        # Car listing
        'select_car': "Select a car to view details:",
        'no_cars': "No cars available at the moment.",
        'car_details': """
🚗 {make} {model} ({year})
👤 Dealer: {dealer}
        """,
        
        # Booking
        'booking_success': "✅ Car booked successfully!\nYou can view your booking details in 'My Booking' section.",
        'booking_failed': "❌ Booking failed: {reason}",
        'no_active_booking': "You have no active bookings.",
        'active_booking': "Your active booking:\n\n{booking_info}",
        'return_success': "✅ Car returned successfully!",
        'return_failed': "❌ Return failed: {reason}",
        
        # Navigation
        'back_btn': "🔙 Back",
        'cancel_btn': "❌ Cancel",
        'book_car_btn': "📝 Book This Car",
        'return_car_btn': "✅ Return Car",
        'delete_car': "🗑️ Delete Car",
        'back': "🔙 Back",
        
        # Errors and status
        'db_error': "❌ Error connecting to the database. Please try again later.",
        'operation_cancelled': "✅ Operation cancelled. Returning to main menu.",
        'error_try_again': "❌ An error occurred. Please try again later.",
        'customer_not_found': "❌ Customer not found. Please start over.",
        'car_not_found': "❌ Car not found or no longer available.",
        
        # Contact
        'contact_admin_msg': "For assistance, please contact the admin group.",
    },
    
    'ru': {
        # Start messages
        'welcome_new': "👋 Добро пожаловать, {name}! Вы зарегистрированы как клиент.",
        'welcome_back': "👋 С возвращением, {name}!",
        'admin_restriction': "❌ Действия клиентов недоступны в группе администраторов.",
        'select_language': "Please select your language / Пожалуйста, выберите язык:",
        'language_changed': "✅ Язык изменен на русский",
        
        # Main menu
        'main_menu': "Главное меню:",
        'list_cars_btn': "🚗 Список автомобилей",
        'my_booking_btn': "📄 Моя бронь",
        'contact_admin_btn': "📞 Связаться с админом",
        'change_language_btn': "🌐 Сменить язык",
        
        # Car listing
        'select_car': "Выберите автомобиль для просмотра деталей:",
        'no_cars': "Сейчас нет доступных автомобилей.",
        'car_details': """
🚗 {make} {model} ({year})
👤 Дилер: {dealer}
        """,
        
        # Booking
        'booking_success': "✅ Автомобиль успешно забронирован!\nВы можете посмотреть детали в разделе 'Моя бронь'.",
        'booking_failed': "❌ Ошибка бронирования: {reason}",
        'no_active_booking': "У вас нет активных бронирований.",
        'active_booking': "Ваше активное бронирование:\n\n{booking_info}",
        'return_success': "✅ Автомобиль успешно возвращен!",
        'return_failed': "❌ Ошибка возврата: {reason}",
        
        # Navigation
        'back_btn': "🔙 Назад",
        'cancel_btn': "❌ Отмена",
        'book_car_btn': "📝 Забронировать",
        'return_car_btn': "✅ Вернуть автомобиль",
        'delete_car': "🗑️ Удалить автомобиль",
        'back': "🔙 Назад",
        
        # Errors and status
        'db_error': "❌ Ошибка подключения к базе данных. Попробуйте позже.",
        'operation_cancelled': "✅ Операция отменена. Возврат в главное меню.",
        'error_try_again': "❌ Произошла ошибка. Попробуйте еще раз.",
        'customer_not_found': "❌ Клиент не найден. Начните сначала.",
        'car_not_found': "❌ Автомобиль не найден или недоступен.",
        
        # Contact
        'contact_admin_msg': "Для помощи свяжитесь с группой администраторов.",
    }
} 