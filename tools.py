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


def add_service(name, price, duration, services_ws):
    id_column = services_ws.col_values(1)

    if len(id_column) <= 1:
        next_id = 1
    else:
        numeric_ids = [int(x) for x in id_column[1:] if str(x).isdigit()]
        next_id = max(numeric_ids) + 1 if numeric_ids else 1
    services_ws.append_row([next_id, name, price, duration])

    print(f"✅ added service #{next_id}: {name} - {price}₴")
    return True

def generate_schedule(schedule_ws):
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
                "Status": "Available",
                "Rem_7d": False,  # Стовпець 7 (номінально)
                "Rem_3d": False,  # Стовпець 8
                "Rem_1h": False   # Стовпець 9
            })

    df_new_schedule = pd.DataFrame(slots)
    schedule_ws.clear()
    set_with_dataframe(schedule_ws, df_new_schedule)

    print(f"Згенеровано розклад на {days_to_generate} днів із полями нагадувань!")

def get_schedule(schedule_ws):
    data = schedule_ws.get_all_records()
    df = pd.DataFrame(data)
    filtered_df = df[df['Status'] == 'Available']

    return filtered_df

def initial_keyboard():
    kb = InlineKeyboardMarkup(row_width=2)

    kb.add(InlineKeyboardButton("Прайс-лист", callback_data="btnPrice"),
           InlineKeyboardButton("Запис", callback_data="btnAppoint"))

    return kb

def appoint(date, time, name, phone, id, schedule_ws):
    df = get_as_dataframe(schedule_ws)
    row_index = df[(df['Date'] == date) & (df['Time'] == time)].index[0] + 2

    new_values = [[name, phone, id, 'Booked']]
    schedule_ws.update(new_values, f'C{row_index}:F{row_index}')

def create_pagination_kb_date(df, page=0, limit=5):
    kb = InlineKeyboardMarkup()
    unique_dates = df['Date'].unique()

    start = page * limit
    end = start + limit
    current_dates = unique_dates[start:end]

    for date_val in current_dates:
        first_index = df[df['Date'] == date_val].index[0]
        kb.add(InlineKeyboardButton(text=str(date_val), callback_data=f"date_{first_index}"))

    nav_btns = []
    if page > 0:
        nav_btns.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"pagedate_{page - 1}"))

    if end < len(unique_dates):
        nav_btns.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"pagedate_{page + 1}"))

    if nav_btns:
        kb.row(*nav_btns)

    kb.add(InlineKeyboardButton("🏠 Головне меню", callback_data="main_menu"))

    return kb


def create_pagination_kb_time(df, date, page=0, limit=5):
    kb = InlineKeyboardMarkup()

    df = df[df['Date'] == date]

    start = page * limit
    end = start + limit
    current_rows = df.iloc[start:end]

    for index, row in current_rows.iterrows():
        btn_text = f"{row['Time']}"
        kb.add(InlineKeyboardButton(btn_text, callback_data=f"book_{index}"))

    nav_btns = []
    if page > 0:
        nav_btns.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"pagetime_{date}_{page - 1}"))

    if end < len(df):
        nav_btns.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"pagetime_{date}_{page + 1}"))

    if nav_btns:
        kb.row(*nav_btns)

    kb.add(InlineKeyboardButton("🔙 До списку дат", callback_data="back_to_dates"))

    return kb

def add_master(name, ws = sh.worksheet(os.getenv("MASTERS_WORKSHEET"))):
    id_column = ws.col_values(1)

    if len(id_column) <= 1:
        next_id = 1
    else:
        numeric_ids = [int(x) for x in id_column[1:] if str(x).isdigit()]
        next_id = max(numeric_ids) + 1 if numeric_ids else 1

    ws.append_row([next_id, name])

if __name__ == "__main__":
    generate_schedule(sh.worksheet(os.getenv('SCHEDULE_WORKSHEET')))