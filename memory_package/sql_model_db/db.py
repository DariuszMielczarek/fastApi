from sqlmodel import create_engine


DATABASE_URL = 'postgresql+psycopg2://postgres:12345@localhost/fast_api_queue_app_with_sql_model'
engine = create_engine(url=DATABASE_URL, echo=False)
