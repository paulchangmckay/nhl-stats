import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.database import get_connection, create_all_tables

conn = get_connection()
create_all_tables(conn)
conn.close()
print("Database ready at data/nhl_stats.db")
