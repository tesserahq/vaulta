from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import get_settings
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

settings = get_settings()

engine = create_engine(settings.database_url)
SQLAlchemyInstrumentor().instrument(
    enable_commenter=True, commenter_options={}, engine=engine
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
