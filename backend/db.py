from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from urllib.parse import quote_plus

password = quote_plus("Y}}a(OKQMuS`Bjfv")
DATABASE_URL = os.getenv("DATABASE_URL", f"postgresql://pgsqladmin:{password}@psql1.dev-we.com:5432/hackathon")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) 