"""Initialize NOVA's OAuth PostgreSQL schema as a deployment migration.

Run with: python -m app.init_oauth_db
"""
from app.oauth_store import initialize_schema


if __name__ == "__main__":
    initialize_schema()
    print("NOVA OAuth database schema initialized.")
