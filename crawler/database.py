from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
import os
import datetime
import time

Base = declarative_base()

class Announcement(Base):
    __tablename__ = 'announcements'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    published_time = Column(String(255))
    company_name = Column(String(500))
    location = Column(String(255))
    announcement_type = Column(String(255))
    pdf_path = Column(String(500), nullable=True) # <-- Thêm trường này
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

def get_engine():
    db_user = os.getenv('DB_USER', 'crawler_user')
    db_password = os.getenv('DB_PASSWORD', 'your_password')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_NAME', 'dkkd_data')
    
    connection_string = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    return create_engine(connection_string)

def init_db():
    engine = get_engine()
    
    # Retry loop because DB might not be fully started yet
    retries = 5
    while retries > 0:
        try:
            Base.metadata.create_all(engine)
            Session = sessionmaker(bind=engine)
            return Session()
        except Exception as e:
            print(f"Database not ready yet, retrying in 5 seconds... ({retries} retries left)")
            time.sleep(5)
            retries -= 1
            
    raise Exception("Could not connect to database after multiple retries.")
