from bot_config import user_df
from telebot import TeleBot
from utils.decorators import is_admin
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from services.schedule_services import appoint
from keyboards.pagination import create_pagination_kb_date_schedule
from services.db_services import get_schedule_info, get_service_and_slot_info

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
