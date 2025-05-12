import unittest
import os
import sys
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

# Import modules to test
import db
from messages import Messages

class TestDatabaseFunctions(unittest.TestCase):
    """Test cases for database functions"""
    
    @patch('db.get_connection')
    def test_get_available_cars(self, mock_get_connection):
        """Test getting available cars"""
        # Mock the database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_get_connection.return_value = mock_conn
        
        # Mock the cursor fetchall method to return test data
        test_cars = [
            (1, 'Toyota', 'Corolla', 2020, 'Test Dealer', 'image_url'),
            (2, 'Honda', 'Civic', 2021, 'Test Dealer', 'image_url')
        ]
        mock_cursor.fetchall.return_value = test_cars
        
        # Call the function
        result = db.get_available_cars()
        
        # Assert the function called the correct SQL
        mock_cursor.execute.assert_called_once()
        self.assertEqual(result, test_cars)
    
    @patch('db.get_connection')
    def test_book_car_success(self, mock_get_connection):
        """Test booking a car successfully"""
        # Mock the database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_get_connection.return_value = mock_conn
        
        # Mock cursor fetchone to return None for active bookings (no existing booking)
        # and True for car availability
        mock_cursor.fetchone.side_effect = [None, (True,), (1,)]
        
        # Call the function
        success, result = db.book_car(1, 1)
        
        # Assert the results
        self.assertTrue(success)
        self.assertEqual(result, 1)  # booking_id
        
        # Verify that commit was called
        mock_conn.commit.assert_called_once()
    
    @patch('db.get_connection')
    def test_book_car_already_has_booking(self, mock_get_connection):
        """Test booking a car when customer already has a booking"""
        # Mock the database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_get_connection.return_value = mock_conn
        
        # Mock cursor fetchone to return an existing booking
        mock_cursor.fetchone.return_value = (1,)
        
        # Call the function
        success, message = db.book_car(1, 1)
        
        # Assert the results
        self.assertFalse(success)
        self.assertEqual(message, "You already have an active booking.")
        
        # Verify commit was not called
        mock_conn.commit.assert_not_called()
    
    @patch('db.get_connection')
    def test_return_car_success(self, mock_get_connection):
        """Test returning a car successfully"""
        # Mock the database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_get_connection.return_value = mock_conn
        
        # Mock cursor fetchone to return a car_id
        mock_cursor.fetchone.return_value = (1,)
        
        # Call the function
        success, message = db.return_car(1)
        
        # Assert the results
        self.assertTrue(success)
        self.assertEqual(message, "Car returned successfully.")
        
        # Verify that commit was called
        mock_conn.commit.assert_called_once()
    
    @patch('db.get_connection')
    def test_return_car_not_found(self, mock_get_connection):
        """Test returning a car that doesn't exist or is not active"""
        # Mock the database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_get_connection.return_value = mock_conn
        
        # Mock cursor fetchone to return None (no booking found)
        mock_cursor.fetchone.return_value = None
        
        # Call the function
        success, message = db.return_car(1)
        
        # Assert the results
        self.assertFalse(success)
        self.assertEqual(message, "Booking not found or already completed.")
        
        # Verify commit was not called
        mock_conn.commit.assert_not_called()

class TestMessages(unittest.TestCase):
    """Test cases for message handling"""
    
    def test_default_language(self):
        """Test that default language is English"""
        msgs = Messages()
        self.assertEqual(msgs.language, 'en')
    
    def test_language_change(self):
        """Test changing language"""
        msgs = Messages('ru')
        self.assertEqual(msgs.language, 'ru')
    
    def test_get_message_en(self):
        """Test getting English messages"""
        msgs = Messages('en')
        self.assertEqual(msgs.get('main_menu'), "Main Menu:")
    
    def test_get_message_ru(self):
        """Test getting Russian messages"""
        msgs = Messages('ru')
        self.assertEqual(msgs.get('main_menu'), "Главное меню:")
    
    def test_message_with_params(self):
        """Test getting message with parameters"""
        msgs = Messages('en')
        result = msgs.get('welcome_new', name="Test User")
        self.assertEqual(result, "👋 Welcome, Test User! You have been registered as a customer.")
    
    def test_fallback_to_english(self):
        """Test fallback to English for unknown language"""
        msgs = Messages('xx')  # Nonexistent language code
        self.assertEqual(msgs.get('main_menu'), "Main Menu:")

if __name__ == '__main__':
    unittest.main() 