from bot_config import user_df
from telebot import TeleBot
from telebot.types import Message, CallbackQuery
from utils.decorators import is_admin
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from services.schedule_services import appoint
from keyboards.pagination import create_pagination_kb_date_schedule
from keyboards.inline import admin_keyboard
from services.db_services import get_schedule_info, get_service_and_slot_info, add_service_db
from utils.formatters import is_float, format_duration_to_db, format_duration_from_db

serv_data = {}

def register_admin_handlers(bot: TeleBot):

    @bot.message_handler(commands=["schedule"])
    @is_admin
    def schedule(message, date=None):
        if date is None:
            date = datetime.now().date()
        user_df.pop(message.from_user.id, None)
        
        res_text = get_schedule_info(date, bot)
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("Вибрати іншу дату", callback_data="pagedate_sched_0"))
        
        date_str = date.strftime("%d-%m-%Y") if hasattr(date, 'strftime') else str(date)
        bot.send_message(message.chat.id, f"📅 Розклад на {date_str}:\n\n{res_text}", reply_markup=kb)
        
    @bot.message_handler(commands=["appoint"])
    @is_admin
    def manual_appoint(message):
        msg = bot.send_message(message.chat.id, "Надішліть дані для запису клієнта у такому форматі:\nДД-ММ-РРРР,ГГ:ХВ,ім'я,телефон,послуга")
        bot.register_next_step_handler(msg, handle_manual_appointment)

    def handle_manual_appointment(msg):
        try:
            parts = [p.strip() for p in msg.text.split(",")]
            if len(parts) != 5:
                raise ValueError("Невірний формат даних.")

            date_str, time_str, name, phone, service_name = parts
            date_obj = datetime.strptime(date_str, "%d-%m-%Y")
            date_reformatted = date_obj.strftime("%Y-%m-%d")
            time_obj = datetime.strptime(time_str, "%H:%M").time()
            
            res = get_service_and_slot_info(service_name, date_reformatted, time_obj)
            
            if res == "No service":
                bot.send_message(msg.chat.id, f"❌ Не знайдено послуги з назвою '{service_name}'. Спробуйте знову: /appoint")
                return
            elif res == "No slot":
                bot.send_message(msg.chat.id, f"❌ Не знайдено вільного слоту на {date_str} о {time_str}. Спробуйте знову: /appoint")
                return
            
            service_id, service_name, slot_id = res
            
            success = appoint(slot_id, name, phone, service_id)

            if success:
                bot.send_message(msg.chat.id, f"<b>✅ Запис створено!</b>\n\n👤 {name}\n📅 Дата: {date_str}\n⏰ Час: {time_str}\n💅 {service_name}", parse_mode='HTML')
            else:
                bot.send_message(msg.chat.id, "❌ Помилка при створенні запису. Спробуйте знову: /appoint")

        except ValueError:
            bot.send_message(msg.chat.id, "⚠️ Помилка у форматі даних.\nСпробуйте знову: /appoint")
        except Exception as e:
            print(f"Глобальна помилка ручного запису: {e}")
            bot.send_message(msg.chat.id, "💥 Сталася технічна помилка під час обробки даних. Спробуйте знову: /appoint")
            
    @bot.callback_query_handler(func=lambda call: call.data == "btn_addService")
    @is_admin
    def handle_add_service_name(call: CallbackQuery):
        bot.answer_callback_query(call.id)
        serv_data[call.from_user.id] = {}
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("Головне меню", callback_data="btn_mainMenu"))
        
        msg = bot.edit_message_text(chat_id=call.message.chat.id,
                                    message_id=call.message.message_id,
                                    text="ДОДАВАННЯ НОВОЇ ПОСЛУГИ\n\nНадішліть назву послуги:",
                                    reply_markup=kb)
        
        serv_data[call.from_user.id]['msg'] = msg
        
        bot.register_next_step_handler(msg, handle_add_service_price, kb)
    
    def handle_add_service_price(message: Message, kb: InlineKeyboardMarkup):
        bot.delete_message(chat_id = message.chat.id,
                           message_id=message.message_id)
        
        serv_data[message.from_user.id]['name'] = message.text.strip()
        msg = bot.edit_message_text(chat_id = message.chat.id,
                                    message_id=serv_data[message.from_user.id]['msg'].id, 
                                    text=f"ДОДАВАННЯ НОВОЇ ПОСЛУГИ\n\nНазва: {serv_data[message.from_user.id]['name']}\n\nНадішліть ціну послуги:",
                                    reply_markup=kb)
        
        bot.register_next_step_handler(msg, handle_add_service_duration, kb)
        
    def handle_add_service_duration(message: Message, kb):
        bot.delete_message(chat_id = message.chat.id,
                           message_id=message.message_id)
        
        text = message.text
        if is_float(text):
            serv_data[message.from_user.id]['price'] = message.text 
        else:
            bot.edit_message_text(chat_id = message.chat.id,
                                    message_id=serv_data[message.from_user.id]['msg'].id, 
                                    text="Помилка у форматі даних: ціна має бути числом.",
                                    reply_markup=admin_keyboard())
            return
        
        msg = bot.edit_message_text(chat_id = message.chat.id,
                                    message_id=serv_data[message.from_user.id]['msg'].id, 
                                    text=f"ДОДАВАННЯ НОВОЇ ПОСЛУГИ\n\nНазва: {serv_data[message.from_user.id]['name']}\nЦіна: {serv_data[message.from_user.id]['price']}\n\nНадішліть тривалість послуги (наприклад: 1год 30хв):",
                                    reply_markup=kb)
        
        bot.register_next_step_handler(msg, handle_add_service)
        
    def handle_add_service(message):
        bot.delete_message(chat_id = message.chat.id,
                           message_id=message.message_id)
        
        name, price, duration = serv_data[message.from_user.id]['name'], serv_data[message.from_user.id]['price'], format_duration_to_db(message.text)
        res = add_service_db(name, price, duration)
        
        if res == "wrong interval format":
            bot.edit_message_text(chat_id = message.chat.id,
                                    message_id=serv_data[message.from_user.id]['msg'].id, 
                                    text="Помилка додавання нової послуги: неправильний формат тривалості\nПравильний формат: 1год 30хв",
                                    reply_markup=admin_keyboard())
        elif res is None:
            bot.edit_message_text(chat_id = message.chat.id,
                                    message_id=serv_data[message.from_user.id]['msg'].id, 
                                    text="Технічна помилка при спробі додати нову послугу. Зверніться до адміністратора або спробуйте пізніше.",
                                    reply_markup=admin_keyboard())
        elif res > 0:
            bot.edit_message_text(chat_id = message.chat.id,
                                    message_id=serv_data[message.from_user.id]['msg'].id, 
                                    text=f"Послугу додано успішно!\n\nНазва: {name}\nЦіна: {price}\nТривалість: {format_duration_from_db(duration)}",
                                    reply_markup=admin_keyboard())
        
    @bot.callback_query_handler(func=lambda call: call.data.startswith("date_sched_"))
    @is_admin
    def handle_date_sched_selection(call):
        bot.answer_callback_query(call.id)

        date_str = call.data.split("date_sched_")[1]

        try:
            selected_date = datetime.strptime(date_str, "%d-%m-%Y").date()
        except ValueError:
            selected_date = datetime.now().date()

        res_text = get_schedule_info(selected_date, bot)
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("Вибрати іншу дату", callback_data="pagedate_sched_0"))
        
        date_str_formatted = selected_date.strftime("%d-%m-%Y")
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"📅 Розклад на {date_str_formatted}:\n\n{res_text}",
            reply_markup=kb
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("pagedate_sched_"))
    @is_admin
    def handle_sched_date_pagination(call):
        bot.answer_callback_query(call.id)
        
        parts = call.data.split("_")
        page = int(parts[2])

        kb = create_pagination_kb_date_schedule(page)
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=kb)
