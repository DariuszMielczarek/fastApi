from datetime import datetime

import pytest
from starlette import status
from starlette.testclient import TestClient

from main import app
from memory_package import get_clients_count, get_orders_count, add_order, ordersDb, clientsDb, \
    get_password_from_client_by_name, add_client, Client
from order_package import Order

test_client = TestClient(app)

order1 = Order(id=0, description='Order1', creation_date=datetime.now(), client_id=None)
order2 = Order(id=1, description='Order2', creation_date=datetime.now(), client_id=None)
name1 = "Client"
name2 = "Test"
password_list = ["abc", "def"]
client1 = Client(name='Client1', password='abc')
client2 = Client(name='Client2', password='abc')


@pytest.fixture(autouse=True)
def reset_db_status():
    ordersDb.clear()
    clientsDb.clear()


def test_send_app_info_should_send_ok_response():
    response = test_client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()['message'] == 'Success'


def test_send_app_info_should_send_back_cookies_sent_by_client():
    cookies_value = "test_cookies"
    test_client.cookies.set("ads_id", cookies_value)
    response = test_client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["ads_id"] == cookies_value


def test_send_app_info_should_send_back_correct_number_of_orders():
    response = test_client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["tasks_count"] == get_orders_count()
    add_order(order1)
    add_order(order2)
    response = test_client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["tasks_count"] == get_orders_count()


def test_add_client_without_task_should_return_added_client_data():
    params = {"client_name1": name1, "client_name2": name2, "passes": password_list}
    response = test_client.post("/clients/add", params=params)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {'name': name1+name2, 'orders': [], 'photo': ''}


def test_add_client_without_task_should_return_422_when_client_name1_parameter_not_filled():
    params = {"client_name2": name2, "passes": password_list}
    response = test_client.post("/clients/add", params=params)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_add_client_without_task_should_add_client_with_correct_name():
    params = {"client_name1": name1, "client_name2": name2}
    response = test_client.post("/clients/add", params=params)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()['name'] == name1+name2
    params = {"client_name1": name1}
    response = test_client.post("/clients/add", params=params)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()['name'] == name1


def test_add_client_without_task_should_add_client_with_correct_password():
    params = {"client_name1": name1, "passes": password_list}
    response = test_client.post("clients/add", params=params)
    assert response.status_code == status.HTTP_200_OK
    assert get_password_from_client_by_name(name1) == "".join(password_list)
    params = {"client_name1": name2}
    response = test_client.post("/clients/add", params=params)
    assert response.status_code == status.HTTP_200_OK
    assert get_password_from_client_by_name(name2) == "123"


def test_add_client_without_task_should_return_409_when_client_name_not_unique():
    params = {"client_name1": name1}
    response = test_client.post("/clients/add", params=params)
    assert response.status_code == status.HTTP_200_OK
    params = {"client_name1": name1}
    response = test_client.post("/clients/add", params=params)
    assert response.status_code == status.HTTP_409_CONFLICT


def test_add_client_without_task_should_return_422_when_query_parameters_values_incorrect():
    params = {"client_name1": "ClientNameThatIsDefinitelyLongerThanExpected"}
    response = test_client.post("/clients/add", params=params)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    params = {"client_name1": "A"}
    response = test_client.post("/clients/add", params=params)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_get_clients_should_return_correct_clients_data():
    clients = [client1, client2]
    for client in clients:
        add_client(client)
    response = test_client.get("/clients/")
    assert response.status_code == status.HTTP_200_OK
    for client, response_client in zip(clients, response.json()):
        assert client.name == response_client['name']


def test_get_clients_should_return_correct_number_of_clients():
    clients = [client1, client2]
    for client in clients:
        add_client(client)
    params = {"count": len(clients) + 1}
    response = test_client.get("/clients/", params=params)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) == len(clients)
    params = {"count": len(clients)}
    response = test_client.get("/clients/", params=params)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) == len(clients)
    params = {"count": len(clients) - 1}
    response = test_client.get("/clients/", params=params)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) == len(clients) - 1


def test_get_clients_should_return_422_when_query_parameter_value_incorrect():
    params = {"count": -1}
    response = test_client.get("/clients/", params=params)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
