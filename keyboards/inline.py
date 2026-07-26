from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

def initial_keyboard():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("Прайс-лист", callback_data="btn_price"),
        InlineKeyboardButton("Запис", callback_data="btn_appoint"),
        InlineKeyboardButton("Мої записи", callback_data="btn_myVisits")
    )
    return kb

def admin_keyboard():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("Додати послугу", callback_data="btn_addService"),
           InlineKeyboardButton("Розклад", callback_data="btn_schedule"),
           InlineKeyboardButton("Запис вручну", callback_data="btn_manualAppoint"))
    
    return kb