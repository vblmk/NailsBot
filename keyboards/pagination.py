from services.db_services import get_date_times, get_services
from services.schedule_services import get_schedule
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import text
from database import engine
from datetime import datetime
import calendar

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

    for _, row in current_rows.iterrows():
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

def create_kb_services_del(page=0, limit=5):
    with engine.connect() as conn:
        kb = InlineKeyboardMarkup(row_width=1)        
        services = conn.execute(text("SELECT id, name FROM services")).mappings().all()
        
        for row in services:
            kb.add(InlineKeyboardButton(row['name'], callback_data=f"serv_del_{row['id']}"))
                    
    return kb

def create_pagination_kb_dates_appoint(month=None, year=None):
    kb = InlineKeyboardMarkup(row_width=7)
    btns = []

    now = datetime.now()
    month = month or now.month
    year = year or now.year

    fwday, days_in_month = calendar.monthrange(year, month)

    sql = text(
        """
        SELECT EXTRACT(DAY FROM slot_date) as day_num, COUNT(*) as cnt 
        FROM schedule 
        WHERE status = 'Available' 
          AND EXTRACT(MONTH FROM slot_date) = :m 
          AND EXTRACT(YEAR FROM slot_date) = :y 
        GROUP BY slot_date
    """
    )

    with engine.connect() as conn:
        result = conn.execute(sql, {"m": month, "y": year}).mappings()
        counts_by_day = {int(row["day_num"]): row["cnt"] for row in result}

    for _ in range(fwday):
        btns.append(InlineKeyboardButton(" - ", callback_data="pass"))

    for day in range(1, days_in_month + 1):
        slots_count = counts_by_day.get(day, 0)

        if slots_count == 0:
            btns.append(InlineKeyboardButton(f"{day}❌", callback_data="pass"))
        else:
            date_str = f"{year}-{month:02d}-{day:02d}"
            btns.append(
                InlineKeyboardButton(
                    f"{day}", callback_data=f"appointDate_{date_str}"
                )
            )

    total_buttons = fwday + days_in_month
    remainder = total_buttons % 7
    if remainder != 0:
        for _ in range(7 - remainder):
            btns.append(InlineKeyboardButton(" - ", callback_data="pass"))

    kb.add(*btns)

    prev_month = 12 if month == 1 else month - 1
    prev_year = year - 1 if month == 1 else year

    next_month = 1 if month == 12 else month + 1
    next_year = year + 1 if month == 12 else year

    kb.row(
        InlineKeyboardButton(
            "⬅️", callback_data=f"manualAppointChooseDate_{prev_month}-{prev_year}"
        ),
        InlineKeyboardButton(
            "➡️", callback_data=f"manualAppointChooseDate_{next_month}-{next_year}"
        ),
    )

    return kb

def create_kb_time_manapp(user_id, date):
    kb = InlineKeyboardMarkup(row_width=1)
    
    res = get_date_times(date)
        
    for row in res:
        time_str = str(row['slot_time']).removesuffix(":00")
        kb.add(InlineKeyboardButton(time_str, callback_data=f'manapp_time_{time_str}'))
        
    return kb

def create_kb_service_manappp(user_id):
    kb = InlineKeyboardMarkup(row_width=1)
    
    services = get_services()
    
    for row in services:
        kb.add(InlineKeyboardButton(str(row['name'] + ", " + row['duration']), callback_data=f"manapp_service_{row['id']}"))
        
    return kb