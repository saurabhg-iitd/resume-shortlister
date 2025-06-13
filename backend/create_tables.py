from models import Base
from db import engine

def create_tables():
    # Drop existing tables first to ensure schema changes are applied
    Base.metadata.drop_all(bind=engine)
    # Create tables with the updated schema
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")

if __name__ == "__main__":
    create_tables() 