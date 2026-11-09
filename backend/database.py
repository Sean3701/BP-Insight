from pathlib import Path
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = Path(os.getenv('VC_DATA_DIR', str(ROOT / 'data'))).resolve()
DB_PATH = DATA_ROOT / "database" / "vc_intelligence.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(f"sqlite:///{DB_PATH.as_posix()}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass

def initialize_database():
    from backend import models  # noqa: F401: register tables
    from backend import workspace_models  # noqa: F401
    Base.metadata.create_all(bind=engine)
