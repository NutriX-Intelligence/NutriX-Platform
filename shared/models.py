from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from shared.db import Base

class HealthCheckModel(Base):
    __tablename__ = "health_check_stub"

    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String, nullable=False)
    checked_at = Column(DateTime(timezone=True), server_default=func.now())
