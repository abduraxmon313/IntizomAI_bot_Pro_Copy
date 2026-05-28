from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Boolean
from datetime import datetime
from database.db import Base


class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    full_name = Column(String(255), nullable=True)
    is_super = Column(Boolean, default=False)  # Super admin (o'chrib bo'lmaydi)
    added_at = Column(DateTime, default=datetime.utcnow)