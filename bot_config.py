import os
import telebot
from dotenv import load_dotenv


load_dotenv()

TOKEN = os.getenv('TOKEN')
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')
GS_CREDS_PATH = os.getenv('GS_CREDS_PATH')
GS_NAME = os.getenv('GS_NAME')
SCHEDULE_WORKSHEET = os.getenv('SCHEDULE_WORKSHEET')
ADMIN_IDS = [int(x.strip()) for x in os.getenv('ADMIN_IDS', '').split(",") if x.strip().isdigit()]

bot = telebot.TeleBot(TOKEN)
user_df = {}