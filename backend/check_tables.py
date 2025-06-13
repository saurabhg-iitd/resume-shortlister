from sqlalchemy import inspect
from db import engine
from models import Base

def check_tables():
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    print("Database tables found:")
    for table in tables:
        print(f"- {table}")
        columns = inspector.get_columns(table)
        print(f"  Columns: {len(columns)}")
        for column in columns:
            print(f"    - {column['name']} ({column['type']})")
    
    expected_tables = [table.__tablename__ for table in Base.__subclasses__()]
    print("\nExpected tables:", expected_tables)
    
    missing_tables = [table for table in expected_tables if table not in tables]
    if missing_tables:
        print("\nMissing tables:", missing_tables)
    else:
        print("\nAll expected tables are present in the database!")

if __name__ == "__main__":
    check_tables() 