import os
import threading
import time
from datetime import datetime, timedelta
import pandas as pd
import telebot
import gspread
from dotenv import load_dotenv
from gspread_dataframe import get_as_dataframe
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from tools import initial_keyboard, get_schedule, create_pagination_kb_date, create_pagination_kb_time, appoint

load_dotenv()

DB_HOST            = os.getenv('DB_HOST')
DB_PORT        = int(os.getenv('DB_PORT'))
DB_USER            = os.getenv('DB_USER')
DB_PASSWORD        = os.getenv('DB_PASSWORD')
DB_NAME            = os.getenv('DB_NAME')
TOKEN              = os.getenv('TOKEN')
GS_CREDS_PATH      = os.getenv('GS_CREDS_PATH')
GS_NAME            = os.getenv('GS_NAME')
SCHEDULE_WORKSHEET = os.getenv('SCHEDULE_WORKSHEET')
DATA_WORKSHEET     = os.getenv("DATA_WORKSHEET")

bot = telebot.TeleBot(TOKEN)

gc          = gspread.service_account(filename=GS_CREDS_PATH)
sh          = gc.open(GS_NAME)
schedule_ws = sh.worksheet(SCHEDULE_WORKSHEET)
data_ws     = sh.worksheet(DATA_WORKSHEET)

user_df = {}

def reminder_loop():
    while True:
        try:
            data = schedule_ws.get_all_records()
            now = datetime.now()

            for i, row in enumerate(data):
                if row["Status"] == "Available" or not row["UserID"]:
                    continue

                try:
                    appoint_dt = datetime.strptime(f"{row['Date']} {row['Time']}", "%d-%m-%Y %H:%M")
                except ValueError:
                    continue

                time_left = appoint_dt - now
                user_id = int(float(row["UserID"]))
                row_idx = i + 2

                if timedelta(days=6, hours=23) < time_left <= timedelta(days=7):
                    if str(row.get("Rem_7d")).upper() != "TRUE":
                        bot.send_message(user_id, f"🔔 Нагадування: Через тиждень ({row['Date']}) чекаємо вас о {row['Time']}! ✨")
                        schedule_ws.update_cell(row_idx, 7, True)

                elif timedelta(days=2, hours=23) < time_left <= timedelta(days=3):
                    if str(row.get("Rem_3d")).upper() != "TRUE":
                        bot.send_message(user_id, f"🗓 Нагадування: Через 3 дні ({row['Date']}) у вас запис о {row['Time']}. 👍")
                        schedule_ws.update_cell(row_idx, 8, True)

                elif timedelta(minutes=0) < time_left <= timedelta(hours=1):
                    if str(row.get("Rem_1h")).upper() != "TRUE":
                        bot.send_message(user_id, f"⏰ Нагадування: Ваш запис уже за годину (о {row['Time']})! Чекаємо на вас. 😉")
                        schedule_ws.update_cell(row_idx, 9, True)

        except Exception as e:
            print(f"Помилка у фоновому потоці нагадувань: {e}")

        time.sleep(900)

@bot.message_handler(commands=["start"])
def start(message):
    user_df.pop(message.from_user.id, None)

    df = get_as_dataframe(data_ws)
    result = df.query("TgId == @message.from_user.id").to_dict("records")

    if len(result) > 0:
        bot.send_message(message.chat.id, "Манікюрна баби галі", reply_markup=initial_keyboard())

    else:
        msg = bot.send_message(message.chat.id, "Привіт! Щоб продовжити, вам необхідно авторизуватись.\n" +
                                          "Надішліть, будь ласка, свій номер телефону")

        bot.register_next_step_handler(msg, get_phone)

@bot.callback_query_handler(func=lambda call: call.data.startswith("pagedate_"))
def handle_date_pagination(call):
    page = int(call.data.split("_")[1])
    df = user_df[call.from_user.id]

    kb = create_pagination_kb_date(df, page=page)

    bot.edit_message_reply_markup(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("date_"))
def handle_date_selection(call):
    df_index = int(call.data.split("_")[1])
    df = user_df[call.from_user.id]

    row = df.loc[df_index]
    date = row['Date']

    kb = create_pagination_kb_time(df, date)

    bot.edit_message_text(
        text="Виберіть час:",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("pagetime_"))
def handle_time_pagination(call):
    date = call.data.split("_")[1]
    page = int(call.data.split("_")[2])

    df = user_df[call.from_user.id]

    kb = create_pagination_kb_time(df, date, page=page)

    bot.edit_message_reply_markup(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=kb
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("book_"))
def handle_booking(call):
    user_df.pop(call.from_user.id, None)

    data = schedule_ws.get_all_records()
    df_full = pd.DataFrame(data)

    df_index = int(call.data.split("_")[1])

    try:
        if df_index not in df_full.index:
            bot.answer_callback_query(call.id, "Цей запис більше не існує.", show_alert=True)
            return

        row = df_full.loc[df_index]
        date = row['Date']
        time = row['Time']
        status = row['Status']

        if status != 'Available':
            bot.answer_callback_query(call.id, "На жаль, цей час уже зайнятий!", show_alert=True)
            return

        df_users = get_as_dataframe(data_ws)
        user_id = call.from_user.id

        user_record = df_users[df_users['TgId'].astype(float) == float(user_id)].to_dict("records")

        if user_record:
            user = user_record[0]
            appoint(date, time, user['Name'], user['PhoneNumber'], user_id)

            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"✅ Ви успішно записані!\n📅 Дата: {date}\n⏰ Час: {time}\n\nЧекаємо на вас!",
                reply_markup=initial_keyboard()
            )
        else:
            bot.answer_callback_query(call.id, "Користувача не знайдено. Натисніть /start", show_alert=True)

    except Exception as e:
        print(f"Помилка бронювання: {e}")
        bot.answer_callback_query(call.id, "Сталася технічна помилка.", show_alert=True)


@bot.callback_query_handler(lambda call: True)
def callback(call):
    if call.data == "btnPrice":
        user_df.pop(call.from_user.id, None)

        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="main_menu"))
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="💸 Прайс:\n - Ноготочкі: 700грн\n - Бровкі: 400грн\n - Глазкі: 500грн",
            reply_markup=kb
        )

    elif call.data == "main_menu":
        user_df.pop(call.from_user.id, None)

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="Манікюрна баби галі",
            reply_markup=initial_keyboard()
        )

    elif call.data == "back_to_dates":
        bot.answer_callback_query(call.id)

        df = user_df.get(call.from_user.id)

        if df is None:
            df = get_schedule()
            user_df[call.from_user.id] = df

        if df.empty:
            bot.answer_callback_query(call.id, "Наразі вільних вікон немає.", show_alert=True)
        else:
            kb = create_pagination_kb_date(df, page=0)
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="Виберіть дату:",
                reply_markup=kb
            )

    if call.data == "btnAppoint":
        user_df[call.from_user.id] = get_schedule()
        df = user_df[call.from_user.id]

        if df.empty:
            bot.answer_callback_query(call.id, "Наразі вільних вікон немає.", show_alert=True)
        else:
            kb = create_pagination_kb_date(df, page=0)
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="Виберіть дату:",
                reply_markup=kb
            )

def get_phone(message):
    user_data = {'phone' : message.text.strip()}
    msg = bot.send_message(message.chat.id, "Як до вас можна звертатись?")
    bot.register_next_step_handler(msg, get_name, user_data)

def get_name(message, user_data):
    name = message.text.strip()
    phone = user_data['phone']
    tg_id = message.from_user.id
    data_ws.append_row([name, phone, tg_id])

    bot.send_message(message.chat.id, f"Авторизація пройшла успішно!", reply_markup=initial_keyboard())

if __name__ == "__main__":
    bg_thread = threading.Thread(target=reminder_loop, daemon=True)
    bg_thread.start()

    print("🚀 Бот та система нагадувань успішно запущені!")
    bot.polling(none_stop=True)