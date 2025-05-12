# Car Rental Telegram Bot

A Telegram bot for car rental management built with Python, Aiogram, and PostgreSQL.

## Features

- **Multi-language Support**: English and Russian interfaces
- **Customer Functions**:
  - Browse available cars
  - Book cars
  - View active bookings
  - Return cars
- **Dealer Functions**:
  - Add new cars to the catalog
  - Manage inventory
  - View booking statistics
- **Admin Functions**:
  - View all bookings
  - Manage dealers
  - System monitoring

## Prerequisites

- Python 3.8+
- PostgreSQL database
- Telegram Bot Token (from BotFather)

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/car-rental-bot.git
   cd car-rental-bot
   ```

2. Create a virtual environment and install dependencies:
   ```
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Set up your PostgreSQL database:
   - Create a database named `car_rental`
   - Run the schema script (provided separately)

4. Create a `.env` file with your configuration:
   ```
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   ADMIN_GROUP_ID=your_admin_group_id
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=car_rental
   DB_USER=your_db_username
   DB_PASSWORD=your_db_password
   ```

5. Run the bot:
   ```
   python bot.py
   ```

## Project Structure

- `bot.py` - Main bot code with all handlers
- `db.py` - Database functions and connection management
- `messages.py` - Multilingual message templates
- `requirements.txt` - Python dependencies

## Usage

### Customer Flow

1. Start the bot with `/start`
2. Select your language
3. Browse available cars
4. Book a car
5. Return the car when done

### Dealer Flow

1. Use `/dealer` command to access dealer functions
2. Add new cars with make, model, year, and photos
3. Manage your car inventory
4. View booking statistics for your cars

### Admin Flow

1. Access admin panel in the designated admin group
2. View all active bookings
3. Manage dealers
4. Monitor system operations

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 