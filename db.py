import os
import re
import psycopg2
import logging
from psycopg2 import OperationalError, InterfaceError
from functools import wraps
from time import sleep
from dotenv import load_dotenv

# Import configuration if available
try:
    from config.config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, CONNECT_TIMEOUT
except ImportError:
    # Fallback to environment variables if config module not available
    load_dotenv()
    
    # Database configuration
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_NAME = os.getenv('DB_NAME', 'car_rental')
    DB_USER = os.getenv('DB_USER', 'postgres')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    CONNECT_TIMEOUT = 5  # seconds

# Get the logger from the main module
logger = logging.getLogger(__name__)

# Connection settings
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds

def retry_on_db_error(func):
    """Decorator to retry database operations on connection errors"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        retries = 0
        last_error = None
        
        while retries < MAX_RETRIES:
            try:
                return func(*args, **kwargs)
            except (OperationalError, InterfaceError) as e:
                last_error = e
                retries += 1
                if retries < MAX_RETRIES:
                    logger.warning(f"Database operation failed, attempt {retries} of {MAX_RETRIES}: {e}")
                    sleep(RETRY_DELAY)
                continue
            except Exception as e:
                logger.error(f"Unexpected database error in {func.__name__}: {e}")
                raise
        
        logger.error(f"Database operation failed after {MAX_RETRIES} attempts: {last_error}")
        raise last_error
    
    return wrapper

def get_connection():
    """Get a database connection with timeout and encoding settings"""
    try:
        logger.info("Attempting database connection")
        
        # Make sure we have valid values
        host = DB_HOST or 'localhost'
        port = DB_PORT or '5432'
        dbname = DB_NAME or 'car_rental'
        user = DB_USER or 'postgres'
        password = DB_PASSWORD or ''
        
        # Log connection attempt (without password)
        logger.info(f"Connecting to database {dbname} on {host}:{port} as {user}")
        
        # Connect using direct parameters
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password,
            client_encoding='UTF8',
            connect_timeout=CONNECT_TIMEOUT
        )
        
        # Verify encoding after connection
        with conn.cursor() as cur:
            cur.execute('SHOW client_encoding')
            client_encoding = cur.fetchone()[0]
            cur.execute('SHOW server_encoding')
            server_encoding = cur.fetchone()[0]
            logger.info(f"Database connected - Client: {client_encoding}, Server: {server_encoding}")
        
        return conn
    except OperationalError as e:
        logger.error(f"Database connection failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during database connection: {e}")
        raise

def get_all_dealers():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT id, telegram_id, name FROM dealers')
            return cur.fetchall()

# Car listing functions
def get_available_cars(limit=10, offset=0):
    """Get a list of available cars"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT c.id, c.make, c.model, c.year, d.name as dealer_name, img.image_url 
                    FROM cars c 
                    JOIN dealers d ON c.dealer_id = d.id
                    LEFT JOIN (
                        SELECT car_id, image_url 
                        FROM car_images 
                        WHERE is_primary = true
                    ) img ON c.id = img.car_id
                    WHERE c.available = true
                    ORDER BY c.id
                    LIMIT %s OFFSET %s
                ''', (limit, offset))
                return cur.fetchall()
    except psycopg2.Error as e:
        logger.error(f"Database error in get_available_cars: {e.pgerror if hasattr(e, 'pgerror') else str(e)}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in get_available_cars: {str(e)}")
        return []

def get_car_details(car_id):
    """Get detailed information about a specific car"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Get car details
                cur.execute('''
                    SELECT c.id, c.make, c.model, c.year, d.name as dealer_name, d.telegram_id as dealer_telegram_id
                    FROM cars c 
                    JOIN dealers d ON c.dealer_id = d.id
                    WHERE c.id = %s
                ''', (car_id,))
                car = cur.fetchone()
                
                if not car:
                    return None
                
                # Get car images
                cur.execute('SELECT image_url, is_primary FROM car_images WHERE car_id = %s', (car_id,))
                images = cur.fetchall()
                
                return {
                    'car': car,
                    'images': images
                }
    except Exception as e:
        logger.error(f"Error in get_car_details: {e}")
        return None

def get_customer_id(telegram_id):
    """Get customer ID from telegram ID"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT id FROM customers WHERE telegram_id = %s', (telegram_id,))
                result = cur.fetchone()
                return result[0] if result else None
    except Exception as e:
        logger.error(f"Error in get_customer_id: {e}")
        return None

def get_active_booking(customer_id):
    """Get active booking for a customer"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT b.id, b.car_id, b.start_date, b.end_date, c.make, c.model, c.year
                    FROM bookings b
                    JOIN cars c ON b.car_id = c.id
                    WHERE b.customer_id = %s AND b.active = true
                ''', (customer_id,))
                return cur.fetchone()
    except Exception as e:
        logger.error(f"Error in get_active_booking: {e}")
        return None

def book_car(customer_id, car_id):
    """Book a car for a customer"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Check if customer already has an active booking
                cur.execute('SELECT id FROM bookings WHERE customer_id = %s AND active = true', (customer_id,))
                if cur.fetchone():
                    return False, "You already have an active booking."
                
                # Check if car is available
                cur.execute('SELECT available FROM cars WHERE id = %s', (car_id,))
                result = cur.fetchone()
                if not result:
                    return False, "This car does not exist in our database."
                if not result[0]:
                    return False, "This car is not available for booking. It may have been recently booked."
                
                # Create booking
                cur.execute('''
                    INSERT INTO bookings (customer_id, car_id, start_date, active)
                    VALUES (%s, %s, NOW(), true)
                    RETURNING id
                ''', (customer_id, car_id))
                booking_id = cur.fetchone()[0]
                
                # Update car availability
                cur.execute('UPDATE cars SET available = false WHERE id = %s', (car_id,))
                
                conn.commit()
                return True, booking_id
    except psycopg2.IntegrityError as e:
        logger.error(f"Integrity constraint violation in book_car: {e.pgerror if hasattr(e, 'pgerror') else str(e)}")
        return False, "A database constraint was violated. The booking could not be completed."
    except psycopg2.Error as e:
        logger.error(f"Database error in book_car: {e.pgerror if hasattr(e, 'pgerror') else str(e)}")
        return False, "A database error occurred. Please try again later."
    except Exception as e:
        logger.error(f"Unexpected error in book_car: {str(e)}")
        return False, "An unexpected error occurred. Please contact support."

def return_car(booking_id):
    """Return a car (end booking)"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Get car ID from booking
                cur.execute('SELECT car_id FROM bookings WHERE id = %s AND active = true', (booking_id,))
                result = cur.fetchone()
                if not result:
                    return False, "Booking not found or already completed."
                
                car_id = result[0]
                
                # Update booking
                cur.execute('''
                    UPDATE bookings 
                    SET active = false, end_date = NOW()
                    WHERE id = %s
                ''', (booking_id,))
                
                # Update car availability
                cur.execute('UPDATE cars SET available = true WHERE id = %s', (car_id,))
                
                conn.commit()
                return True, "Car returned successfully."
    except psycopg2.Error as e:
        logger.error(f"Database error in return_car: {e.pgerror if hasattr(e, 'pgerror') else str(e)}")
        return False, "A database error occurred while processing your return. Please try again later."
    except Exception as e:
        logger.error(f"Unexpected error in return_car: {str(e)}")
        return False, "An unexpected error occurred. Please contact support."

def is_admin_in_group(telegram_id, group_id):
    """Check if admin group is configured and valid"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT id FROM admin_group WHERE group_id = %s', (group_id,))
                return bool(cur.fetchone())
    except Exception as e:
        logger.error(f"Error in is_admin_in_group: {e}")
        return False

def get_all_bookings(active_only=False, limit=20):
    """Get all bookings (for admin)"""
    try:
        logger.info("Getting all bookings from database")
        with get_connection() as conn:
            with conn.cursor() as cur:
                query = '''
                    SELECT 
                        b.id,
                        b.start_date,
                        b.end_date,
                        b.active,
                        c.name as customer_name,
                        c.telegram_id as customer_telegram,
                        cars.make,
                        cars.model,
                        cars.year
                    FROM bookings b
                    JOIN customers c ON b.customer_id = c.id
                    JOIN cars ON b.car_id = cars.id
                    ORDER BY b.start_date DESC
                '''
                
                logger.info(f"Executing query: {query}")
                cur.execute(query)
                bookings = cur.fetchall()
                logger.info(f"Found {len(bookings)} bookings")
                return bookings
    except Exception as e:
        logger.error(f"Error in get_all_bookings: {e}")
        return []

def admin_delete_booking(booking_id):
    """Delete a booking and update car availability if needed"""
    try:
        logger.info(f"Attempting to delete booking {booking_id}")
        with get_connection() as conn:
            with conn.cursor() as cur:
                # First get the car_id and active status
                cur.execute('''
                    SELECT car_id, active 
                    FROM bookings 
                    WHERE id = %s
                ''', (booking_id,))
                result = cur.fetchone()
                
                if not result:
                    logger.warning(f"Booking {booking_id} not found")
                    return False, "Booking not found."
                
                car_id, is_active = result
                logger.info(f"Found booking {booking_id}: car_id={car_id}, active={is_active}")
                
                # If booking was active, make car available again
                if is_active:
                    logger.info(f"Making car {car_id} available again")
                    cur.execute('UPDATE cars SET available = true WHERE id = %s', (car_id,))
                
                # Delete the booking
                cur.execute('DELETE FROM bookings WHERE id = %s', (booking_id,))
                logger.info(f"Deleted booking {booking_id}")
                
                conn.commit()
                return True, "Booking deleted successfully."
                
    except Exception as e:
        logger.error(f"Error in admin_delete_booking: {e}")
        return False, f"Database error: {e}"

@retry_on_db_error
def register_customer(telegram_id: int, name: str) -> bool:
    """Register a new customer or return False if already exists
    
    Args:
        telegram_id: Telegram user ID
        name: Customer's full name
        
    Returns:
        True if new customer registered
        False if customer already exists
        None if error occurred
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Check if customer exists
                cur.execute('SELECT id FROM customers WHERE telegram_id = %s', (telegram_id,))
                if cur.fetchone():
                    return False
                
                # Create new customer
                cur.execute('''
                    INSERT INTO customers (telegram_id, name, registration_date)
                    VALUES (%s, %s, NOW())
                ''', (telegram_id, name))
                
                conn.commit()
                return True
                
    except Exception as e:
        logger.error(f"Error in register_customer: {e}")
        return None

def get_pending_bookings(limit=20):
    """Get pending bookings (for admin)"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT 
                        b.id,
                        b.start_date,
                        b.end_date,
                        b.active,
                        c.name as customer_name,
                        c.telegram_id as customer_telegram,
                        cars.make,
                        cars.model,
                        cars.year
                    FROM bookings b
                    JOIN customers c ON b.customer_id = c.id
                    JOIN cars ON b.car_id = cars.id
                    WHERE b.pending = true
                    ORDER BY b.start_date DESC
                    LIMIT %s
                ''', (limit,))
                return cur.fetchall()
    except Exception as e:
        logger.error(f"Error in get_pending_bookings: {e}")
        return []

def get_active_bookings(limit=20):
    """Get active bookings (for admin)"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT 
                        b.id,
                        b.start_date,
                        b.end_date,
                        b.active,
                        c.name as customer_name,
                        c.telegram_id as customer_telegram,
                        cars.make,
                        cars.model,
                        cars.year
                    FROM bookings b
                    JOIN customers c ON b.customer_id = c.id
                    JOIN cars ON b.car_id = cars.id
                    WHERE b.active = true AND b.pending = false
                    ORDER BY b.start_date DESC
                    LIMIT %s
                ''', (limit,))
                return cur.fetchall()
    except Exception as e:
        logger.error(f"Error in get_active_bookings: {e}")
        return []

def approve_booking(booking_id):
    """Approve a pending booking"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Check if booking exists and is pending
                cur.execute('SELECT id, car_id FROM bookings WHERE id = %s AND pending = true', (booking_id,))
                result = cur.fetchone()
                
                if not result:
                    return False, "Booking not found or already processed."
                
                # Update booking status
                cur.execute('''
                    UPDATE bookings 
                    SET pending = false
                    WHERE id = %s
                ''', (booking_id,))
                
                # Set car as unavailable
                cur.execute('UPDATE cars SET available = false WHERE id = %s', (result[1],))
                
                conn.commit()
                return True, "Booking approved successfully."
    except Exception as e:
        logger.error(f"Error in approve_booking: {e}")
        return False, f"Database error: {e}"

def reject_booking(booking_id):
    """Reject a pending booking"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Check if booking exists and is pending
                cur.execute('SELECT id FROM bookings WHERE id = %s AND pending = true', (booking_id,))
                if not cur.fetchone():
                    return False, "Booking not found or already processed."
                
                # Delete the booking
                cur.execute('DELETE FROM bookings WHERE id = %s', (booking_id,))
                
                conn.commit()
                return True, "Booking rejected successfully."
    except Exception as e:
        logger.error(f"Error in reject_booking: {e}")
        return False, f"Database error: {e}"

def add_dealer(telegram_id, name):
    """Add a new dealer"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Check if dealer with this Telegram ID already exists
                cur.execute('SELECT id FROM dealers WHERE telegram_id = %s', (telegram_id,))
                if cur.fetchone():
                    return False, "Dealer with this Telegram ID already exists."
                
                # Insert new dealer
                cur.execute('''
                    INSERT INTO dealers (telegram_id, name)
                    VALUES (%s, %s)
                    RETURNING id
                ''', (telegram_id, name))
                
                dealer_id = cur.fetchone()[0]
                
                conn.commit()
                return True, dealer_id
    except Exception as e:
        logger.error(f"Error in add_dealer: {e}")
        return False, f"Database error: {e}"

def delete_dealer(dealer_id):
    """Delete a dealer and all their cars"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Check if dealer exists
                cur.execute('SELECT id FROM dealers WHERE id = %s', (dealer_id,))
                if not cur.fetchone():
                    return False, "Dealer not found."
                
                # Get all cars for this dealer
                cur.execute('SELECT id FROM cars WHERE dealer_id = %s', (dealer_id,))
                car_ids = [row[0] for row in cur.fetchall()]
                
                # Delete all car images
                if car_ids:
                    cur.execute('DELETE FROM car_images WHERE car_id = ANY(%s)', (car_ids,))
                
                # Delete all cars
                cur.execute('DELETE FROM cars WHERE dealer_id = %s', (dealer_id,))
                
                # Delete dealer
                cur.execute('DELETE FROM dealers WHERE id = %s', (dealer_id,))
                
                conn.commit()
                return True, "Dealer and all their cars deleted successfully."
    except Exception as e:
        logger.error(f"Error in delete_dealer: {e}")
        return False, f"Database error: {e}"

def is_dealer(user_id):
    """Check if user is a registered dealer"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT id FROM dealers WHERE telegram_id = %s', (user_id,))
                return bool(cur.fetchone())
    except Exception as e:
        logger.error(f"Error in is_dealer: {e}")
        return False

def get_dealer_id(user_id):
    """Get dealer ID from user ID"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT id FROM dealers WHERE telegram_id = %s', (user_id,))
                result = cur.fetchone()
                return result[0] if result else None
    except Exception as e:
        logger.error(f"Error in get_dealer_id: {e}")
        return None

def get_dealer_cars(dealer_id):
    """Get all cars for a dealer"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT 
                        id, 
                        make, 
                        model, 
                        year, 
                        available
                    FROM cars 
                    WHERE dealer_id = %s
                    ORDER BY make, model
                ''', (dealer_id,))
                return cur.fetchall()
    except Exception as e:
        logger.error(f"Error in get_dealer_cars: {e}")
        return []

def get_dealer_stats(dealer_id):
    """Get booking statistics for a dealer"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Get total cars
                cur.execute('SELECT COUNT(*) FROM cars WHERE dealer_id = %s', (dealer_id,))
                total_cars = cur.fetchone()[0]
                
                # Get total bookings
                cur.execute('''
                    SELECT COUNT(*) 
                    FROM bookings b
                    JOIN cars c ON b.car_id = c.id
                    WHERE c.dealer_id = %s
                ''', (dealer_id,))
                total_bookings = cur.fetchone()[0]
                
                # Get active bookings
                cur.execute('''
                    SELECT COUNT(*) 
                    FROM bookings b
                    JOIN cars c ON b.car_id = c.id
                    WHERE c.dealer_id = %s AND b.active = true
                ''', (dealer_id,))
                active_bookings = cur.fetchone()[0]
                
                # Get completed bookings
                cur.execute('''
                    SELECT COUNT(*) 
                    FROM bookings b
                    JOIN cars c ON b.car_id = c.id
                    WHERE c.dealer_id = %s AND b.active = false
                ''', (dealer_id,))
                completed_bookings = cur.fetchone()[0]
                
                # Get statistics for each car
                cur.execute('''
                    SELECT 
                        c.id,
                        c.make,
                        c.model,
                        c.year,
                        COUNT(b.id) as booking_count
                    FROM cars c
                    LEFT JOIN bookings b ON c.id = b.car_id
                    WHERE c.dealer_id = %s
                    GROUP BY c.id, c.make, c.model, c.year
                    ORDER BY booking_count DESC
                ''', (dealer_id,))
                
                car_stats = []
                for row in cur.fetchall():
                    car_stats.append({
                        'id': row[0],
                        'make': row[1],
                        'model': row[2],
                        'year': row[3],
                        'bookings': row[4]
                    })
                
                return {
                    'total_cars': total_cars,
                    'total_bookings': total_bookings,
                    'active_bookings': active_bookings,
                    'completed_bookings': completed_bookings,
                    'car_stats': car_stats
                }
    except Exception as e:
        logger.error(f"Error in get_dealer_stats: {e}")
        return None

def add_dealer_car(dealer_id, make, model, year, photo_id):
    """Add a new car for a dealer"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Insert car
                cur.execute('''
                    INSERT INTO cars (dealer_id, make, model, year, available)
                    VALUES (%s, %s, %s, %s, true)
                    RETURNING id
                ''', (dealer_id, make, model, year))
                
                car_id = cur.fetchone()[0]
                
                # Insert car image
                cur.execute('''
                    INSERT INTO car_images (car_id, image_url, is_primary)
                    VALUES (%s, %s, true)
                ''', (car_id, photo_id))
                
                conn.commit()
                return True, car_id
    except Exception as e:
        logger.error(f"Error in add_dealer_car: {e}")
        return False, f"Database error: {e}"

def delete_dealer_car(dealer_id, car_id):
    """Delete a car for a dealer"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Check if car exists and belongs to this dealer
                cur.execute('SELECT id FROM cars WHERE id = %s AND dealer_id = %s', (car_id, dealer_id))
                if not cur.fetchone():
                    return False, "Car not found or doesn't belong to you."
                
                # Check if car is currently booked
                cur.execute('''
                    SELECT id 
                    FROM bookings 
                    WHERE car_id = %s AND active = true
                ''', (car_id,))
                
                if cur.fetchone():
                    return False, "Cannot delete a car that is currently booked."
                
                # Delete car images
                cur.execute('DELETE FROM car_images WHERE car_id = %s', (car_id,))
                
                # Delete car
                cur.execute('DELETE FROM cars WHERE id = %s', (car_id,))
                
                conn.commit()
                return True, "Car deleted successfully."
    except Exception as e:
        logger.error(f"Error in delete_dealer_car: {e}")
        return False, f"Database error: {e}"

def update_car_image(car_id, image_url, is_primary=True):
    """Update or add a car image with a valid Telegram file ID
    
    Args:
        car_id: ID of the car
        image_url: Telegram file ID for the image
        is_primary: Whether this is the primary image
        
    Returns:
        tuple: (success, result)
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Check if car exists
                cur.execute('SELECT id FROM cars WHERE id = %s', (car_id,))
                if not cur.fetchone():
                    return False, "Car not found"
                
                # If is_primary is True, set all other images for this car to not primary
                if is_primary:
                    cur.execute('UPDATE car_images SET is_primary = FALSE WHERE car_id = %s', (car_id,))
                
                # Check if image already exists
                cur.execute('SELECT id FROM car_images WHERE car_id = %s AND is_primary = %s', 
                           (car_id, is_primary))
                existing_image = cur.fetchone()
                
                if existing_image:
                    # Update existing image
                    cur.execute('''
                        UPDATE car_images 
                        SET image_url = %s, is_primary = %s
                        WHERE id = %s
                    ''', (image_url, is_primary, existing_image[0]))
                    result = f"Updated image #{existing_image[0]}"
                else:
                    # Insert new image
                    cur.execute('''
                        INSERT INTO car_images (car_id, image_url, is_primary)
                        VALUES (%s, %s, %s)
                        RETURNING id
                    ''', (car_id, image_url, is_primary))
                    image_id = cur.fetchone()[0]
                    result = f"Added new image #{image_id}"
                
                conn.commit()
                return True, result
    except Exception as e:
        logger.error(f"Error in update_car_image: {e}")
        return False, f"Database error: {str(e)}"

def refresh_car_image(car_id, new_file_id):
    """Update a car's image with a new Telegram file ID when invalid ID error occurs
    
    Args:
        car_id: ID of the car to update
        new_file_id: New valid Telegram file ID
        
    Returns:
        tuple: (success, message)
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Check if car exists
                cur.execute('SELECT id FROM cars WHERE id = %s', (car_id,))
                if not cur.fetchone():
                    return False, "Car not found"
                
                # Find the primary image for this car 
                cur.execute('SELECT id FROM car_images WHERE car_id = %s AND is_primary = TRUE', (car_id,))
                image = cur.fetchone()
                
                if image:
                    # Update the existing primary image
                    cur.execute('''
                        UPDATE car_images 
                        SET image_url = %s
                        WHERE id = %s
                    ''', (new_file_id, image[0]))
                    result = f"Updated primary image for car #{car_id}"
                else:
                    # Create a new primary image
                    cur.execute('''
                        INSERT INTO car_images (car_id, image_url, is_primary)
                        VALUES (%s, %s, TRUE)
                    ''', (car_id, new_file_id))
                    result = f"Created new primary image for car #{car_id}"
                
                conn.commit()
                return True, result
    except Exception as e:
        logger.error(f"Error in refresh_car_image: {e}")
        return False, f"Database error: {str(e)}"