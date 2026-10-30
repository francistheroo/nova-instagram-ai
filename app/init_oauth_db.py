"""Initialize NOVA's OAuth PostgreSQL schema as a deployment migration.

Run with: python -m app.init_oauth_db
"""
from app.oauth_store import initialize_schema
from app.canva_store import initialize_canva_schema
from app.dm_memory import initialize_schema as initialize_dm_memory_schema
from app.admin import initialize_admin_schema


if __name__ == "__main__":
    initialize_schema()
    initialize_canva_schema()
    initialize_dm_memory_schema()
    initialize_admin_schema()
    print("NOVA OAuth, Canva, 12-hour DM memory, and admin schemas initialized.")
