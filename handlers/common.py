from telebot import TeleBot
from bot_config import user_df
from keyboards.inline import initial_keyboard
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from services.db_services import get_price

def register_common_handlers(bot: TeleBot):
    
    @bot.callback_query_handler(func=lambda call: call.data == "btn_mainMenu")
    def cb_main_menu(call):
        bot.answer_callback_query(call.id)
        
        user_df.pop(call.from_user.id, None)
        bot.edit_message_text(
            chat_id=call.message.chat.id, 
            message_id=call.message.message_id,
            text="Манікюрна баби галі", 
            reply_markup=initial_keyboard()
        )

    @bot.callback_query_handler(func=lambda call: call.data == "btn_price")
    def cd_btn_price(call):
        bot.answer_callback_query(call.id)
        
        user_df.pop(call.from_user.id, None)
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("Запис", callback_data="btn_appoint"))

        bot.edit_message_text(
            chat_id=call.message.chat.id, 
            message_id=call.message.message_id,
            text="Наші послуги:\n" + str(get_price()), 
            reply_markup=kb
        )
    
    @bot.callback_query_handler(func=lambda call: call.data == "btn_cancel")
    def cb_btn_cancel(call):
        bot.answer_callback_query(call.id)
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="Запис скасовано",
            reply_markup=initial_keyboard()
        )