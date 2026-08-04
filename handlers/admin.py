from bot_config import user_df
from telebot import TeleBot
from telebot.types import Message, CallbackQuery
from utils.decorators import is_admin
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from services.schedule_services import appoint
from keyboards.pagination import create_pagination_kb_date_schedule, create_pagination_kb_services_del
from keyboards.inline import admin_keyboard
from services.db_services import get_schedule_info, get_service_and_slot_info, add_service_db, delete_service, get_serv_name_by_id, get_serv_id_by_name, check_slot
from utils.formatters import is_float, format_duration_to_db, format_duration_from_db

serv_data = {}
appoint_data = {}

def register_admin_handlers(bot: TeleBot):

    @bot.message_handler(commands=["schedule"])
    @is_admin
    def schedule(message: Message, date=None):
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
    def handle_manual_appoint_date(message: Message):
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("Головне меню", callback_data="btn_mainMenu"))
        appoint_data[message.from_user.id] = {}
        
        msg = bot.send_message(message.chat.id, "СТВОРЕННЯ НОВОГО ЗАПИСУ\n\nНадішліть дату (ДД-ММ-РРРР):", reply_markup=kb)
        
        bot.register_next_step_handler(msg, handle_manual_appoint_time, msg, kb)
        
    def handle_manual_appoint_time(message: Message, msg_to_edit: Message, kb: InlineKeyboardMarkup):
        bot.delete_message(chat_id=message.chat.id, 
                            message_id=message.message_id)
        try:
            appoint_data[message.from_user.id]['date'] = datetime.strptime(message.text.replace(".", "-"), "%d-%m-%Y").strftime("%Y-%m-%d")
        except ValueError:
            msg = bot.edit_message_text(chat_id=msg_to_edit.chat.id,
                        message_id=msg_to_edit.message_id,
                        text="Невірний формат дати",
                        reply_markup=admin_keyboard())
        appoint_data[message.from_user.id]['date_str'] = message.text
        
        msg = bot.edit_message_text(chat_id=msg_to_edit.chat.id,
                              message_id=msg_to_edit.message_id,
                              text=f"СТВОРЕННЯ НОВОГО ЗАПИСУ\n\nДата: {message.text}\nНадішліть час:",
                              reply_markup=kb)

        bot.register_next_step_handler(msg, handle_manual_appoint_name, msg, kb)
    
    def handle_manual_appoint_name(message: Message, msg_to_edit: Message, kb: InlineKeyboardMarkup):
        bot.delete_message(chat_id=message.chat.id, 
                            message_id=message.message_id)
        
        appoint_data[message.from_user.id]['time'] = message.text
        check = check_slot(appoint_data[message.from_user.id]['date'], appoint_data[message.from_user.id]['time'])
        
        if check > 0:
            appoint_data[message.from_user.id]['slot_id'] = check
            msg = bot.edit_message_text(chat_id=msg_to_edit.chat.id,
                                message_id=msg_to_edit.message_id,
                                text=f"СТВОРЕННЯ НОВОГО ЗАПИСУ\n\nДата: {appoint_data[message.from_user.id]['date_str']}\nЧас: {appoint_data[message.from_user.id]['time']}\nНадішліть ім'я клієнта:",
                                reply_markup=kb)
        
        elif check == False:
            msg = bot.edit_message_text(chat_id=msg_to_edit.chat.id,
                    message_id=msg_to_edit.message_id,
                    text="Час вже зайнятий або ще не доданий в календар.\n\nСпробуйте ще раз: /appoint",
                    reply_markup=kb)
            return
        
        if check is None:
            msg = bot.edit_message_text(chat_id=msg_to_edit.chat.id,
                    message_id=msg_to_edit.message_id,
                    text="Неправильний формат дати або часу.\n\nСпробуйте ще раз: /appoint",
                    reply_markup=kb)
            return
            
        bot.register_next_step_handler(msg, handle_manual_appoint_phone, msg, kb)
        
    def handle_manual_appoint_phone(message: Message, msg_to_edit: Message, kb: InlineKeyboardMarkup):
        bot.delete_message(chat_id=message.chat.id, 
                    message_id=message.message_id) 
        
        appoint_data[message.from_user.id]['name'] = message.text
        msg = bot.edit_message_text(chat_id=msg_to_edit.chat.id,
                              message_id=msg_to_edit.message_id, 
                              text=f"СТВОРЕННЯ НОВОГО ЗАПИСУ\n\nДата: {appoint_data[message.from_user.id]['date_str']}\nЧас: {appoint_data[message.from_user.id]['time']}\nІм'я: {appoint_data[message.from_user.id]['name']}\nНадішліть номер телефону клієнта:",
                              reply_markup=kb)
    
        bot.register_next_step_handler(msg, handle_manual_appoint_service, msg, kb)
        
    def handle_manual_appoint_service(message: Message, msg_to_edit: Message, kb: InlineKeyboardMarkup):
        bot.delete_message(chat_id=message.chat.id, 
                    message_id=message.message_id)
        
        appoint_data[message.from_user.id]['phone'] = message.text
        msg = bot.edit_message_text(chat_id=msg_to_edit.chat.id,
                              message_id=msg_to_edit.message_id,
                              text=f"СТВОРЕННЯ НОВОГО ЗАПИСУ\n\nДата: {appoint_data[message.from_user.id]['date_str']}\nЧас: {appoint_data[message.from_user.id]['time']}\nІм'я: {appoint_data[message.from_user.id]['name']}\nНомер телефону: {appoint_data[message.from_user.id]['phone']}\nНадішліть назву послуги:",
                              reply_markup=kb)
    
        bot.register_next_step_handler(msg, handle_manual_appoint, msg, kb)
        
    def handle_manual_appoint(message: Message, msg_to_edit: Message, kb: InlineKeyboardMarkup):
        bot.delete_message(chat_id=message.chat.id, 
                            message_id=message.message_id)
        
        slot_id, name, phone, date_str, time = appoint_data[message.from_user.id]['slot_id'], appoint_data[message.from_user.id]['name'], appoint_data[message.from_user.id]['phone'], appoint_data[message.from_user.id]['date_str'], appoint_data[message.from_user.id]['time']  
        serv_id = get_serv_id_by_name(message.text)
        
        if serv_id is None:
            bot.edit_message_text(chat_id=msg_to_edit.chat.id,
                                    message_id=msg_to_edit.message_id,
                                    text=f"Не знайдено послуги за назвою {message.text}.\n\nСпробуйте ще раз: /appoint", parse_mode='HTML',
                                    reply_markup=kb)
            return
        
        bot.edit_message_text(chat_id=msg_to_edit.chat.id,
                        message_id=msg_to_edit.message_id,
                        text="Створення запису...",
                        reply_markup=kb)
        
        if appoint(slot_id, name, phone, serv_id) == True:
            bot.edit_message_text(chat_id=msg_to_edit.chat.id,
                                    message_id=msg_to_edit.message_id,
                                    text=f"<b>✅ Запис створено!</b>\n\n👤 {name}\n📅 Дата: {date_str}\n⏰ Час: {time}\nТелефон: {phone}\n💅 {message.text}", parse_mode='HTML',
                                    reply_markup=kb)
    
            
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
        
        
    @bot.callback_query_handler(func= lambda call: call.data == "btn_deleteService")
    @is_admin
    def handle_delete_service_name(call: CallbackQuery):
        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton("Головне меню", callback_data="btn_mainMenu")
        )

        msg = bot.edit_message_text(chat_id=call.message.chat.id,
                                    message_id=call.message.message_id,
                                    text='Виберіть послугу:',
                                    reply_markup=create_pagination_kb_services_del()
                                   )        
              
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

    @bot.callback_query_handler(func=lambda call: call.data.startswith("serv_del_"))
    def handle_service_deletion(call: CallbackQuery):
        serv_id = call.data.split("_")[2]
        serv_name = get_serv_name_by_id(serv_id)
        
        res = delete_service(serv_id)
        
        if res > 0:
            bot.edit_message_text(chat_id=call.message.chat.id,
                                    message_id=call.message.message_id,
                                    text=f"Послугу \"{serv_name}\" видалено успішно",
                                    reply_markup=admin_keyboard())
        elif res == 0:
            bot.edit_message_text(chat_id=call.message.chat.id,
                                    message_id=call.message.message_id,
                                    text=f"Не знайдено послугу {serv_name}",
                                    reply_markup=admin_keyboard())
        elif res is None:
            bot.edit_message_text(chat_id=call.message.chat.id,
                                    message_id=call.message.message_id,
                                    text=f"Виникла технічна помилка при спробі видалити послугу {serv_name}\n\nЗверніться до адміністратора або спробуйте пізніше",
                                    reply_markup=admin_keyboard())