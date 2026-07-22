from telebot import TeleBot
from bot_config import user_df
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from services.schedule_services import appoint
from keyboards.pagination import (create_pagination_kb_date,  
                                  create_pagination_kb_services, 
                                  create_pagination_kb_time)
from keyboards.inline import initial_keyboard
from services.schedule_services import get_schedule
from services.db_services import get_slot_and_user_info

def register_booking_handlers(bot: TeleBot):

    @bot.callback_query_handler(func=lambda call: call.data == "btn_chooseService")
    def cb_btn_chooseService(call):
        bot.answer_callback_query(call.id)
        
        kb = create_pagination_kb_services()
        bot.edit_message_text(
            chat_id=call.message.chat.id, 
            message_id=call.message.message_id,
            text="Виберіть послугу:", 
            reply_markup=kb
        )
        
    @bot.callback_query_handler(func=lambda call: call.data == "btn_appoint")
    def cb_btn_appoint(call):
        bot.answer_callback_query(call.id)
        
        df = get_schedule()
        user_df[call.from_user.id] = df

        if df.empty:
            bot.answer_callback_query(call.id, "Наразі вільних вікон немає.", show_alert=True)
        else:
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("Вибрати послугу", callback_data="btn_chooseService"))
            bot.edit_message_text(
                chat_id=call.message.chat.id, 
                message_id=call.message.message_id,
                text="Запис:", 
                reply_markup=kb
            )
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("pagedate_"))
    def handle_date_pagination(call):
        bot.answer_callback_query(call.id)

        parts = call.data.split("_")
        service_id = int(parts[1])
        page = int(parts[2])

        df = user_df.get(call.from_user.id)
        if df is None:
            df = get_schedule()
            user_df[call.from_user.id] = df

        kb = create_pagination_kb_date(df, service_id=service_id, page=page)
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=kb)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("date_"))
    def handle_date_selection(call):
        bot.answer_callback_query(call.id)
        
        parts = call.data.split("_")
        date_val = parts[2]
        service_id = parts[3]

        df = user_df.get(call.from_user.id)
        if df is None:
            df = get_schedule()
            user_df[call.from_user.id] = df

        kb = create_pagination_kb_time(df, date_val, service_id=service_id)
        bot.edit_message_text(text="Виберіть час:", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=kb)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("pagetime_"))
    def handle_time_pagination(call):
        bot.answer_callback_query(call.id)
        
        parts = call.data.split("_")
        date_val = parts[1]
        service_id = int(parts[2])
        page = int(parts[3])

        df = user_df.get(call.from_user.id)
        if df is None:
            df = get_schedule()
            user_df[call.from_user.id] = df

        kb = create_pagination_kb_time(df, date_val, service_id=service_id, page=page)
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=kb)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("pageserv_"))
    def callback_services_pagination(call):
        bot.answer_callback_query(call.id)
        
        current_page = int(call.data.split("_")[1])

        kb = create_pagination_kb_services(page=current_page)
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="Виберіть послугу:",
            reply_markup=kb
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("service_"))
    def callback_service_selection(call):
        bot.answer_callback_query(call.id)
        
        service_id = int(call.data.split("_")[1])

        df = get_schedule()
        user_df[call.from_user.id] = df

        if df.empty:
            bot.answer_callback_query(call.id, "Наразі вільних вікон немає.", show_alert=True)
        else:
            kb = create_pagination_kb_date(df, service_id=service_id, page=0)
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="Виберіть дату:", reply_markup=kb)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("back_to_dates_"))
    def handle_back_to_dates(call):
        bot.answer_callback_query(call.id)
        
        service_id = int(call.data.split("_")[3])
        df = get_schedule()
        user_df[call.from_user.id] = df

        if df.empty:
            bot.answer_callback_query(call.id, "Наразі вільних вікон немає.", show_alert=True)
        else:
            kb = create_pagination_kb_date(df, service_id=service_id, page=0)
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="Виберіть дату:", reply_markup=kb)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("approve_"))
    def appoint_approved(call):
        bot.answer_callback_query(call.id)
        
        _, slot_id, serv_id = call.data.split("_")
        user_id = call.from_user.id

        info = get_slot_and_user_info(user_id, slot_id, serv_id)
        
        if info is None:
            bot.answer_callback_query(call.id, "Цей запис або користувач не існує. Натисніть /start", show_alert=True)
            return 
        
        name, phone_number, date_str, time_str, serv_name, slot_status = info

        if slot_status != 'Available':
            bot.answer_callback_query(call.id, "Не вдалося забронювати. Можливо, цей час щойно зайняли.", show_alert=True)
            return

        success = appoint(slot_id, name, phone_number, serv_id, call.from_user.id)

        if success:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"✅ Ви успішно записані!\n📅 Дата: {date_str}\n⏰ Час: {time_str}\n💅 {serv_name}\nЧекаємо на вас!",
                reply_markup=initial_keyboard()
            )
        else:
            bot.answer_callback_query(call.id, "Не вдалося забронювати. Можливо, цей час щойно зайняли.", show_alert=True)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("book_"))
    def handle_booking(call):
        bot.answer_callback_query(call.id)
        
        user_df.pop(call.from_user.id, None)

        _, slot_id, service_id = call.data.split("_")
        slot_id = int(slot_id)
        service_id = int(service_id)
        user_id = call.from_user.id

        try:            
            info = get_slot_and_user_info(user_id, slot_id, service_id)
            
            if info is None:
                bot.answer_callback_query(call.id, "Цей запис або користувач не існує. Натисніть /start", show_alert=True)
                return
            
            name, phone, date_str, time_str, serv_name, slot_status = info

            if slot_status != 'Available':
                bot.answer_callback_query(call.id, "На жаль, цей час уже зайнятий!", show_alert=True)
                return
        
            kb = InlineKeyboardMarkup(row_width=1)
            kb.add(
                InlineKeyboardButton("✅ Підтвердити запис", callback_data=f"approve_{slot_id}_{service_id}"),
                InlineKeyboardButton("❌ Скасувати", callback_data="btn_cancel")
            )
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"✍️ Перевірте інформацію:\n   📅 Дата: {date_str}\n   ⏰ Час: {time_str}\n   💅 {serv_name}",
                reply_markup=kb
            )

        except Exception as e:
            print(f"Помилка бронювання: {e}")
            bot.answer_callback_query(call.id, "Сталася технічна помилка.", show_alert=True)