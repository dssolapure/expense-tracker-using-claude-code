import os
import tempfile
import pytest
import database.db as db_module
from database.db import init_db
import app as flask_app


@pytest.fixture()
def app():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    original_path = db_module.DB_PATH
    db_module.DB_PATH = db_path

    flask_app.app.config["TESTING"] = True

    with flask_app.app.app_context():
        init_db()

    yield flask_app.app

    db_module.DB_PATH = original_path
    os.unlink(db_path)


@pytest.fixture()
def client(app):
    return app.test_client()
