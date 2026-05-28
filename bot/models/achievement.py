from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database.db import Base


class Achievement(Base):
    """Unlocked achievement record (one row per user per badge)."""
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    code = Column(String(40), nullable=False)        # e.g. "streak_7", "level_5"
    title = Column(String(80), nullable=False)
    icon = Column(String(8), default="🏆")
    rarity = Column(String(16), default="common")    # common | rare | epic | legendary
    unlocked_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="achievements")
