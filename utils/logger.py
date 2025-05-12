import os
import logging
import logging.handlers
from datetime import datetime

def setup_logger(log_level=None):
    """Set up application logging with proper formatting and file rotation
    
    Args:
        log_level: Override log level from environment (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
    Returns:
        logging.Logger: Configured logger instance
    """
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Get log level from environment or use default
    if not log_level:
        log_level_str = os.getenv('LOG_LEVEL', 'INFO')
        # Clean up the log level string - take only the first word
        log_level = log_level_str.split()[0].strip().upper()
    
    # Validate log level
    valid_levels = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    
    if log_level not in valid_levels:
        print(f"Invalid log level: {log_level}, falling back to INFO")
        numeric_level = logging.INFO
    else:
        numeric_level = valid_levels[log_level]
    
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(numeric_level)
    logger.handlers = []  # Remove any existing handlers
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Create console handler for log output to stdout
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(simple_formatter)
    console_handler.setLevel(numeric_level)
    logger.addHandler(console_handler)
    
    # Create rotating file handler for persistent logs
    log_filename = os.path.join('logs', f'car_rental_{datetime.now().strftime("%Y-%m-%d")}.log')
    file_handler = logging.handlers.RotatingFileHandler(
        log_filename,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(detailed_formatter)
    file_handler.setLevel(numeric_level)
    logger.addHandler(file_handler)
    
    # Log startup message
    logger.info(f"Logger initialized with level {log_level}")
    
    return logger

# Log critical errors to a separate file
def log_critical_error(message, exception=None):
    """Log critical errors to a separate file for monitoring
    
    Args:
        message: Error message
        exception: Exception object if available
    """
    os.makedirs('logs', exist_ok=True)
    
    critical_logger = logging.getLogger('critical')
    critical_logger.setLevel(logging.CRITICAL)
    critical_logger.handlers = []  # Remove any existing handlers
    
    # Create critical error file handler
    critical_file = os.path.join('logs', 'critical_errors.log')
    critical_handler = logging.FileHandler(critical_file)
    critical_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(message)s\nException: %(exc_info)s\n---')
    )
    critical_logger.addHandler(critical_handler)
    
    # Log the error
    if exception:
        critical_logger.critical(message, exc_info=exception)
    else:
        critical_logger.critical(message) 