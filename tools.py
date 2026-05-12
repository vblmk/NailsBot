import pandas as pd
from datetime import datetime, timedelta
import gspread
from gspread_dataframe import set_with_dataframe
import os
from dotenv import load_dotenv
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

load_dotenv()

gc = gspread.service_account(filename=os.getenv('GS_CREDS_PATH'))
sh = gc.open(os.getenv('GS_NAME'))
worksheet = sh.worksheet(os.getenv('SCHEDULE_WORKSHEET'))


def generate_schedule():
    start_date = datetime.now().date()
    days_to_generate = 14
    slots = []

    for i in range(days_to_generate):
        current_date = start_date + timedelta(days=i)

        for hour in range(9, 19):
            time_str = f"{hour:02d}:00"
            slots.append({
                "Date": current_date.strftime("%d-%m-%Y"),
                "Time": time_str,
                "Name": "",
                "Phone": "",
                "UserID": "",
                "Status": "Available"
            })

    df_new_schedule = pd.DataFrame(slots)
    worksheet.clear()

    set_with_dataframe(worksheet, df_new_schedule)
    print(f"Згенеровано розклад на {days_to_generate} днів!")

def get_schedule():
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    filtered_df = df[df['Status'] == 'Available']

    return filtered_df

def initial_keyboard():
    kb = InlineKeyboardMarkup(row_width=2)
    btnPrice = InlineKeyboardButton("Прайс-лист", callback_data="btnPrice")
    btnAppoint = InlineKeyboardButton("Запис", callback_data="btnAppoint")
    kb.add(btnPrice, btnAppoint)
    return kb

if __name__ == "__main__":
    get_schedule()