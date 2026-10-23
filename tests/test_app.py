import os
import tempfile
import pytest
from app import app as flask_app, db, User, KycCase

@pytest.fixture()
def client():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    flask_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{db_path}",
        SECRET_KEY="test-secret",
        UPLOAD_FOLDER=tempfile.mkdtemp(),
    )
    with flask_app.app_context():
        db.drop_all()
        db.create_all()
        admin = User(username="admin_test", role="admin")
        admin.set_password("testpass")
        reviewer = User(username="reviewer_test", role="reviewer")
        reviewer.set_password("testpass")
        db.session.add_all([admin, reviewer])
        db.session.commit()
    with flask_app.test_client() as client:
        yield client
    with flask_app.app_context():
        db.session.remove()
        db.drop_all()
    os.close(db_fd)
    os.unlink(db_path)

def login(client, username="admin_test", password="testpass"):
    return client.post("/login", data={"username": username, "password": password}, follow_redirects=True)

def test_login_and_dashboard(client):
    response = login(client)
    assert response.status_code == 200
    assert b"Dashboard" in response.data

def test_cases_requires_login(client):
    response = client.get("/cases")
    assert response.status_code == 302
    assert "/login" in response.location

def test_reviewer_cannot_view_audit_page(client):
    login(client, "reviewer_test")
    response = client.get("/audit")
    assert response.status_code == 403

def test_admin_can_create_case(client):
    login(client)
    response = client.post("/cases/new", data={
        "customer_name": "Demo Customer",
        "customer_email": "demo@example.com",
        "document_type": "Passport",
        "notes": "Test case",
        "due_date": "2026-12-31",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Demo Customer" in response.data
    with flask_app.app_context():
        assert KycCase.query.filter_by(customer_name="Demo Customer").count() == 1
