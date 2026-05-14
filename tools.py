import pandas as pd
from datetime import datetime, timedelta
import gspread
from gspread_dataframe import set_with_dataframe, get_as_dataframe
import os
from dotenv import load_dotenv
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

load_dotenv()

gc = gspread.service_account(filename=os.getenv('GS_CREDS_PATH'))
sh = gc.open(os.getenv('GS_NAME'))
schedule_ws = sh.worksheet(os.getenv('SCHEDULE_WORKSHEET'))

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
    schedule_ws.clear()
    set_with_dataframe(schedule_ws, df_new_schedule)

    print(f"Згенеровано розклад на {days_to_generate} днів!")

def get_schedule():
    data = schedule_ws.get_all_records()
    df = pd.DataFrame(data)
    filtered_df = df[df['Status'] == 'Available']

    return filtered_df

def initial_keyboard():
    kb = InlineKeyboardMarkup(row_width=2)
    btnPrice = InlineKeyboardButton("Прайс-лист", callback_data="btnPrice")
    btnAppoint = InlineKeyboardButton("Запис", callback_data="btnAppoint")
    kb.add(btnPrice, btnAppoint)

    return kb

def appoint(date, time, name, phone, id):
    df = get_as_dataframe(schedule_ws)
    row_index = df[(df['Date'] == date) & (df['Time'] == time)].index[0] + 2

    new_values = [[name, phone, id, 'Booked']]
    schedule_ws.update(new_values, f'C{row_index}:F{row_index}')


def create_pagination_kb(df, page=0, limit=5):
    kb = InlineKeyboardMarkup()

    start = page * limit
    end = start + limit

    current_rows = df.iloc[start:end]

    for index, row in current_rows.iterrows():
        btn_text = f"{row['Date']} {row['Time']}"
        kb.add(InlineKeyboardButton(btn_text, callback_data=f"book_{index}"))

    nav_btns = []
    if page > 0:
        nav_btns.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"page_{page - 1}"))

    if end < len(df):
        nav_btns.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"page_{page + 1}"))

    if nav_btns:
        kb.row(*nav_btns)

    return kb

if __name__ == "__main__":
    generate_schedule()