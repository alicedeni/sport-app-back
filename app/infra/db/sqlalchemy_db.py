from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from config import config

_env = os.environ.get('FLASK_ENV', 'development')
_app_config = config.get(_env, config['default'])

if _app_config.DATABASE_URL:
    SQLALCHEMY_DATABASE_URI = _app_config.DATABASE_URL
else:
    SQLALCHEMY_DATABASE_URI = f"postgresql+psycopg2://{_app_config.DB_USER}:{_app_config.DB_PASSWORD}@{_app_config.DB_HOST}:{_app_config.DB_PORT}/{_app_config.DB_NAME}?client_encoding=utf8"

engine = create_engine(
    SQLALCHEMY_DATABASE_URI, 
    pool_pre_ping=True, 
    future=True,
    connect_args={
        'client_encoding': 'utf8',
        'options': '-c client_encoding=UTF8'
    }
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

Base = declarative_base()


def get_session():
    """Fast dependency-less session context manager."""
    return SessionLocal()
