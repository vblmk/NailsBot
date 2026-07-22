from keyboards.inline import initial_keyboard
from telebot import TeleBot
from services.db_services import get_user_visits

def register_visits_handlers(bot: TeleBot):
    @bot.message_handler(commands=["myvisits"])
    def my_visits(message):
        tg_id = message.from_user.id
        
        text_to_send = ""
        res_text = get_user_visits(tg_id)
        
        if res_text is None:
            text_to_send = "Сталась технічна помилка, спробуйте пізніше."
        elif res_text == "":
            text_to_send = "Не знайдено активних записів за цим користувачем."
        else:
            text_to_send = "Ваші записи:" + res_text    
            
        bot.send_message(chat_id=message.chat.id,
                         text = text_to_send,
                         reply_markup=initial_keyboard())
            
    @bot.callback_query_handler(func=lambda call: call.data == "btn_myVisits")
    def cb_btn_myVisits(call):
        bot.answer_callback_query(call.id)
        
        tg_id = call.from_user.id
        
        res_text = get_user_visits(tg_id)
        text_to_send = ""
        
        if res_text is None:    
            text_to_send = "Сталась технічна помилка, спробуйте пізніше."
        elif res_text == "":
            text_to_send = "Не знайдено активних записів за цим користувачем."
        else:
            text_to_send = "Ваші записи:" + res_text  
        
        bot.edit_message_text(chat_id=call.message.chat.id,
                              message_id=call.message.message_id,
                              text = text_to_send,
                              reply_markup=initial_keyboard())