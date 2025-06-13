from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float, Date, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()

class SelectionTypeEnum(enum.Enum):
    FIXED = "FIXED"
    PERCENTAGE = "PERCENTAGE"

class JD(Base):
    __tablename__ = 'jds'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, default="Untitled Job")
    text = Column(Text, nullable=False)
    parsed_json = Column(Text)
    num_shortlist = Column(Integer, nullable=True)
    application_deadline = Column(Date, nullable=True)
    selection_type = Column('selection_type', Enum(SelectionTypeEnum), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    resumes = relationship("Resume", back_populates="jd")

class Resume(Base):
    __tablename__ = 'resumes'
    id = Column(Integer, primary_key=True)
    jd_id = Column(Integer, ForeignKey('jds.id'))
    s3_path = Column(String, nullable=False)
    name = Column(String)
    email = Column(String)
    phone = Column(String)
    linkedin = Column(String)
    location = Column(String)
    total_experience = Column(Float)
    relevant_experience = Column(Float)
    ai_score = Column(Float)
    parsed_json = Column(Text)
    openai_output = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    jd = relationship("JD", back_populates="resumes") 