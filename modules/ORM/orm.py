from sqlalchemy import create_engine
from config import CONFIG
from core.logger.logger import LOG

SQLALCHEMY_DATABASE_URL = f"postgresql://{CONFIG.database_user}:{CONFIG.database_password}@{CONFIG.database_host}:{CONFIG.database_port}/{CONFIG.database_name}"

engine = create_engine(SQLALCHEMY_DATABASE_URL)

try:
    with engine.connect() as connection:
        LOG.info("Database connection established successfully.")
except Exception as e:
    LOG.error(f"Database connection failed: {e}")
    raise