from bot_config import bot
from handlers.start import register_start_handler
from handlers.booking import register_booking_handlers
from handlers.admin import register_admin_handlers
from handlers.common import register_common_handlers
from handlers.visits import register_visits_handlers

def main():
    print("starting...")

    register_start_handler(bot)
    register_admin_handlers(bot)
    register_booking_handlers(bot)
    register_visits_handlers(bot)
    register_common_handlers(bot)
    
    print("all handlers registered, listening to telegram...")
    
    bot.infinity_polling(timeout=10, long_polling_timeout=5)

if __name__ == "__main__":
    main()