import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

engine = create_engine(
    DATABASE_URL,
    # pool_pre_ping issues an extra round trip (a throwaway "ping" query) on
    # every connection checkout, on top of the request's real query. Against
    # a remote DB where each round trip already costs hundreds of ms, that
    # doubles latency for single-query endpoints. pool_recycle proactively
    # retires connections before Supabase's pooler would otherwise drop them
    # silently, without paying a ping on every request.
    pool_recycle=280
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        