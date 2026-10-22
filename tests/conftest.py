import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app  # noqa: E402
import db  # noqa: E402

ELIGIBLE = {"is_student": "yes", "age_18_25": "yes", "dating_app": "yes", "consent": "yes", "is_test": "1"}


@pytest.fixture
def app(tmp_path):
    return create_app(db_path=str(tmp_path / "test.db"))


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def con(app):
    c = db.connect(app.config["DB_PATH"])
    yield c
    c.close()


def enrol(client):
    """Go through consent as a marked test session; return the study code."""
    r = client.post("/consent", data=ELIGIBLE)
    assert r.status_code == 302, r.data
    m = re.search(r"/s/(P-[0-9A-F]{6})/intro", r.location)
    assert m, r.location
    return m.group(1)


def article_html(html):
    """The profile card markup only (photo, origin slot, text)."""
    m = re.search(r'<article class="profile-card".*?</article>', html, re.S)
    assert m
    return m.group(0)
