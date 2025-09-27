from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Float, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum

DATABASE_URL = "sqlite:///./frontline_support.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class UrgencyLevel(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class CaseStatus(enum.Enum):
    SUBMITTED = "submitted"
    TRIAGED = "triaged"
    ASSIGNED = "assigned"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class ServiceType(enum.Enum):
    MEDICAL = "medical"
    EMERGENCY = "emergency"
    SOCIAL = "social"
    ADMINISTRATIVE = "administrative"

class Citizen(Base):
    __tablename__ = "citizens"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, index=True)
    phone = Column(String(20))
    address = Column(Text)
    emergency_contact = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    cases = relationship("Case", back_populates="citizen")

class Service(Base):
    __tablename__ = "services"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    type = Column(Enum(ServiceType), nullable=False)
    department = Column(String(100))
    location = Column(String(200))
    capacity_per_hour = Column(Integer, default=10)
    available_hours = Column(String(50), default="9:00-17:00")
    contact_info = Column(String(200))
    is_emergency = Column(Boolean, default=False)
    
    cases = relationship("Case", back_populates="assigned_service")
    appointments = relationship("Appointment", back_populates="service")

class Case(Base):
    __tablename__ = "cases"
    
    id = Column(Integer, primary_key=True, index=True)
    citizen_id = Column(Integer, ForeignKey("citizens.id"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    urgency = Column(Enum(UrgencyLevel), default=UrgencyLevel.MEDIUM)
    status = Column(Enum(CaseStatus), default=CaseStatus.SUBMITTED)
    assigned_service_id = Column(Integer, ForeignKey("services.id"))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Triage information
    triage_notes = Column(Text)
    estimated_duration = Column(Integer)  # in minutes
    
    citizen = relationship("Citizen", back_populates="cases")
    assigned_service = relationship("Service", back_populates="cases")
    appointments = relationship("Appointment", back_populates="case")
    updates = relationship("CaseUpdate", back_populates="case")

class Appointment(Base):
    __tablename__ = "appointments"
    
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    
    scheduled_time = Column(DateTime(timezone=True), nullable=False)
    duration_minutes = Column(Integer, default=30)
    confirmation_sent = Column(Boolean, default=False)
    reminder_sent = Column(Boolean, default=False)
    
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    case = relationship("Case", back_populates="appointments")
    service = relationship("Service", back_populates="appointments")

class CaseUpdate(Base):
    __tablename__ = "case_updates"
    
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    
    message = Column(Text, nullable=False)
    update_type = Column(String(50))  # 'triage', 'assignment', 'booking', 'reminder', 'completion'
    agent_type = Column(String(50))   # 'triage', 'guidance', 'booking', 'follow_up', 'equity'
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    case = relationship("Case", back_populates="updates")

class SystemMetrics(Base):
    __tablename__ = "system_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(Integer, ForeignKey("services.id"))
    
    date = Column(DateTime(timezone=True), server_default=func.now())
    demand_count = Column(Integer, default=0)
    capacity_used = Column(Float, default=0.0)  # percentage
    avg_wait_time = Column(Float, default=0.0)  # in minutes
    satisfaction_score = Column(Float, default=0.0)  # 1-5 scale

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    Base.metadata.create_all(bind=engine)