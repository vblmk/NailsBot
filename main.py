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
                   add_service)

load_dotenv()

DB_HOST            = os.getenv('DB_HOST')
DB_PORT        = int(os.getenv('DB_PORT'))
DB_USER            = os.getenv('DB_USER')
DB_PASSWORD        = os.getenv('DB_PASSWORD')
DB_NAME            = os.getenv('DB_NAME')
TOKEN              = os.getenv('TOKEN')

bot = telebot.TeleBot(TOKEN)
user_df = {}


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

@bot.callback_query_handler(func=lambda call: call.data.startswith("pagedate_"))
def handle_date_pagination(call):
    page = int(call.data.split("_")[1])
    df = user_df.get(call.from_user.id)
    if df is None:
        df = get_schedule()
        user_df[call.from_user.id] = df

    kb = create_pagination_kb_date(df, page=page)
    bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("date_"))
def handle_date_selection(call):
    date_val = call.data.split("_")[2]
    df = user_df.get(call.from_user.id)
    if df is None:
        df = get_schedule()
        user_df[call.from_user.id] = df

    kb = create_pagination_kb_time(df, date_val)
    bot.edit_message_text(text="Виберіть час:", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("pagetime_"))
def handle_time_pagination(call):
    date_val = call.data.split("_")[1]
    page = int(call.data.split("_")[2])
    df = user_df.get(call.from_user.id)
    if df is None:
        df = get_schedule()
        user_df[call.from_user.id] = df

    kb = create_pagination_kb_time(df, date_val, page=page)
    bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("book_"))
def handle_booking(call):
    user_df.pop(call.from_user.id, None)
    slot_id = int(call.data.split("_")[1])

    try:
        # Перевіряємо статус слоту прямо в БД
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
            success = appoint(slot_id, user.name, user.phone_number, call.from_user.id)
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
    if call.data == "btnPrice":
        user_df.pop(call.from_user.id, None)

        kb = InlineKeyboardMarkup(row_width=2)

        kb.add(InlineKeyboardButton("Запис", callback_data="btnAppoint"))

        df = pd.read_sql("SELECT name, price, duration FROM services", engine)
        res_text = ""
        for index, row in df.iterrows():
            res_text += f" 📌 {row['name']}, {row['price']}₴, {row['duration']}\n"

        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text="Наші послуги:\n" + res_text, reply_markup=kb)

    elif call.data == "main_menu":
        user_df.pop(call.from_user.id, None)
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text="Манікюрна баби галі", reply_markup=initial_keyboard())

    elif call.data in ["back_to_dates", "btnAppoint"]:
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
