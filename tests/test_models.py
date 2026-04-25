# -*- coding: utf-8 -*-
import os, sys, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.models import Base, LabelBatch, LabelEntry

@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()

def test_create_batch(session):
    batch = LabelBatch(batch_name="テスト", label_mode="normal")
    session.add(batch)
    session.commit()
    assert batch.id is not None

def test_create_entry(session):
    batch = LabelBatch(batch_name="テスト", label_mode="normal")
    session.add(batch)
    session.flush()
    entry = LabelEntry(
        batch_id=batch.id,
        sort_order=0,
        client_id=None,
        company_name="株式会社テスト",
        postal_code="100-0001",
        address1="東京都千代田区",
        address2="",
        title="部長",
        person_name="山田太郎",
    )
    session.add(entry)
    session.commit()
    assert entry.id is not None
    assert entry.client_id is None

def test_cascade_delete(session):
    batch = LabelBatch(batch_name="削除テスト", label_mode="normal")
    session.add(batch)
    session.flush()
    entry = LabelEntry(batch_id=batch.id, sort_order=0,
                       company_name="テスト", client_id=None)
    session.add(entry)
    session.commit()
    session.delete(batch)
    session.commit()
    assert session.query(LabelEntry).count() == 0
