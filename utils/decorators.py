from typing import Callable
from functools import wraps
from bot_config import ADMIN_IDS

def is_admin(func: Callable):
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        user_id = message.from_user.id

        if user_id not in ADMIN_IDS:
            return None

        return func(message, *args, **kwargs)

    return wrapper

def safe_db_query(func: Callable):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)   
        
        except Exception as e:
            print(f"func {func.__name__} exception {e}")
            return None
    
    return wrapper