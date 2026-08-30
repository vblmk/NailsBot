from bot_config import user_df, months_ua
from telebot import TeleBot
from telebot.types import Message, CallbackQuery
from utils.decorators import is_admin
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from services.schedule_services import appoint, generate_schedule
from keyboards.pagination import create_pagination_kb_date_schedule, create_kb_services_del, create_pagination_kb_dates_appoint, create_pagination_kb_time, create_kb_time_manapp, create_kb_service_manappp
from keyboards.inline import admin_keyboard, mainmenu_keyboard, confirm_manapp_keyboard
from services.db_services import get_schedule_info, add_service_db, delete_service, get_serv_name_by_id, get_serv_id_by_name, check_slot, get_slot_id
from utils.formatters import is_float, format_duration_to_db, format_duration_from_db

serv_data = {}
appoint_data = {}
admin_sched_cache_df = {}

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
        bot.answer_callback_query(call.id)
        
        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton("Головне меню", callback_data="btn_mainMenu")
        )

        msg = bot.edit_message_text(chat_id=call.message.chat.id,
                                    message_id=call.message.message_id,
                                    text='Виберіть послугу:',
                                    reply_markup=create_kb_services_del()
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
    @is_admin
    def handle_service_deletion(call: CallbackQuery):
        bot.answer_callback_query(call.id)
        
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
            
    @bot.callback_query_handler(func=lambda call: call.data == "gen_sched")
    @is_admin
    def gen_sched(call: CallbackQuery):
        bot.answer_callback_query(call.id)
        
        bot.edit_message_text(chat_id=call.message.chat.id,
                        message_id=call.message.message_id,
                        text="Генерація розкладу...")
        
        if generate_schedule():
            bot.edit_message_text(chat_id=call.message.chat.id,
                                  message_id=call.message.message_id,
                                  text="Розклад успішно згенеровано",
                                  reply_markup=admin_keyboard())
        
    @bot.callback_query_handler(func=lambda call: call.data.startswith("manualAppointChooseDate_"))
    @is_admin
    def handle_manual_appoint_date(call: CallbackQuery):
        bot.answer_callback_query(call.id)
        
        data = call.data.split("_")[1].split("-")

        month = int(data[0])
        year = int(data[1])
        
        now = datetime.now()
        
        if month is None:
            month = int(now.month)        
        if year is None:
            year = int(now.year)
        
        bot.edit_message_text(chat_id=call.message.chat.id,
                              message_id= call.message.message_id,
                              text = f"Виберіть дату:\n\n{months_ua[month]} {year}",
                              reply_markup=create_pagination_kb_dates_appoint(month, year))
        
    @bot.callback_query_handler(func=lambda call: call.data.startswith("appointDate_"))
    @is_admin
    def handle_manual_appoint_time(call: CallbackQuery):
        bot.answer_callback_query(call.id)
        
        date_str = call.data.split("_")[1]
        year, month, day = date_str.split("-")
        
        appoint_data[call.from_user.id] = {}
        appoint_data[call.from_user.id]['date'] = date_str
        
        bot.edit_message_text(chat_id=call.message.chat.id,
                              message_id= call.message.message_id,
                              text = f"Дата: {date_str}\n\nВиберіть час:",
                              reply_markup=create_kb_time_manapp(call.from_user.id, date_str))

    @bot.callback_query_handler(func=lambda call: call.data.startswith("manapp_time_"))
    @is_admin
    def handle_manual_appoint_service(call: CallbackQuery):
        bot.answer_callback_query(call.id)
        
        time_str = call.data.split("_")[2]
        appoint_data[call.from_user.id]['time'] = time_str
        
        slot_id = get_slot_id(appoint_data[call.from_user.id]['date'], time_str)
        appoint_data[call.from_user.id]['slot_id'] = slot_id
        
        bot.edit_message_text(chat_id=call.message.chat.id,
                                message_id= call.message.message_id,
                                text = f"Дата: {appoint_data[call.from_user.id]['date']}\nЧас: {appoint_data[call.from_user.id]['time']}\n\nВиберіть послугу:",
                                reply_markup=create_kb_service_manappp(call.from_user.id))
        
    @bot.callback_query_handler(func=lambda call: call.data.startswith("manapp_service_"))
    @is_admin
    def handle_manual_appoint_name(call: CallbackQuery):
        bot.answer_callback_query(call.id)
        
        service_id = call.data.split("_")[2]
        service_name = get_serv_name_by_id(service_id)
        
        appoint_data[call.from_user.id]['service_id'] = service_id
        appoint_data[call.from_user.id]['service_name'] = service_name

        msg = bot.edit_message_text(chat_id=call.message.chat.id,
                        message_id= call.message.message_id,
                        text = f"Дата: {appoint_data[call.from_user.id]['date']}\nЧас: {appoint_data[call.from_user.id]['time']}\nПослуга: {service_name}\n\nНадішліть ім'я клієнта:",
                        reply_markup=mainmenu_keyboard())
        
        bot.register_next_step_handler(msg, handle_manual_appoint_phone, msg)
        
    def handle_manual_appoint_phone(message: Message, msg: Message):
        bot.delete_message(message.chat.id, message.message_id)
        
        name = message.text
        appoint_data[message.from_user.id]['name'] = name
        
        msg = bot.edit_message_text(chat_id=msg.chat.id,
                message_id= msg.message_id,
                text = f"Дата: {appoint_data[message.from_user.id]['date']}\nЧас: {appoint_data[message.from_user.id]['time']}\nПослуга: {appoint_data[message.from_user.id]['service_name']}\nІм'я: {name}\n\nНадішліть номер телефону клієнта: ",
                reply_markup=mainmenu_keyboard())
        
        bot.register_next_step_handler(msg, handle_manual_appoint, msg)
        
    def handle_manual_appoint(message: Message, msg: Message):
        bot.delete_message(message.chat.id, message.message_id)
        
        phone = message.text
        
        appoint_data[message.from_user.id]['phone'] = phone
        msg = bot.edit_message_text(chat_id=msg.chat.id,
                                    message_id= msg.message_id,
                                    text = f"Дата: {appoint_data[message.from_user.id]['date']}\nЧас: {appoint_data[message.from_user.id]['time']}\nПослуга: {appoint_data[message.from_user.id]['service_name']}\nІм'я: {appoint_data[message.from_user.id]['name']}\nТелефон: {phone}\n\nПеревірте інформацію:",
                                    reply_markup=confirm_manapp_keyboard())
    
    @bot.callback_query_handler(func=lambda call: call.data == "manapp_confirm")
    @is_admin
    def manapp_confirm(call: CallbackQuery):
        bot.answer_callback_query(call.id)
        user_id = call.from_user.id
        
        slot_id, name, phone, service_id = appoint_data[user_id]['slot_id'], appoint_data[user_id]['name'], appoint_data[user_id]['phone'], appoint_data[user_id]['service_id']
        
        bot.edit_message_text(chat_id=call.message.chat.id,
                                message_id=call.message.message_id,
                                text="Створення запису...")
        
        res = appoint(slot_id, name, phone, service_id) 
        
        if res == True:
            bot.edit_message_text(chat_id=call.message.chat.id,
                            message_id= call.message.message_id,
                            text = f"✅Запис створено!\nДата: {appoint_data[call.from_user.id]['date']}\nЧас: {appoint_data[call.from_user.id]['time']}\nПослуга: {appoint_data[call.from_user.id]['service_name']}\nІм'я: {appoint_data[call.from_user.id]['name']}\nТелефон: {phone}\n\n",
                            reply_markup=mainmenu_keyboard())
        elif res is None:
            bot.edit_message_text(chat_id=call.message.chat.id,
                            message_id= call.message.message_id,
                            text = "Виникла технічна помилка при створенні запису.",
                            reply_markup=mainmenu_keyboard())
        elif res == False:
            bot.edit_message_text(chat_id=call.message.chat.id,
                            message_id= call.message.message_id,
                            text = "Цей час уже зайнятий, спробуйте ще раз.",
                            reply_markup=mainmenu_keyboard())