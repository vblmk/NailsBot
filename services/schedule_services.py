import pandas as pd
from datetime import datetime, timedelta
from database import schedule_ws
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from database import engine
from sqlalchemy import text
from utils.decorators import safe_db_query

@safe_db_query
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
                "service_id": None,
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

    print(f"Згенеровано розклад на {days_to_generate} днів у PostgreSQL та Google Sheets!")

@safe_db_query
def get_schedule():
    query = "SELECT id, slot_date AS \"Date\", slot_time AS \"Time\", status AS \"Status\", client_name AS \"Name\", service_id AS \"Service_id\" FROM schedule WHERE status = 'Available' ORDER BY slot_date, slot_time"
    df = pd.read_sql(query, engine)

    if not df.empty:
        df['Date'] = df['Date'].apply(lambda x: x.strftime("%d-%m-%Y") if hasattr(x, 'strftime') else str(x))
        df['Time'] = df['Time'].apply(lambda x: x.strftime("%H:%M") if hasattr(x, 'strftime') else str(x))
    return df


@safe_db_query
def appoint(slot_id, name, phone, service_id, user_id=None):
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

    try:
        df = get_as_dataframe(schedule_ws)
        matching_rows = df[(df['Дата'] == date_str) & (df['Час'] == time_str)].index
        if len(matching_rows) > 0:
            row_index = matching_rows[0] + 2
            new_values = [[name, phone, service_name]]
            schedule_ws.update(range_name=f'C{row_index}:E{row_index}', values=new_values)
        else:
            print("⚠️ Не знайдено відповідного рядка в Google Таблиці")
    except Exception as gs_err:
        print(f"💥 Помилка оновлення Google Sheets: {gs_err}")

    return True