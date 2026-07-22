from sqlalchemy import create_engine
import gspread
from bot_config import (DB_HOST, 
                    DB_USER, 
                    DB_PASSWORD, 
                    DB_NAME, 
                    DB_PORT,
                    GS_CREDS_PATH,
                    GS_NAME,
                    SCHEDULE_WORKSHEET)

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL, 
                       pool_pre_ping=True,
                       pool_recycle=900)

gc = gspread.service_account(filename=GS_CREDS_PATH)
sh = gc.open(GS_NAME)
schedule_ws = sh.worksheet(SCHEDULE_WORKSHEET)