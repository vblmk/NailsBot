import os
import threading
import time
from datetime import datetime, timedelta
import pandas as pd
import telebot
from sqlalchemy import text
from dotenv import load_dotenv
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from tools import (engine,
                   initial_keyboard,
                   get_schedule,
                   create_pagination_kb_date,
                   create_pagination_kb_time,
                   appoint,
                   add_service,
                   create_pagination_kb_services,
                   format_duration)

load_dotenv()

DB_HOST            = os.getenv('DB_HOST')
DB_PORT        = int(os.getenv('DB_PORT'))
DB_USER            = os.getenv('DB_USER')
DB_PASSWORD        = os.getenv('DB_PASSWORD')
DB_NAME            = os.getenv('DB_NAME')
TOKEN              = os.getenv('TOKEN')

bot = telebot.TeleBot(TOKEN)
user_df = {}
services = []

def reminder_loop():
    while True:
        try:
            now = datetime.now()
            query = text(
                "SELECT id, slot_date, slot_time, user_id, rem_7d, rem_3d, rem_1h FROM schedule WHERE status = 'Booked' AND user_id IS NOT NULL")

            with engine.connect() as conn:
                records = conn.execute(query).mappings().all()

            for row in records:
                appoint_dt = datetime.combine(row['slot_date'], row['slot_time'])
                time_left = appoint_dt - now
                user_id = int(row['user_id'])
                slot_id = row['id']

                date_str = row['slot_date'].strftime("%d-%m-%Y")
                time_str = row['slot_time'].strftime("%H:%M")

                if timedelta(days=6, hours=23) < time_left <= timedelta(days=7) and not row['rem_7d']:
                    bot.send_message(user_id, f"🔔 Нагадування: Через тиждень ({date_str}) чекаємо вас о {time_str}! ✨")
                    with engine.begin() as conn:
                        conn.execute(text("UPDATE schedule SET rem_7d = TRUE WHERE id = :id"), {"id": slot_id})

                elif timedelta(days=2, hours=23) < time_left <= timedelta(days=3) and not row['rem_3d']:
                    bot.send_message(user_id, f"🗓 Нагадування: Через 3 дні ({date_str}) у вас запис о {time_str}. 👍")
                    with engine.begin() as conn:
                        conn.execute(text("UPDATE schedule SET rem_3d = TRUE WHERE id = :id"), {"id": slot_id})

                elif timedelta(minutes=0) < time_left <= timedelta(hours=1) and not row['rem_1h']:
                    bot.send_message(user_id,
                                     f"⏰ Нагадування: Ваш запис уже за годину (о {time_str})! Чекаємо на вас. 😉")
                    with engine.begin() as conn:
                        conn.execute(text("UPDATE schedule SET rem_1h = TRUE WHERE id = :id"), {"id": slot_id})

        except Exception as e:
            print(f"Помилка у фоновому потоці нагадувань: {e}")

        time.sleep(900)

@bot.message_handler(commands=["start"])
def start(message):
    user_df.pop(message.from_user.id, None)

    query = text("SELECT * FROM users WHERE tg_id = :tg_id")
    with engine.connect() as conn:
        user_exists = conn.execute(query, {"tg_id": message.from_user.id}).fetchone()

    if user_exists:
        bot.send_message(message.chat.id, "Манікюрна баби галі", reply_markup=initial_keyboard())
    else:
        msg = bot.send_message(message.chat.id, "Привіт! Щоб продовжити, вам необхідно авторизуватись.\n" +
                                          "Надішліть, будь ласка, свій номер телефону")
        bot.register_next_step_handler(msg, get_phone)


@bot.message_handler(commands=["schedule"])
def schedule(message):
    user_df.pop(message.from_user.id, None)

    query = text("""
                 SELECT slot_time, client_name, client_phone, user_id, service_id
                 FROM schedule
                 WHERE slot_date = CURRENT_DATE
                   AND status = 'Booked'
                 ORDER BY slot_time
                 """)

    services_query = text("SELECT id, name FROM services")

    res_text = ""

    with engine.connect() as conn:
        booked_slots = conn.execute(query).mappings().all()
        services = conn.execute(services_query).mappings().all()

        services_dict = {srv['id']: srv['name'] for srv in services}

        if not booked_slots:
            bot.send_message(message.chat.id, "На сьогодні немає жодних записів. 🤷‍♀️")
            return

        for row in booked_slots:
            time_str = row['slot_time'].strftime("%H:%M")

            service_name = services_dict.get(row['service_id'], "Невідома послуга")

            try:
                chat_info = bot.get_chat(row['user_id'])
                tg_nick = f"@{chat_info.username}" if chat_info.username else "без юзернейму"
            except Exception:
                tg_nick = "не знайдено"

            res_text += f"⏰ {time_str}:\n   - 👤 {row['client_name']}\n   - 📞 {row['client_phone']}\n   - {tg_nick}\n   - 💅 {service_name}\n\n"

    bot.send_message(message.chat.id, f"📅 Розклад на сьогодні:\n\n{res_text}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("pagedate_"))
def handle_date_pagination(call):
    bot.answer_callback_query(call.id)
    parts = call.data.split("_")
    service_id = int(parts[1])  # Дістаємо послугу
    page = int(parts[2])  # Дістаємо сторінку

    df = user_df.get(call.from_user.id)
    if df is None:
        df = get_schedule()
        user_df[call.from_user.id] = df

    kb = create_pagination_kb_date(df, service_id=service_id, page=page)
    bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("date_"))
def handle_date_selection(call):
    bot.answer_callback_query(call.id)
    date_val = call.data.split("_")[2]
    service_id = call.data.split("_")[3]

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
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text="Виберіть дату:", reply_markup=kb)



@bot.callback_query_handler(func=lambda call: call.data.startswith("back_to_dates_"))
def handle_back_to_dates(call):
    bot.answer_callback_query(call.id)
    service_id = int(call.data.split("_")[3]) # back_to_dates_1
    df = get_schedule()
    user_df[call.from_user.id] = df

    if df.empty:
        bot.answer_callback_query(call.id, "Наразі вільних вікон немає.", show_alert=True)
    else:
        kb = create_pagination_kb_date(df, service_id=service_id, page=0)
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text="Виберіть дату:", reply_markup=kb)


@bot.callback_query_handler(func=lambda call: call.data.startswith("book_"))
def handle_booking(call):
    bot.answer_callback_query(call.id)

    user_df.pop(call.from_user.id, None)
    slot_id = int(call.data.split("_")[1])
    service_id = int(call.data.split("_")[2])

    try:
        with engine.connect() as conn:
            slot = conn.execute(text("SELECT slot_date, slot_time, status FROM schedule WHERE id = :id"), {"id": slot_id}).fetchone()

        if not slot:
            bot.answer_callback_query(call.id, "Цей запис більше не існує.", show_alert=True)
            return

        if slot.status != 'Available':
            bot.answer_callback_query(call.id, "На жаль, цей час уже зайнятий!", show_alert=True)
            return

        # Отримуємо дані користувача з БД
        with engine.connect() as conn:
            user = conn.execute(text("SELECT name, phone_number FROM users WHERE tg_id = :tg_id"), {"tg_id": call.from_user.id}).fetchone()

        if user:
            success = appoint(slot_id, user.name, user.phone_number, call.from_user.id, service_id)
            if success:
                date_str = slot.slot_date.strftime("%d-%m-%Y")
                time_str = slot.slot_time.strftime("%H:%M")
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=f"✅ Ви успішно записані!\n📅 Дата: {date_str}\n⏰ Час: {time_str}\n\nЧекаємо на вас!",
                    reply_markup=initial_keyboard()
                )
            else:
                bot.answer_callback_query(call.id, "Не вдалося забронювати. Можливо, його щойно зайняли.", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "Користувача не знайдено. Натисніть /start", show_alert=True)

    except Exception as e:
        print(f"Помилка бронювання: {e}")
        bot.answer_callback_query(call.id, "Сталася технічна помилка.", show_alert=True)

@bot.callback_query_handler(lambda call: True)
def callback(call):
    bot.answer_callback_query(call.id)

    if call.data == "btnPrice":
        user_df.pop(call.from_user.id, None)

        kb = InlineKeyboardMarkup(row_width=2)

        kb.add(InlineKeyboardButton("Запис", callback_data="btnAppoint"))

        df = pd.read_sql("SELECT name, price, duration FROM services", engine)
        res_text = ""
        for index, row in df.iterrows():
            res_text += f" 📌 {row['name']}, {row['price']}₴, {format_duration(row['duration'])}\n"

        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text="Наші послуги:\n" + res_text, reply_markup=kb)

    elif call.data == "main_menu":
        user_df.pop(call.from_user.id, None)
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text="Манікюрна баби галі", reply_markup=initial_keyboard())

    elif call.data == "btnAppoint":
        df = get_schedule()
        user_df[call.from_user.id] = df

        if df.empty:
            bot.answer_callback_query(call.id, "Наразі вільних вікон немає.", show_alert=True)
        else:
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("Вибрати послугу", callback_data="choose_service"))

            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text="Запис:", reply_markup=kb)

    elif call.data == "choose_service":
        kb = create_pagination_kb_services()

        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text="Виберіть послугу:", reply_markup=kb)

    elif call.data == "back_to_dates":
        df = get_schedule()
        user_df[call.from_user.id] = df

        if df.empty:
            bot.answer_callback_query(call.id, "Наразі вільних вікон немає.", show_alert=True)
        else:
            kb = create_pagination_kb_date(df, page=0)
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text="Виберіть дату:", reply_markup=kb)

def get_phone(message):
    user_data = {'phone' : message.text.strip()}
    msg = bot.send_message(message.chat.id, "Як до вас можна звертатись?")
    bot.register_next_step_handler(msg, get_name, user_data)

def get_name(message, user_data):
    name = message.text.strip()
    phone = user_data['phone']
    tg_id = message.from_user.id

    query = text("INSERT INTO users (tg_id, name, phone_number) VALUES (:tg_id, :name, :phone) ON CONFLICT (tg_id) DO NOTHING")
    with engine.begin() as conn:
        conn.execute(query, {"tg_id": tg_id, "name": name, "phone": phone})

    bot.send_message(message.chat.id, f"Авторизація пройшла успішно!", reply_markup=initial_keyboard())

if __name__ == "__main__":
    bg_thread = threading.Thread(target=reminder_loop, daemon=True)
    bg_thread.start()

    print("🚀 Бот та система нагадувань успішно запущені!")
    bot.polling(none_stop=True)
