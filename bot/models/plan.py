from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Date
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from database.db import Base


class PlanStatus(enum.Enum):
    pending = "pending"
    done = "done"
    failed = "failed"


class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(String(1000), nullable=True)
    scheduled_time = Column(String(10), nullable=True)   # "06:00" formatda
    plan_date = Column(Date, default=datetime.utcnow().date)
    status = Column(Enum(PlanStatus), default=PlanStatus.pending)
    score_value = Column(Integer, default=5)
    created_at = Column(DateTime, default=datetime.utcnow)
    notified_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="plans")
    score_logs = relationship("ScoreLog", back_populates="plan", cascade="all, delete")