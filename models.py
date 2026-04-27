import pg8000.dbapi
from sqlalchemy import create_engine, Column, Integer, String, JSON
from sqlalchemy.orm import declarative_base, sessionmaker

DB_USER = "postgres"
DB_PASS = "bhoomika2004"
DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "garages"

def create_database_if_not_exists():
    try:
        conn = pg8000.dbapi.connect(
            user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT, database="postgres"
        )
        conn.autocommit = True
        cursor = conn.cursor()
        cursor.execute(f"SELECT 1 FROM pg_database WHERE datname='{DB_NAME}'")
        exists = cursor.fetchone()
        if not exists:
            cursor.execute(f"CREATE DATABASE {DB_NAME}")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error during database pre-flight check: {e}")

create_database_if_not_exists()

DATABASE_URL = f"postgresql+pg8000://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Garage(Base):
    __tablename__ = "saved_garages"
    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, index=True)
    source_url = Column(String, unique=True, index=True)
    name = Column(String, nullable=False)
    location = Column(String, index=True)
    phone = Column(String)
    extra_data = Column(JSON, default={})

Base.metadata.create_all(bind=engine)