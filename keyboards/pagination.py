from services.schedule_services import get_schedule
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import text
from database import engine

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
    kb.add(InlineKeyboardButton("🏠 Головне меню", callback_data="btn_mainMenu"))
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

    kb.add(InlineKeyboardButton("🏠 Головне меню", callback_data="btn_mainMenu"))
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
    kb.add(InlineKeyboardButton("🏠 Головне меню", callback_data="btn_mainMenu"))
    return kb


def create_pagination_kb_time(df, date, service_id, page=0, limit=5):
    kb = InlineKeyboardMarkup()
    df_filtered = df[df['Date'] == date]

    start = page * limit
    end = start + limit
    current_rows = df_filtered.iloc[start:end]

    for index, row in current_rows.iterrows():
        btn_text = f"{row['Time']}"
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