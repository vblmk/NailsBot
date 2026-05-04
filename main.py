import os
import telebot
from dotenv import load_dotenv
load_dotenv()

TOKEN = str(os.getenv('TOKEN'))
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=["start"])
def start(message):
        bot.send_message(message.chat.id, "Hello!")

bot.polling(none_stop=True)