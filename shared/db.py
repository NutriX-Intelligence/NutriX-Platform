import os
import logging
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
try:
    from dotenv import load_dotenv
    BASE_DIR = Path(__file__).resolve().parent.parent
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    BASE_DIR = Path(__file__).resolve().parent.parent
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

logger = logging.getLogger("shared.db")

DB_PATH = BASE_DIR / "dataset" / "nutrition_master.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

pg_user = os.environ.get("POSTGRES_USER", "nutrix")
pg_pass = os.environ.get("POSTGRES_PASSWORD", "nutties")
pg_db = os.environ.get("POSTGRES_DB", "nutrix_db")

DATABASE_URL = os.environ.get("DATABASE_URL", f"postgresql://{pg_user}:{pg_pass}@localhost:5432/{pg_db}")

# If running on local host outside docker, replace container host 'postgres' with 'localhost'
if "@postgres:" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("@postgres:", "@localhost:")

# Normalise Heroku-style postgres:// → postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = None

try:
    if DATABASE_URL.startswith("postgresql://"):
        logger.info(f"Connecting to PostgreSQL database...")
        # Verify the database connection synchronously
        temp_engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        with temp_engine.connect() as conn:
            pass
        engine = temp_engine
        logger.info("Successfully connected to PostgreSQL!")
    else:
        raise ValueError("SQLite fallback requested.")
except Exception as e:
    logger.warning(f"PostgreSQL connection failed ({e}). Falling back to SQLite database: {DB_PATH}")
    DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"
    engine = create_engine(
        DATABASE_URL, connect_args={"check_same_thread": False}
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
