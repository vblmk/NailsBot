from database import engine
from sqlalchemy import text
from utils.formatters import format_duration_from_db
from utils.decorators import safe_db_query

@safe_db_query
def get_price():
    res_text = ""
    with engine.connect() as conn:
        services = conn.execute(text("SELECT name, price, duration FROM services")).mappings().all()
    for row in services:
        res_text += f" 📌 {row['name']}, {row['price']}₴, {format_duration_from_db(row['duration'])}\n"
    
    return res_text

@safe_db_query
def get_slot_and_user_info(user_id, slot_id, serv_id):
    with engine.connect() as conn:
        user = conn.execute(text("SELECT name, phone_number FROM users WHERE tg_id = :tg_id"), {"tg_id": user_id}).fetchone()
        slot = conn.execute(text("SELECT slot_date, slot_time, status FROM schedule WHERE id = :id"), {"id": slot_id}).fetchone()
        service = conn.execute(text("SELECT name FROM services WHERE id = :id"), {"id": serv_id}).fetchone()

    if not user or not slot:
        return
    
    return (user.name, 
            user.phone_number, 
            slot.slot_date.strftime("%d-%m-%Y"), 
            slot.slot_time.strftime("%H:%M"), 
            service.name if service else "Невідома послуга",
            slot.status)

@safe_db_query
def get_user_by_phone(phone):
    with engine.begin() as conn:
        user = conn.execute(
            text("SELECT phone_number, name, tg_id FROM users WHERE phone_number = :phone_number"), 
            {"phone_number": phone}
        ).fetchone()
    
    return user

@safe_db_query
def update_user_tgid(phone, tg_id):
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("UPDATE users SET tg_id = :tg_id WHERE phone_number = :phone"),
                {"tg_id": tg_id, "phone": phone}
            )

            if result.rowcount > 0:
                return True
            else:
                return False
    except Exception as e:
        print(f"Помилка при оновленні tg_id для {phone}: {e}")
        return False
    
@safe_db_query
def get_user_visits(phone: int):
        res_text = ''

        query = text("""
            SELECT s.slot_date, s.slot_time, s.client_name, serv.name as service_name
            FROM schedule s
            LEFT JOIN services serv ON s.service_id = serv.id
            WHERE s.client_phone = :phone AND s.status = 'Booked'
            ORDER BY s.slot_date, s.slot_time
        """)

        with engine.connect() as conn:
            visits = conn.execute(query, {"phone": str(phone)}).mappings().all()

        if visits:
            for row in visits:
                date_str = row['slot_date'].strftime("%d-%m-%Y")
                time_str = row['slot_time'].strftime("%H:%M")
                serv_name = row['service_name'] or "Невідома послуга"
                res_text += f"\n\n📌 {serv_name}\n  📅 Дата: {date_str}\n  ⏰ Час: {time_str}"
        else:
            return ""
                
        return res_text
    
@safe_db_query
def get_schedule_info(date, bot):
        query = text("""
            SELECT slot_time, client_name, client_phone, user_id, service_id
            FROM schedule
            WHERE slot_date = :date AND status = 'Booked'
            ORDER BY slot_time
        """)

        services_query = text("SELECT id, name FROM services")
        res_text = ""

        with engine.connect() as conn:
            booked_slots = conn.execute(query, {"date": date}).mappings().all()
            services_list = conn.execute(services_query).mappings().all()
            services_dict = {srv['id']: srv['name'] for srv in services_list}

            if not booked_slots:
                date_str = date.strftime("%d-%m-%Y") if hasattr(date, 'strftime') else str(date)
                return f"На {date_str} немає жодних записів."

            for row in booked_slots:
                time_str = row['slot_time'].strftime("%H:%M")
                service_name = services_dict.get(row['service_id'], "Невідома послуга")

                try:
                    chat_info = bot.get_chat(row['user_id'])
                    tg_nick = f"@{chat_info.username}" if chat_info.username else "без юзернейму"
                except Exception:
                    tg_nick = "не знайдено"

                res_text += f"⏰ {time_str}:\n   - 👤 {row['client_name']}\n   - 📞 {row['client_phone']}\n   - {tg_nick}\n   - 💅 {service_name}\n\n"
        
        return res_text

@safe_db_query
def add_service_db(name, price, duration):
    with engine.connect() as conn:
        conn.execute(text("select * from schedule"))
        try:
            conn.execute(text("SELECT * FROM schedule WHERE slot_time + INTERVAL :duration < '18:00'"), {'duration' : duration})
        except Exception as e:
            print(f"wif {e}")
            return "wrong interval format"

        result = conn.execute(text("INSERT INTO services (name, price, duration) VALUES (:name, :price, :duration)"), 
                     {'name' : name, 'price' : price, 'duration': duration})
        conn.commit()
        
    return result.rowcount

@safe_db_query
def delete_service(id):
    with engine.connect() as conn:
        result = conn.execute(text("DELETE FROM services WHERE id = :id"), {"id" : id})
        conn.commit()
    return result.rowcount

@safe_db_query
def get_serv_name_by_id(id: int):
    with engine.connect() as conn:
        res = conn.execute(text("SELECT name FROM services WHERE id = :id"), {'id' : id}).fetchone()
    return res.name     
    
@safe_db_query
def get_serv_id_by_name(name: str) -> str:
    with engine.connect() as conn:
        res = conn.execute(text("SELECT id FROM services WHERE name = :name"), {'name' : name}).fetchone()
    return res.id

@safe_db_query
def check_slot(date, time):
    query = text("""
        SELECT id 
        FROM schedule 
        WHERE slot_date = :date 
          AND slot_time = :time 
          AND status = 'Available'
    """)
    
    with engine.connect() as conn:
        res = conn.execute(query, {"date": date, "time": time}).fetchone()
    
    if res is None:
        return False
        
    return int(res.id)

@safe_db_query
def get_user_phone_by_id(tg_id: int):
    with engine.connect() as conn:
        return conn.execute(text("SELECT phone_number FROM users WHERE tg_id = :tg_id"), {"tg_id" : tg_id}).fetchone().phone_number
    
@safe_db_query
def get_date_times(date):
    with engine.connect() as conn:
        r = conn.execute(text("SELECT slot_time FROM schedule WHERE slot_date = :date and status = 'Available'"), {'date' : date}).mappings()
        
    if r is None:
        return False
    
    return r

@safe_db_query
def get_services():
    with engine.connect() as conn:
        r = conn.execute(text("SELECT id, name, duration FROM services")).mappings()
    return r

@safe_db_query
def get_slot_id(date, time):
    with engine.connect() as conn:
        r = conn.execute(text("SELECT id FROM schedule WHERE slot_date = :date AND slot_time = :time"), {'date' : date, 'time' : time}).fetchone()
    return r.id

@safe_db_query
def get_days_counts(month, year):
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
        
    return counts_by_day