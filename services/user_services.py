from sqlalchemy import text
from database import engine
from utils.decorators import safe_db_query

@safe_db_query
def user_exists_by_id(tg_id):
    with engine.connect() as conn:
        return conn.execute(text("SELECT * FROM users WHERE tg_id = :tg_id"), 
                            {"tg_id": tg_id}).fetchone()
    
@safe_db_query
def register_user(tg_id, name, phone):
    with engine.begin() as conn:
        try:
            conn.execute(text("INSERT INTO users (tg_id, name, phone_number) VALUES (:tg_id, :name, :phone) ON CONFLICT (tg_id) DO NOTHING"),
                     {"tg_id": tg_id, "name": name, "phone": phone})
        except:
            return False
    return True
