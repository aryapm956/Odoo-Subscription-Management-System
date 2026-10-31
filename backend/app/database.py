from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
    echo=False,
)

# Enable WAL mode and foreign keys for SQLite
if "sqlite" in settings.database_url:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def ensure_sqlite_schema() -> None:
    """Apply small additive migrations for existing SQLite databases."""
    if "sqlite" not in str(engine.url):
        return
    inspector = inspect(engine)
    if "discount_rules" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("discount_rules")}
    if "plan_id" not in columns:
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE discount_rules ADD COLUMN plan_id INTEGER REFERENCES plans(id)")
            )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
