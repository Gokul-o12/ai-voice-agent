# import os
# import uuid # 🌟 NEW: Required for generating log_ids
# from dotenv import load_dotenv
# from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, JSON, Boolean, Index
# from sqlalchemy.orm import declarative_base, sessionmaker
# from sqlalchemy.sql import func
# from sqlalchemy.dialects.postgresql import UUID # 🌟 NEW: PostgreSQL UUID type

# # 1. Load the environment variables from .env
# load_dotenv()

# # 2. Fetch the Database URL
# SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

# # 3. Create the SQLAlchemy Engine with 🌟 CONNECTION POOLING 🌟
# engine = create_engine(
#     SQLALCHEMY_DATABASE_URL,
#     pool_size=20,          # Keep 20 connections open and ready at all times
#     max_overflow=10,       # Allow up to 10 extra connections during sudden traffic spikes
#     pool_timeout=30,       # If all 30 connections are busy, wait 30 seconds before dropping the request
#     pool_pre_ping=True     # Ping the DB before using a connection to ensure it hasn't dropped silently
# )

# # 4. Create a SessionLocal class for database transactions
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base = declarative_base()

# # ---------------------------------------------------------
# # DATABASE TABLES
# # ---------------------------------------------------------

# # 🌟 NEW: The Factory Tables
# class ProductionLine(Base):
#     __tablename__ = "production_lines"
#     line_id = Column(String(50), primary_key=True)
#     supervisor_name = Column(String(100))
#     supervisor_phone = Column(String(20))
#     preferred_language = Column(String(50), default="English")

# class DailyProductionLog(Base):
#     __tablename__ = "daily_production_logs"
#     log_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     line_id = Column(String(50), ForeignKey("production_lines.line_id"))
#     order_id = Column(String(50))
#     target_output = Column(Integer)
#     actual_output = Column(Integer)
#     ai_status = Column(String(50), default='Normal') # Normal, Investigating, Resolved
#     last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# # 1. The Caller (Employee, Customer, or Lead)
# class User(Base):
#     __tablename__ = "users"
#     id = Column(Integer, primary_key=True)
#     phone_number = Column(String, unique=True, nullable=False, index=True)
#     name = Column(String, nullable=True) 
#     role = Column(String, default="supervisor") # 🌟 NEW: Changed default to supervisor

# # 2. The Phone Call Itself
# class CallSession(Base):
#     __tablename__ = "call_sessions"
#     id = Column(Integer, primary_key=True)
#     call_sid = Column(String, unique=True, index=True) 
#     user_id = Column(Integer, ForeignKey("users.id"))
    
#     # 🌟 NEW: Link the call session directly to the specific factory log
#     log_id = Column(UUID(as_uuid=True), ForeignKey("daily_production_logs.log_id"), nullable=True)
    
#     status = Column(String, default="in_progress") 
#     start_time = Column(DateTime(timezone=True), server_default=func.now())

# # 3. The AI's Brain Dump (The Universal Storage)
# class CallAnalysisRecord(Base):
#     __tablename__ = "call_analysis"
#     id = Column(Integer, primary_key=True)
#     call_id = Column(Integer, ForeignKey("call_sessions.id"))
    
#     sentiment = Column(String, index=True) 
#     extracted_data = Column(JSON) 
#     unresolved_issues = Column(JSON) 
#     transcript = Column(JSON) 
    
#     requires_human_followup = Column(Boolean, default=False)
#     processed_at = Column(DateTime(timezone=True), server_default=func.now())

# Index('idx_analysis_sentiment', CallAnalysisRecord.sentiment)

# # Automatically create all tables in pgAdmin if they don't exist yet
# Base.metadata.create_all(bind=engine)

# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()


import os
import uuid
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, JSON, Boolean, Index, Enum
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
import enum

# 1. Load the environment variables from .env
load_dotenv()

# 2. Fetch the Database URL (Make sure this points to voice_v3 in your .env!)
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

# 3. Create the SQLAlchemy Engine with CONNECTION POOLING
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=20,          
    max_overflow=10,       
    pool_timeout=30,       
    pool_pre_ping=True     
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ---------------------------------------------------------
# ENUMS FOR STRICT STATE MANAGEMENT
# ---------------------------------------------------------
class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"

class AIStatus(str, enum.Enum):
    NORMAL = "NORMAL"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"

# ---------------------------------------------------------
# DATABASE TABLES
# ---------------------------------------------------------

# 1. The Production Line
class ProductionLine(Base):
    __tablename__ = "production_lines"
    line_id = Column(String(50), primary_key=True)
    supervisor_name = Column(String(100))
    supervisor_phone = Column(String(20))
    preferred_language = Column(String(50), default="English")
    
    # Relationship to fetch all orders for this line easily
    orders = relationship("ProductionOrder", back_populates="line", cascade="all, delete-orphan")

# 🌟 NEW: The specific Orders for each line (e.g., the 5 orders you mentioned)
class ProductionOrder(Base):
    __tablename__ = "production_orders"
    order_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    line_id = Column(String(50), ForeignKey("production_lines.line_id"))
    
    order_sequence = Column(Integer, nullable=False) # Order 1, Order 2, etc. so the AI knows what's next
    order_name = Column(String(100)) # e.g., "Assemble Chassis"
    
    # target_output = Column(Integer, default=0)
    # actual_output = Column(Integer, default=0)
    
    # State Management
    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING)
    blocker_reason = Column(String, nullable=True)
    ai_status = Column(Enum(AIStatus), default=AIStatus.NORMAL) # Tracks if AI needs to call about this order
    
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    line = relationship("ProductionLine", back_populates="orders")

# 2. The Caller (Employee, Customer, or Lead)
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    phone_number = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=True) 
    role = Column(String, default="supervisor")

# 3. The Phone Call Itself
class CallSession(Base):
    __tablename__ = "call_sessions"
    id = Column(Integer, primary_key=True)
    call_sid = Column(String, unique=True, index=True) 
    user_id = Column(Integer, ForeignKey("users.id"))
    
    # We now link the call session to the Line, as the AI might discuss multiple orders on one call
    line_id = Column(String(50), ForeignKey("production_lines.line_id"), nullable=True)
    
    status = Column(String, default="in_progress") 
    start_time = Column(DateTime(timezone=True), server_default=func.now())

# 4. The AI's Brain Dump (The Universal Storage)
class CallAnalysisRecord(Base):
    __tablename__ = "call_analysis"
    id = Column(Integer, primary_key=True)
    call_id = Column(Integer, ForeignKey("call_sessions.id"))
    
    sentiment = Column(String, index=True) 
    extracted_data = Column(JSON) # This will now store the array of order updates!
    unresolved_issues = Column(JSON) 
    transcript = Column(JSON) 
    
    requires_human_followup = Column(Boolean, default=False)
    processed_at = Column(DateTime(timezone=True), server_default=func.now())

Index('idx_analysis_sentiment', CallAnalysisRecord.sentiment)

# Automatically create all tables in pgAdmin if they don't exist yet
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()