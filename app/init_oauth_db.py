"""Initialize NOVA's OAuth PostgreSQL schema as a deployment migration.

Run with: python -m app.init_oauth_db
"""
from app.oauth_store import initialize_schema
from app.canva_store import initialize_canva_schema


if __name__ == "__main__":
    initialize_schema()
    initialize_canva_schema()
    print("NOVA OAuth database schema initialized.")
