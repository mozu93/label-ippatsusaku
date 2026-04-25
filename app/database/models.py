# -*- coding: utf-8 -*-
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, create_engine
)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker
import os, sys


def _get_db_path() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "label_ippatsusaku.db")


class Base(DeclarativeBase):
    pass


class LabelBatch(Base):
    __tablename__ = "label_batches"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    batch_name = Column(String(200), nullable=False)
    label_mode = Column(String(20), default="normal")
    pdf_path   = Column(String(500), default="")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    entries = relationship(
        "LabelEntry", back_populates="batch",
        cascade="all, delete-orphan",
        order_by="LabelEntry.sort_order",
    )


class LabelEntry(Base):
    __tablename__ = "label_entries"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    batch_id     = Column(Integer, ForeignKey("label_batches.id"), nullable=False)
    sort_order   = Column(Integer, default=0)
    client_id    = Column(Integer, nullable=True)
    company_name = Column(String(200), default="")
    postal_code  = Column(String(10), default="")
    address1     = Column(String(200), default="")
    address2     = Column(String(200), default="")
    title        = Column(String(100), default="")
    person_name  = Column(String(100), default="")
    entry_mode   = Column(String(20), default="inherit")

    batch = relationship("LabelBatch", back_populates="entries")


_engine = None
_Session = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(f"sqlite:///{_get_db_path()}", echo=False)
    return _engine


def init_db():
    Base.metadata.create_all(get_engine())


def get_session():
    global _Session
    if _Session is None:
        _Session = sessionmaker(bind=get_engine())
    return _Session()
