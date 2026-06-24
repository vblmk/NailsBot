import os
from datetime import datetime, timedelta
import gspread
import pandas as pd
from dotenv import load_dotenv
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from sqlalchemy import create_engine, text
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
load_dotenv()

DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')
GS_CREDS_PATH      = os.getenv('GS_CREDS_PATH')
GS_NAME            = os.getenv('GS_NAME')
SCHEDULE_WORKSHEET = os.getenv('SCHEDULE_WORKSHEET')

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

gc = gspread.service_account(filename=os.getenv('GS_CREDS_PATH'))
sh = gc.open(os.getenv('GS_NAME'))
schedule_ws = sh.worksheet(SCHEDULE_WORKSHEET)

def add_service(name, price, duration):
    query = text("INSERT INTO services (name, price, duration) VALUES (:name, :price, :duration)")
    with engine.begin() as conn:
        conn.execute(query, {"name": name, "price": price, "duration": duration})

def generate_schedule():
    start_date = datetime.now().date()
    days_to_generate = 14
    slots_psql = []
    slots_gs = []

    for i in range(days_to_generate):
        current_date = start_date + timedelta(days=i)

        for hour in range(9, 19):
            time_str = f"{hour:02d}:00"
            slots_psql.append({
                "slot_date": current_date,
                "slot_time": time_str,
                "client_name": None,
                "client_phone": None,
                "user_id": None,
                "status": "Available",
                "service_id" : None,
                "rem_7d": False,
                "rem_3d": False,
                "rem_1h": False
            })

            slots_gs.append({
                "Дата": current_date.strftime("%d-%m-%Y"),
                "Час": time_str,
                "Ім'я": None,
                "Телефон": None,
                "Послуга": None,
            })

    df_new_schedule_psql = pd.DataFrame(slots_psql)
    df_new_schedule_gs = pd.DataFrame(slots_gs)

    schedule_ws.clear()
    set_with_dataframe(schedule_ws, df_new_schedule_gs)

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE schedule RESTART IDENTITY;"))
        df_new_schedule_psql.to_sql('schedule', conn, if_exists='append', index=False)

    print(f"Згенеровано розклад на {days_to_generate} днів у PostgreSQL!")

def get_schedule():
    query = "SELECT id, slot_date AS \"Date\", slot_time AS \"Time\", status AS \"Status\", client_name AS \"Name\", service_id AS \"Service_id\" FROM schedule WHERE status = 'Available' ORDER BY slot_date, slot_time"
    df = pd.read_sql(query, engine)

    if not df.empty:
        df['Date'] = df['Date'].apply(lambda x: x.strftime("%d-%m-%Y") if hasattr(x, 'strftime') else str(x))
        df['Time'] = df['Time'].apply(lambda x: x.strftime("%H:%M") if hasattr(x, 'strftime') else str(x))
    return df

def initial_keyboard():
    kb = InlineKeyboardMarkup(row_width=1)

    kb.add(InlineKeyboardButton("Прайс-лист", callback_data="btnPrice"),
           InlineKeyboardButton("Запис", callback_data="btnAppoint"),
           InlineKeyboardButton("Мої записи", callback_data="btnMyVisits"))

    return kb

def appoint(slot_id, name, phone, service_id, user_id=None, schedule_ws=schedule_ws):
    # ==========================================
    # 1. РОБОТА З БАЗОЮ ДАНИХ (Єдина транзакція)
    # ==========================================
    with engine.begin() as conn:
        result = conn.execute(text("""
            UPDATE schedule
            SET client_name  = :name,
                client_phone = :phone,
                user_id      = :user_id,
                status       = 'Booked',
                service_id   = :service_id
            WHERE id = :slot_id
              AND status = 'Available'
        """), {
            "name": name,
            "phone": phone,
            "user_id": user_id,
            "slot_id": slot_id,
            "service_id": service_id
        })

        if result.rowcount == 0:
            return False

        conn.execute(
            text("UPDATE services SET stat = COALESCE(stat, 0) + 1 WHERE id = :service_id"),
            {"service_id": service_id}
        )

    # ==========================================
    # 2. ОТРИМАННЯ ДАНИХ ДЛЯ GOOGLE ТАБЛИЦІ
    # ==========================================
    query_slot = text("SELECT slot_date, slot_time FROM schedule WHERE id = :slot_id")
    query_service = text("SELECT name FROM services WHERE id = :service_id")

    with engine.connect() as conn:
        result1 = conn.execute(query_slot, {"slot_id": slot_id}).mappings().first()
        result2 = conn.execute(query_service, {"service_id": service_id}).mappings().first()

    if not result1 or not result2:
        return True

    date_str = result1['slot_date'].strftime("%d-%m-%Y")
    time_str = result1['slot_time'].strftime("%H:%M")
    service_name = result2['name']

    # ==========================================
    # 3. ОНОВЛЕННЯ GOOGLE ТАБЛИЦІ
    # ==========================================
    try:
        df = get_as_dataframe(schedule_ws)
        matching_rows = df[(df['Дата'] == date_str) & (df['Час'] == time_str)].index
        if len(matching_rows) > 0:
            row_index = matching_rows[0] + 2
            new_values = [[name, phone, service_name]]
            schedule_ws.update(range_name=f'C{row_index}:E{row_index}', values=new_values)
        else:
            print("⚠️ Не знайдено відповідного рядка в Google Таблиці для оновлення")
    except Exception as gs_err:
        print(f"💥 Помилка оновлення Google Sheets: {gs_err}")

    return True

def create_pagination_kb_date_schedule(page=0, limit=5):
    kb = InlineKeyboardMarkup()
    df = get_schedule()
    unique_dates = df['Date'].unique()

    start = page * limit
    end = start + limit
    current_dates = unique_dates[start:end]

    for date_val in current_dates:
        kb.add(InlineKeyboardButton(text=str(date_val), callback_data=f"date_sched_{date_val}"))

    nav_btns = []
    if page > 0:
        nav_btns.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"pagedate_sched_{page - 1}"))
    if end < len(unique_dates):
        nav_btns.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"pagedate_sched_{page + 1}"))

    if nav_btns:
        kb.row(*nav_btns)
    kb.add(InlineKeyboardButton("🏠 Головне меню", callback_data="main_menu"))
    return kb

def create_pagination_kb_services(page=0, limit=5):
    kb = InlineKeyboardMarkup()
    query = text("SELECT id, name FROM services")

    with engine.connect() as conn:
        services_list = [dict(row) for row in conn.execute(query).mappings()]

    start = page * limit
    end = start + limit

    current_page_services = services_list[start:end]

    for e in current_page_services:
        kb.add(InlineKeyboardButton(f"{e['name']}", callback_data=f"service_{e['id']}"))

    nav_btns = []
    if page > 0:
        nav_btns.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"pageserv_{page - 1}"))
    if end < len(services_list):
        nav_btns.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"pageserv_{page + 1}"))

    if nav_btns:
        kb.row(*nav_btns)

    kb.add(InlineKeyboardButton("🏠 Головне меню", callback_data="main_menu"))
    return kb

def create_pagination_kb_date(df, service_id, page=0, limit=5):
    kb = InlineKeyboardMarkup()
    unique_dates = df['Date'].unique()

    start = page * limit
    end = start + limit
    current_dates = unique_dates[start:end]

    for date_val in current_dates:
        first_id = df[df['Date'] == date_val].iloc[0]['id']
        kb.add(InlineKeyboardButton(text=str(date_val), callback_data=f"date_{first_id}_{date_val}_{service_id}"))

    nav_btns = []
    if page > 0:
        nav_btns.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"pagedate_{service_id}_{page - 1}"))
    if end < len(unique_dates):
        nav_btns.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"pagedate_{service_id}_{page + 1}"))

    if nav_btns:
        kb.row(*nav_btns)
    kb.add(InlineKeyboardButton("🏠 Головне меню", callback_data="main_menu"))
    return kb

def create_pagination_kb_time(df, date, service_id, page=0, limit=5):
    kb = InlineKeyboardMarkup()
    df_filtered = df[df['Date'] == date]

    start = page * limit
    end = start + limit
    current_rows = df_filtered.iloc[start:end]

    for index, row in current_rows.iterrows():
        btn_text = f"{row['Time']}"
        # Передаємо реальний ID з бази даних для бронювання
        kb.add(InlineKeyboardButton(btn_text, callback_data=f"book_{row['id']}_{service_id}"))

    nav_btns = []
    if page > 0:
        nav_btns.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"pagetime_{date}_{service_id}_{page - 1}"))
    if end < len(df_filtered):
        nav_btns.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"pagetime_{date}_{service_id}_{page + 1}"))

    if nav_btns:
        kb.row(*nav_btns)
    kb.add(InlineKeyboardButton("🔙 До списку дат", callback_data=f"back_to_dates_{service_id}"))
    return kb

def add_master(name):
    query_insert = text("INSERT INTO masters (name) VALUES (:name)")
    with engine.begin() as conn:
        conn.execute(query_insert, {"name": name})


def format_duration(hours_float: float) -> str:
    hours_float = float(hours_float)
    hours = int(hours_float)
    minutes = round((hours_float - hours) * 60)

    if minutes == 60:
        hours += 1
        minutes = 0

    result = []
    if hours > 0:
        result.append(f"{hours} год")
    if minutes > 0:
        result.append(f"{minutes} хв")

    if not result:
        return "0 хв"

    return " ".join(result)


if __name__ == "__main__":
    generate_schedule()
