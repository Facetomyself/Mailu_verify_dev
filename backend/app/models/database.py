"""数据库模型定义"""

from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import os

Base = declarative_base()

class TempEmail(Base):
    """临时邮箱模型"""
    __tablename__ = "temp_emails"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    domain = Column(String(100), nullable=False)
    password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    user_ip = Column(String(45))  # 支持IPv6
    user_agent = Column(Text)

    # 关联验证码
    codes = relationship("VerificationCode", back_populates="temp_email", cascade="all, delete-orphan")

class VerificationCode(Base):
    """验证码模型"""
    __tablename__ = "verification_codes"

    id = Column(Integer, primary_key=True, index=True)
    temp_email_id = Column(Integer, ForeignKey("temp_emails.id"), nullable=False)
    code = Column(String(20), nullable=False)
    sender = Column(String(255))
    subject = Column(Text)
    content = Column(Text)
    received_at = Column(DateTime, default=datetime.utcnow)
    is_read = Column(Boolean, default=False)

    # 关联临时邮箱
    temp_email = relationship("TempEmail", back_populates="codes")

class Domain(Base):
    """域名模型"""
    __tablename__ = "domains"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    is_active = Column(Boolean, default=True)
    max_emails = Column(Integer, default=100)
    created_at = Column(DateTime, default=datetime.utcnow)

class SystemStats(Base):
    """系统统计模型"""
    __tablename__ = "system_stats"

    id = Column(Integer, primary_key=True, index=True)
    total_emails = Column(Integer, default=0)
    active_emails = Column(Integer, default=0)
    total_codes = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# 数据库连接配置
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://user:password@localhost/mailu_codes")

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    """创建所有表"""
    Base.metadata.create_all(bind=engine)

def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
