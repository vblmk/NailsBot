from bot_config import ADMIN_IDS
from telebot import TeleBot
from telebot.types import Message, CallbackQuery
from bot_config import user_df
from keyboards.inline import initial_keyboard, admin_keyboard
from services.user_services import user_exists_by_id, register_user
from services.db_services import get_user_by_phone, update_user_tgid

def register_start_handler(bot: TeleBot):

    @bot.message_handler(commands=["start"])
    def start(message):
        user_df.pop(message.from_user.id, None)

        tg_id = message.from_user.id
        
        if tg_id in ADMIN_IDS:
            bot.send_message(message.chat.id, "Адмін-панель", reply_markup=admin_keyboard())

        elif user_exists_by_id(tg_id):
            bot.send_message(message.chat.id, "Манікюрна баби галі", reply_markup=initial_keyboard())
        else:
            msg = bot.send_message(
                message.chat.id, 
                "Привіт! Щоб продовжити, вам необхідно авторизуватись.\nНадішліть, будь ласка, свій номер телефону"
            )
            bot.register_next_step_handler(msg, get_phone, msg)

    def get_phone(message, msg: Message):
        if message.contact:
            phone = message.contact.phone_number
        elif message.text:
            phone = message.text.strip()
        else:
            bot.delete_message(chat_id=msg.chat.id, message_id=msg.message_id)
            bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
            
            msg = bot.send_message(message.chat.id, "Будь ласка, надішліть номер телефону")
            bot.register_next_step_handler(msg, get_phone, msg)
            return
        
        user = get_user_by_phone(phone)
        
        if user:
            if user.tg_id is None:
                success = update_user_tgid(phone, message.from_user.id)
                
                if not success:
                    bot.edit_message_text(
                        chat_id=msg.chat.id, 
                        message_id=msg.id, 
                        text="Технічна помилка при авторизації. Будь ласка, спробуйте пізніше або напишіть адміністратору.", 
                    )
                    return

            bot.edit_message_text(
                chat_id=msg.chat.id, 
                message_id=msg.id, 
                text=f"Ви є в списку клієнтів. Вас авторизовано під ім'ям {user.name}.", 
                reply_markup=initial_keyboard()
            )
        else:
            bot.delete_message(chat_id=message.chat.id,
                                message_id=message.message_id)
            
            next_msg = bot.edit_message_text(chat_id=message.chat.id,
                                             message_id=msg.message_id,
                                             text="Як до вас можна звертатись?")
            
            user_data = {'msg': next_msg, 'phone': phone}
            
            bot.register_next_step_handler(next_msg, get_name, user_data)

    def get_name(message, user_data):
        bot.delete_message(chat_id=message.chat.id,
                    message_id=message.message_id)
        
        if not message.text:
            next_msg = bot.send_message(message.chat.id, "Будь ласка, введіть ваше ім'я текстом:")
            
            user_data['msg'] = next_msg
            
            bot.register_next_step_handler(next_msg, get_name, user_data)
            return

        name = message.text.strip()
        phone = user_data['phone']
        tg_id = message.from_user.id

        if register_user(tg_id, name, phone):
            bot.edit_message_text(
                text="Авторизація пройшла успішно!", 
                chat_id=message.chat.id, 
                message_id=user_data['msg'].id,
                reply_markup=initial_keyboard()
            )
        else:
            bot.edit_message_text(
                text="Виникла помилка при авторизації, спробуйте ще раз: /start", 
                chat_id=message.chat.id, 
                message_id=user_data['msg'].id,
                reply_markup=initial_keyboard()
            )
        