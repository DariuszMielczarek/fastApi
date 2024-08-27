import pytest
from starlette import status
from starlette.testclient import TestClient
from app.main.main import app
import memory_package

test_client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_db_status():
    memory_package.reset_db()


def test_no_order_exception_handler_should_return_404_status_code_and_message():
    response = test_client.post("/orders/0")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"message": "ID: 0) No order"}
    response = test_client.post("/orders/process")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"message": "No awaiting order"}


def test_validation_exception_handler_should_return_422_status_code_and_message():
    response = test_client.post("/orders/non_existing_endpoint")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
