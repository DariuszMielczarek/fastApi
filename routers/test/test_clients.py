from datetime import datetime

import pytest
from starlette import status
from starlette.testclient import TestClient
from client_management_package.main.passwords import pwd_context, hash_password
from app.main.main import app
from memory_package import Client, open_dbs, add_client, close_dbs, get_password_from_client_by_name, get_next_order_id, \
    add_order, add_order_to_client, get_client_by_id, get_orders_count, get_clients_count, get_order_by_id, clear_db, \
    set_calls_count
from order_package import Order


test_client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_db_status():
    clear_db()
    set_calls_count(0)


order1 = Order(id=0, description='Order1', creation_date=datetime.now(), client_id=None)
order2 = Order(id=1, description='Order2', creation_date=datetime.now(), client_id=None)
name1 = "Client"
name2 = "Test"
name3 = "333"
password_list = ["abc", "def"]
client1 = Client(name=name1, password=hash_password('abc'))
client2 = Client(name=name2, password=hash_password('abc'))
client3 = Client(name=name3, password=hash_password('abc'))


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


def test_change_client_password_should_update_password_to_correct_values():
    local_add_client(client1)
    new_password = "ABCD"
    params = {"password": new_password}
    headers = {'verification-key': 'key'}
    response = test_client.patch("/clients/update/password/" + client1.name, params=params, headers=headers)
    assert response.status_code == status.HTTP_200_OK
    assert pwd_context.verify(new_password, get_password_from_client_by_name(client1.name))


def test_change_client_password_should_return_client_data_after_password_change():
    local_add_client(client1)
    header = {'verification-key': 'key'}
    params = {'password': 'new'}
    response = test_client.patch("/clients/update/password/"+client1.name, headers=header, params=params)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()['name'] == client1.name


def test_change_client_password_should_return_401_status_code_when_incorrect_verification_key():
    local_add_client(client1)
    header = {'verification-key': 'key2'}
    response = test_client.patch("/clients/update/password/"+client1.name, headers=header)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_change_client_password_should_return_404_status_code_when_name_does_not_exist():
    local_add_client(client1)
    header = {'verification-key': 'key'}
    response = test_client.patch("/clients/update/password/"+client2.name, headers=header)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_change_client_password_should_return_client_data_and_not_change_password_when_password_not_given():
    local_add_client(client1)
    header = {'verification-key': 'key'}
    response = test_client.patch("/clients/update/password/"+client1.name, headers=header)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()['name'] == client1.name
    assert pwd_context.verify('abc', get_password_from_client_by_name(client1.name))


def test_change_client_data_should_return_updated_client_data():
    local_add_client(client1)
    params = {"name": "NewClientName"}
    response = test_client.put("/clients/update/all/" + client1.name, params=params)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()['name'] == "NewClientName"


def test_change_client_data_should_update_name_and_password_to_correct_values():
    local_add_client(client1)
    new_client_name = "NewClientName"
    new_password1 = "ABCD"
    new_password2 = "ABCDEF"
    params = {"name": new_client_name, "password": new_password1}
    response = test_client.put("/clients/update/all/" + client1.name, params=params)
    assert response.status_code == status.HTTP_200_OK
    assert get_password_from_client_by_name(new_client_name) == new_password1
    params = {"password": new_password2}
    response = test_client.put("/clients/update/all/" + new_client_name, params=params)
    assert response.status_code == status.HTTP_200_OK
    assert get_password_from_client_by_name("NewClientName") == new_password2


def test_change_client_data_should_return_404_status_code_when_name_not_in_database():
    local_add_client(client1)
    params = {"name": "NewClientName", "password": "ABCD"}
    response = test_client.put("/clients/update/all/" + client1.name + "1", params=params)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_fake_login_should_return_client_data_if_name_and_password_are_correct():
    local_add_client(client1)
    data = {"name": client1.name, "password": client1.password}
    response = test_client.post("clients/fake_login/", data=data)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()['name'] == client1.name


def test_fake_login_should_return_401_status_code_when_password_is_incorrect():
    local_add_client(client1)
    data = {"name": client1.name, "password": client1.password + "1"}
    response = test_client.post("clients/fake_login/", data=data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_fake_login_should_return_404_status_code_when_name_is_incorrect():
    local_add_client(client1)
    data = {"name": client1.name + "1", "password": client1.password}
    response = test_client.post("clients/fake_login/", data=data)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_fake_login_and_set_photo_should_return_updated_client_data():
    local_add_client(client1)
    data = {"name": client1.name, "password": client1.password}
    files = {'file': open('./static/test_image.png', 'rb')}
    response = test_client.post("clients/login_set_photo", data=data, files=files)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()['name'] == client1.name
    assert response.json()['photo'] != str()


def test_fake_login_and_set_photo_should_return_404_status_code_when_no_file_was_sent():
    local_add_client(client1)
    data = {"name": client1.name, "password": client1.password}
    response = test_client.post("clients/login_set_photo", data=data)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_fake_login_and_set_photo_should_return_401_status_code_when_password_is_incorrect():
    local_add_client(client1)
    data = {"name": client1.name, "password": client1.password + "1"}
    files = {'file': open('./static/test_image.png', 'rb')}
    response = test_client.post("clients/login_set_photo", data=data, files=files)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_fake_login_and_set_photo_should_return_404_status_code_when_name_is_incorrect():
    local_add_client(client1)
    data = {"name": client1.name + "1", "password": client1.password}
    files = {'file': open('./static/test_image.png', 'rb')}
    response = test_client.post("clients/login_set_photo", data=data, files=files)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_delete_clients_of_ids_should_return_removed_clients_count_and_remove_all_orders_when_query_parameters_not_filled():
    client_id = local_add_client(client1)
    order_id1 = get_next_order_id()
    new_order = Order(id=order_id1, description="order1", client_id=client_id, creation_date=datetime.now())
    local_add_order(new_order)
    add_order_to_client(new_order, get_client_by_id(client_id))
    order_id2 = get_next_order_id()
    new_order = Order(id=order_id2, description="order2", client_id=client_id, creation_date=datetime.now())
    local_add_order(new_order)
    add_order_to_client(new_order, get_client_by_id(client_id))
    response = test_client.delete("/clients/remove")
    assert response.status_code == status.HTTP_200_OK
    assert get_orders_count() == 0
    assert get_clients_count() == 0
    assert response.json()['removed_count'] == 1


def test_delete_clients_of_ids_should_remove_all_orders_with_ids_between_given():
    local_add_client(client1)
    client_id2 = local_add_client(client2)
    local_add_client(client3)
    params = {"first": client_id2, "last": client_id2}
    response = test_client.delete("/clients/remove", params=params)
    assert response.status_code == status.HTTP_200_OK
    assert get_clients_count() == 2
    assert response.json()['removed_count'] == 1


def test_delete_clients_of_ids_should_return_412_status_code_when_first_id_greater_than_last_id_query_parameter():
    local_add_client(client1)
    params = {"first": 2, "last": 1}
    response = test_client.delete("/clients/remove", params=params)
    assert response.status_code == status.HTTP_412_PRECONDITION_FAILED


def test_delete_clients_of_ids_should_remove_all_removed_client_orders():
    client_id1 = local_add_client(client1)
    client_id2 = local_add_client(client2)
    order_id1 = get_next_order_id()
    new_order = Order(id=order_id1, description="order1", client_id=client_id1, creation_date=datetime.now())
    local_add_order(new_order)
    add_order_to_client(new_order, get_client_by_id(client_id1))
    order_id2 = get_next_order_id()
    new_order = Order(id=order_id2, description="order2", client_id=client_id2, creation_date=datetime.now())
    local_add_order(new_order)
    add_order_to_client(new_order, get_client_by_id(client_id2))
    order_id3 = get_next_order_id()
    new_order = Order(id=order_id3, description="order3", client_id=client_id1, creation_date=datetime.now())
    local_add_order(new_order)
    add_order_to_client(new_order, get_client_by_id(client_id1))
    params = {"first": client_id1, "last": client_id1}
    response = test_client.delete("/clients/remove", params=params)
    assert response.status_code == status.HTTP_200_OK
    assert get_orders_count() == 1
    assert get_order_by_id(order_id1) is None
    assert get_order_by_id(order_id2) is not None


def test_get_clients_should_return_correct_clients_data():
    clients = [client1, client2]
    for client in clients:
        local_add_client(client)
    response = test_client.get("/clients/")
    assert response.status_code == status.HTTP_200_OK
    for client, response_client in zip(clients, response.json()):
        assert client.name == response_client['name']


def test_get_clients_should_return_correct_number_of_clients():
    clients = [client1, client2]
    for client in clients:
        local_add_client(client)
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


def test_get_clients_should_return_422_status_code_when_query_parameter_value_incorrect():
    params = {"count": -1}
    response = test_client.get("/clients/", params=params)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_add_client_without_task_should_return_added_client_data():
    params = {"client_name1": name1, "client_name2": name2, "passes": password_list}
    response = test_client.post("/clients/add", params=params)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {'name': name1 + name2, 'orders': [], 'photo': ''}


def test_add_client_without_task_should_return_422_status_code_when_client_name1_parameter_not_filled():
    params = {"client_name2": name2, "passes": password_list}
    response = test_client.post("/clients/add", params=params)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_add_client_without_task_should_add_client_with_correct_name():
    params = {"client_name1": name1, "client_name2": name2}
    response = test_client.post("/clients/add", params=params)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()['name'] == name1 + name2
    params = {"client_name1": name1}
    response = test_client.post("/clients/add", params=params)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()['name'] == name1


def test_add_client_without_task_should_add_client_with_correct_password():
    params = {"client_name1": name1, "passes": password_list}
    response = test_client.post("clients/add", params=params)
    assert response.status_code == status.HTTP_200_OK
    assert pwd_context.verify("".join(password_list), get_password_from_client_by_name(name1))
    params = {"client_name1": name2}
    response = test_client.post("/clients/add", params=params)
    assert response.status_code == status.HTTP_200_OK
    assert pwd_context.verify("123", get_password_from_client_by_name(name2))


def test_add_client_without_task_should_return_409_status_code_when_client_name_not_unique():
    params = {"client_name1": name1}
    response = test_client.post("/clients/add", params=params)
    assert response.status_code == status.HTTP_200_OK
    params = {"client_name1": name1}
    response = test_client.post("/clients/add", params=params)
    assert response.status_code == status.HTTP_409_CONFLICT


def test_add_client_without_task_should_return_422_status_code_when_query_parameters_values_incorrect():
    params = {"client_name1": "ClientNameThatIsDefinitelyLongerThanExpected"}
    response = test_client.post("/clients/add", params=params)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    params = {"client_name1": "A"}
    response = test_client.post("/clients/add", params=params)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
