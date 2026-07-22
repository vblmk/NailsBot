from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

def initial_keyboard():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("Прайс-лист", callback_data="btn_price"),
        InlineKeyboardButton("Запис", callback_data="btn_appoint"),
        InlineKeyboardButton("Мої записи", callback_data="btn_myVisits")
    )
    return kb
