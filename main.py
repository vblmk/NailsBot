import os
import telebot
import gspread
from dotenv import load_dotenv
from gspread_dataframe import get_as_dataframe
from tools import initial_keyboard

load_dotenv()

DB_HOST            = os.getenv('DB_HOST')
DB_PORT            = int(os.getenv('DB_PORT'))
DB_USER            = os.getenv('DB_USER')
DB_PASSWORD        = os.getenv('DB_PASSWORD')
DB_NAME            = os.getenv('DB_NAME')
TOKEN              = os.getenv('TOKEN')
GS_CREDS_PATH      = os.getenv('GS_CREDS_PATH')
GS_NAME            = os.getenv('GS_NAME')
SCHEDULE_WORKSHEET = os.getenv('SCHEDULE_WORKSHEET')
DATA_WORKSHEET     = os.getenv("DATA_WORKSHEET")

bot = telebot.TeleBot(TOKEN)

gc         = gspread.service_account(filename=GS_CREDS_PATH)
sh         = gc.open(GS_NAME)
scedule_ws = sh.worksheet(SCHEDULE_WORKSHEET)
data_ws    = sh.worksheet(DATA_WORKSHEET)

@bot.message_handler(commands=["start"])
def start(message):
    df = get_as_dataframe(data_ws)
    result = df.query("TgId == @message.from_user.id").to_dict("records")

    if len(result) > 0:
        bot.send_message(message.chat.id, "Манікюрна баби галі", reply_markup=initial_keyboard())

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
            bot.answer_callback_query(call.id, text="to be done...")

        bot.answer_callback_query(call.id, text='')

def get_phone(message):
    user_data = {'phone' : message.text}
    msg = bot.send_message(message.chat.id, "Як до вас можна звертатись?")
    bot.register_next_step_handler(msg, get_name, user_data)

def get_name(message, user_data):
    name = message.text
    phone = user_data['phone']
    tg_id = message.from_user.id

    data_ws.append_row([name, phone, tg_id])

    bot.send_message(message.chat.id, f"Авторизація пройшла успішно!", reply_markup=initial_keyboard())

bot.polling(none_stop=True)