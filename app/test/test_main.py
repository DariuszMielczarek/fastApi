from datetime import datetime
import jwt
import pytest
from starlette import status
from starlette.testclient import TestClient
from client_management_package import SECRET_KEY, ALGORITHM
from app.main.main import app
from memory_package import get_orders_count, add_order, \
    add_client, Client, set_calls_count
from memory_package.in_memory_db import clear_db, open_dbs, close_dbs
from order_package import Order


test_client = TestClient(app)


order1 = Order(id=0, description='Order1', creation_date=datetime.now(), client_id=None)
order2 = Order(id=1, description='Order2', creation_date=datetime.now(), client_id=None)
name1 = "Client"
name2 = "Test"
client1 = Client(name=name1, password='abc')
client2 = Client(name=name2, password='abc')


def local_add_client(client: Client):
    open_dbs()
    client_id = add_client(client)
    close_dbs()
    return client_id


def local_add_order(order: Order):
    open_dbs()
    order_id = add_order(order)
    close_dbs()
    return order_id


@pytest.fixture(autouse=True)
def reset_db_status():
    clear_db()
    set_calls_count(0)


def test_send_app_info_should_return_ok_response():
    response = test_client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()['message'] == 'Success'


def test_send_app_info_should_send_back_cookies_sent_by_client():
    cookies_value = "test_cookies"
    test_client.cookies.set("ads_id", cookies_value)
    response = test_client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["query_or_ads_id"] == cookies_value


def test_send_app_info_should_send_back_correct_number_of_orders():
    response = test_client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["tasks_count"] == get_orders_count()
    local_add_order(order1)
    local_add_order(order2)
    response = test_client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["tasks_count"] == get_orders_count()


def test_send_app_info_should_return_ok_response_when_correct_global_dependency_key():
    headers = {'key': 'key'}
    response = test_client.get("/", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()['message'] == 'Success'


def test_send_app_info_should_return_401_status_code_when_incorrect_global_dependency_key():
    headers = {'key': 'yek'}
    response = test_client.get("/", headers=headers)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_send_app_info_should_return_middleware_calls_counted_in_header():
    loop_count = 10
    for i in range(loop_count):
        test_client.get("/")
    response = test_client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert int(response.headers['calls_count']) == loop_count + 1


def test_real_login_should_return_valid_token():
    local_add_client(client1)
    form = {"username": client1.name, "password": client1.password}
    response = test_client.post("/token", data=form)
    token = response.json()['access_token']
    decoded_token = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert response.status_code == status.HTTP_200_OK
    assert decoded_token['sub'] == client1.name


def test_real_login_should_return_404_status_code_when_username_is_incorrect():
    local_add_client(client1)
    form = {"username": client2.name, "password": client1.password}
    response = test_client.post("/token", data=form)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_real_login_should_return_401_status_code_when_password_is_incorrect():
    local_add_client(client1)
    form = {"username": client1.name, "password": 'xyz'}
    response = test_client.post("/token", data=form)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_static_file_endpoint_with_test_image_should_return_ok_response():
    response = test_client.get("/static/test_image.png")
    assert response.status_code == status.HTTP_200_OK


def test_static_file_endpoint_should_return_404_status_code_when_static_file_does_not_exist():
    response = test_client.get("/static/test_image2.png")
    assert response.status_code == status.HTTP_404_NOT_FOUND
