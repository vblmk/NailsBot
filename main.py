import os
import telebot
import pymysql.cursors
import gspread
import pandas as pd
from dotenv import load_dotenv
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

load_dotenv()

DB_HOST = os.getenv('DB_HOST')
DB_PORT=int(os.getenv('DB_PORT'))
DB_USER=os.getenv('DB_USER')
DB_PASSWORD=os.getenv('DB_PASSWORD')
DB_NAME=os.getenv('DB_NAME')
TOKEN = os.getenv('TOKEN')
GS_CREDS_PATH = os.getenv('GS_CREDS_PATH')
GS_NAME = os.getenv('GS_NAME')

bot = telebot.TeleBot(TOKEN)
connection = pymysql.connect(host=DB_HOST,
                             user=DB_USER,
                             password=DB_PASSWORD,
                             db=DB_NAME,
                             port=DB_PORT,
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor)
cursor = connection.cursor()

gc = gspread.service_account(filename=GS_CREDS_PATH)
sh = gc.open(GS_NAME)
worksheet = sh.worksheet("Sheet1")
data = worksheet.get_all_records()

@bot.message_handler(commands=["start"])
def start(message):
        sql = f"select * from users where tgId = {message.from_user.id};"
        cursor.execute(sql)
        results = cursor.fetchall()

        if len(results) > 0:
            kb = InlineKeyboardMarkup(row_width=2)
            btnPrice = InlineKeyboardButton("Прайс-лист", callback_data="btnPrice")
            btnAppoint = InlineKeyboardButton("Запис", callback_data="btnAppoint")
            kb.add(btnPrice, btnAppoint)

            bot.send_message(message.chat.id, "Манікюрна баби галі", reply_markup=kb)

        else:
            msg = bot.send_message(message.chat.id, "Привіт! Щоб продовжити, вам необхідно авторизуватись.\n" +
                                              "Надішліть, будь ласка, свій номер телефону")

            bot.register_next_step_handler(msg, get_phone)

@bot.callback_query_handler(lambda call:True)
def callback(call):
        if call.data == "btnPrice":
                bot.send_message(call.message.chat.id, "💸 Прайс:\n"+
                                                       " - Ноготочкі: 700грн\n"+
                                                       " - Бровкі: 400грн\n"+
                                                       " - Глазкі: 500грн")

        if call.data == "btnAppoint":
                bot.send_message(call.message.chat.id, "ну вот і всьо (┬﹏┬)")

        bot.answer_callback_query(call.id, text="Processed!")

def get_phone(message):
    phone = message.text
    user_data = {'phone' : phone}
    msg = bot.send_message(message.chat.id, "Як до вас можна звертатись?")

    bot.register_next_step_handler(msg, get_name, user_data)

def get_name(message, user_data):
    name = message.text
    phone = user_data['phone']
    tg_id = message.from_user.id

    with connection.cursor() as cursor:
        sql = "INSERT INTO users (name, phoneNumber, tgId) VALUES (%s, %s, %s)"
        cursor.execute(sql, (name, phone, message.from_user.id))
        connection.commit()

    kb = InlineKeyboardMarkup(row_width=2)
    btnPrice = InlineKeyboardButton("Прайс-лист", callback_data="btnPrice")
    btnAppoint = InlineKeyboardButton("Запис", callback_data="btnAppoint")
    kb.add(btnPrice, btnAppoint)

    bot.send_message(message.chat.id, f"Авторизація пройшла успішно!", reply_markup=kb)


bot.polling(none_stop=True)