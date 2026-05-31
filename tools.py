import os
from datetime import datetime, timedelta
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
load_dotenv()

DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

def add_service(name, price, duration):
    query = text("INSERT INTO services (name, price, duration) VALUES (:name, :price, :duration)")
    with engine.begin() as conn:
        conn.execute(query, {"name": name, "price": price, "duration": duration})

def generate_schedule():
    start_date = datetime.now().date()
    days_to_generate = 14
    slots = []

    for i in range(days_to_generate):
        current_date = start_date + timedelta(days=i)

        for hour in range(9, 19):
            time_str = f"{hour:02d}:00"
            slots.append({
                "slot_date": current_date,
                "slot_time": time_str,
                "client_name": None,
                "client_phone": None,
                "user_id": None,
                "status": "Available",
                "rem_7d": False,
                "rem_3d": False,
                "rem_1h": False
            })

    df_new_schedule = pd.DataFrame(slots)

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE schedule RESTART IDENTITY;"))
        df_new_schedule.to_sql('schedule', conn, if_exists='append', index=False)

    print(f"Згенеровано розклад на {days_to_generate} днів у PostgreSQL!")

def get_schedule():
    query = "SELECT id, slot_date AS \"Date\", slot_time AS \"Time\", status AS \"Status\" FROM schedule WHERE status = 'Available' ORDER BY slot_date, slot_time"
    df = pd.read_sql(query, engine)

    if not df.empty:
        df['Date'] = df['Date'].apply(lambda x: x.strftime("%d-%m-%Y") if hasattr(x, 'strftime') else str(x))
        df['Time'] = df['Time'].apply(lambda x: x.strftime("%H:%M") if hasattr(x, 'strftime') else str(x))
    return df

def initial_keyboard():
    kb = InlineKeyboardMarkup(row_width=2)

    kb.add(InlineKeyboardButton("Прайс-лист", callback_data="btnPrice"),
           InlineKeyboardButton("Запис", callback_data="btnAppoint"))

    return kb

def appoint(slot_id, name, phone, user_id):
    query = text("""
        UPDATE schedule 
        SET client_name = :name, client_phone = :phone, user_id = :user_id, status = 'Booked'
        WHERE id = :slot_id AND status = 'Available'
    """)
    with engine.begin() as conn:
        result = conn.execute(query, {"name": name, "phone": phone, "user_id": user_id, "slot_id": slot_id})
        return result.rowcount > 0

def create_pagination_kb_date(df, page=0, limit=5):
    kb = InlineKeyboardMarkup()
    unique_dates = df['Date'].unique()

    start = page * limit
    end = start + limit
    current_dates = unique_dates[start:end]

    for date_val in current_dates:
        first_id = df[df['Date'] == date_val].iloc[0]['id']
        kb.add(InlineKeyboardButton(text=str(date_val), callback_data=f"date_{first_id}_{date_val}"))

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
    df_filtered = df[df['Date'] == date]

    start = page * limit
    end = start + limit
    current_rows = df_filtered.iloc[start:end]

    for index, row in current_rows.iterrows():
        btn_text = f"{row['Time']}"
        # Передаємо реальний ID з бази даних для бронювання
        kb.add(InlineKeyboardButton(btn_text, callback_data=f"book_{row['id']}"))

    nav_btns = []
    if page > 0:
        nav_btns.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"pagetime_{date}_{page - 1}"))
    if end < len(df_filtered):
        nav_btns.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"pagetime_{date}_{page + 1}"))

    if nav_btns:
        kb.row(*nav_btns)
    kb.add(InlineKeyboardButton("🔙 До списку дат", callback_data="back_to_dates"))
    return kb

def add_master(name):
    query = text("INSERT INTO masters (name) VALUES (:name)")
    with engine.begin() as conn:
        conn.execute(query, {"name": name})

if __name__ == "__main__":
    generate_schedule()