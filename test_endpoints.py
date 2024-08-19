from datetime import datetime
import pytest
from starlette import status
from starlette.testclient import TestClient
from main import app, pwd_context
from memory_package import get_orders_count, add_order, orders_db, clients_db, \
    get_password_from_client_by_name, add_client, Client, get_orders_by_client_id, get_clients_count
from memory_package.in_memory_db import get_orders_by_client_name, get_next_order_id, add_order_to_client, \
    get_clients_by_ids, get_order_by_id, get_client_by_id, get_clients_db, get_orders_db, clear_db, open_dbs
from order_package import Order, OrderStatus

test_client = TestClient(app)

order1 = Order(id=0, description='Order1', creation_date=datetime.now(), client_id=None)
order2 = Order(id=1, description='Order2', creation_date=datetime.now(), client_id=None)
name1 = "Client"
name2 = "Test"
name3 = "333"
password_list = ["abc", "def"]
client1 = Client(name=name1, password='abc')
client2 = Client(name=name2, password='abc')
client3 = Client(name=name3, password='abc')


@pytest.fixture(autouse=True)
def reset_db_status():
    clear_db()


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
    add_order(order1)
    add_order(order2)
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
    print("LOLZ")
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


def test_change_client_data_should_return_updated_client_data():
    add_client(client1)
    params = {"name": "NewClientName"}
    response = test_client.put("/clients/update/all/" + client1.name, params=params)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()['name'] == "NewClientName"


def test_change_client_data_should_update_name_and_password_to_correct_values():
    add_client(client1)
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
    add_client(client1)
    params = {"name": "NewClientName", "password": "ABCD"}
    response = test_client.put("/clients/update/all/" + client1.name + "1", params=params)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_change_client_password_should_return_updated_client_data():
    add_client(client1)
    new_password = "ABCD"
    params = {"password": new_password}
    headers = {'verification-key': 'key'}
    response = test_client.patch("/clients/update/password/" + client1.name, params=params, headers=headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()['name'] == client1.name


def test_change_client_password_should_update_password_to_correct_values():
    add_client(client1)
    new_password = "ABCD"
    params = {"password": new_password}
    headers = {'verification-key': 'key'}
    response = test_client.patch("/clients/update/password/" + client1.name, params=params, headers=headers)
    assert response.status_code == status.HTTP_200_OK
    assert get_password_from_client_by_name(client1.name) == new_password


def test_change_client_password_should_return_404_status_code_exception_when_name_not_in_database():
    add_client(client1)
    new_password = "ABCD"
    params = {"password": new_password}
    headers = {'verification-key': 'key'}
    response = test_client.patch("/clients/update/" + client1.name + "1", params=params, headers=headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_fake_login_should_return_client_data_if_name_and_password_are_correct():
    add_client(client1)
    data = {"name": client1.name, "password": client1.password}
    response = test_client.post("/login/", data=data)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()['name'] == client1.name


def test_fake_login_should_return_401_status_code_when_password_is_incorrect():
    add_client(client1)
    data = {"name": client1.name, "password": client1.password + "1"}
    response = test_client.post("/login/", data=data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_fake_login_should_return_404_status_code_when_name_is_incorrect():
    add_client(client1)
    data = {"name": client1.name + "1", "password": client1.password}
    response = test_client.post("/login/", data=data)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_fake_login_and_set_photo_should_return_updated_client_data():
    add_client(client1)
    data = {"name": client1.name, "password": client1.password}
    files = {'file': open('test_image.png', 'rb')}
    response = test_client.post("/login/set_photo", data=data, files=files)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()['name'] == client1.name
    assert response.json()['photo'] != str()


def test_fake_login_and_set_photo_should_return_404_status_code_when_no_file_was_sent():
    add_client(client1)
    data = {"name": client1.name, "password": client1.password}
    response = test_client.post("/login/set_photo", data=data)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_fake_login_and_set_photo_should_return_401_status_code_when_password_is_incorrect():
    add_client(client1)
    data = {"name": client1.name, "password": client1.password + "1"}
    files = {'file': open('test_image.png', 'rb')}
    response = test_client.post("/login/set_photo", data=data, files=files)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_fake_login_and_set_photo_should_return_404_status_code_when_name_is_incorrect():
    add_client(client1)
    data = {"name": client1.name + "1", "password": client1.password}
    files = {'file': open('test_image.png', 'rb')}
    response = test_client.post("/login/set_photo", data=data, files=files)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_create_order_should_return_created_response():
    client_id = add_client(client1)
    order_data = {"description": "order1", "time": 44}
    response = test_client.post("/orders/" + str(client_id), json=order_data)
    assert response.status_code == status.HTTP_201_CREATED


def test_create_order_should_save_order_with_given_data():
    client_id = add_client(client1)
    order_data = {"description": "order1", "time": 44}
    response = test_client.post("/orders/" + str(client_id), json=order_data)
    assert response.status_code == status.HTTP_201_CREATED
    assert get_orders_count() == 1
    assert get_clients_count() == 1
    clients_orders = get_orders_by_client_id(client_id)
    assert len(clients_orders) == 1
    assert clients_orders[0].description == order_data['description']
    assert clients_orders[0].time == order_data['time']
    assert clients_orders[0].client_id == client_id


def test_create_order_should_create_new_client_when_client_with_given_client_id_does_not_exist():
    client_id = 100
    order_data = {"description": "order1", "time": 44}
    response = test_client.post("/orders/" + str(client_id), json=order_data)
    assert response.status_code == status.HTTP_201_CREATED
    assert get_orders_count() == 1
    assert get_clients_count() == 1
    clients_orders = get_orders_by_client_name("New client100")
    assert len(clients_orders) == 1
    assert clients_orders[0].description == order_data['description']
    assert clients_orders[0].time == order_data['time']
    assert clients_orders[0].client_id == client_id


def test_create_order_should_return_404_status_code_when_no_order_was_sent():
    client_id = add_client(client1)
    response = test_client.post("/orders/" + str(client_id))
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_create_order_should_return_422_status_code_when_json_body_is_invalid():
    client_id = add_client(client1)
    order_data = {"time": 44}
    response = test_client.post("/orders/" + str(client_id), json=order_data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_process_next_order_should_return_first_order_id():
    client_id = add_client(client1)
    order_id = get_next_order_id()
    new_order = Order(id=order_id, description="order1", client_id=client_id, creation_date=datetime.now())
    add_order(new_order)
    add_order_to_client(new_order, get_clients_by_ids([client_id])[0])
    response = test_client.post("/orders/process")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()['orderId'] == order_id


def test_process_next_order_should_change_order_status():
    client_id = add_client(client1)
    order_id = get_next_order_id()
    time = 2
    new_order = Order(id=order_id, time=time, description="order1", client_id=client_id, creation_date=datetime.now())
    add_order(new_order)
    add_order_to_client(new_order, get_clients_by_ids([client_id])[0])
    response = test_client.post("/orders/process")
    assert response.status_code == status.HTTP_200_OK
    order = get_order_by_id(order_id)
    assert order.status == OrderStatus.in_progress


def test_process_next_order_should_return_404_status_code_when_no_awaiting_order():
    response = test_client.post("/orders/process")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    client_id = add_client(client1)
    order_id = get_next_order_id()
    new_order = Order(id=order_id, description="order1", client_id=client_id, creation_date=datetime.now())
    add_order(new_order)
    add_order_to_client(new_order, get_clients_by_ids([client_id])[0])
    response = test_client.post("/orders/process")
    assert response.status_code == status.HTTP_200_OK
    response = test_client.post("/orders/process")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_process_order_of_id_should_return_processed_order_id_and_message():
    client_id = add_client(client1)
    order_id = get_next_order_id()
    new_order = Order(id=order_id, description="order1", client_id=client_id, creation_date=datetime.now())
    add_order(new_order)
    add_order_to_client(new_order, get_clients_by_ids([client_id])[0])
    response = test_client.post("/orders/process/" + str(order_id))
    assert response.status_code == status.HTTP_200_OK
    assert response.json()['orderId'] == order_id
    assert response.json()['message'] == 'Success'
    order_id = get_next_order_id()
    new_order = Order(id=order_id, description="order2", client_id=client_id, creation_date=datetime.now())
    add_order(new_order)
    add_order_to_client(new_order, get_clients_by_ids([client_id])[0])
    new_success_msg = 'Other success message!'
    params = {"resp_success": new_success_msg}
    response = test_client.post("/orders/process/" + str(order_id), params=params)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()['orderId'] == order_id
    assert response.json()['message'] == new_success_msg


def test_process_order_of_id_should_return_409_status_code_and_message_when_order_status_is_not_received():
    client_id = add_client(client1)
    order_id = get_next_order_id()
    new_order = Order(id=order_id, description="order1", client_id=client_id,
                      creation_date=datetime.now(), status=OrderStatus.in_progress)
    add_order(new_order)
    add_order_to_client(new_order, get_clients_by_ids([client_id])[0])
    response = test_client.post("/orders/process/" + str(order_id))
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()['detail']['message'] == "Order does not await for process"
    new_fail_msg = 'Other failure message!'
    fail_msg_json_data = {"resp_fail2": new_fail_msg}
    response = test_client.post("/orders/process/" + str(order_id), json=fail_msg_json_data)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()['detail']['message'] == new_fail_msg


def test_process_order_of_id_should_return_404_status_code_and_message_when_order_does_not_exist():
    response = test_client.post("/orders/process/0")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()['message'] == "No such order"
    new_fail_msg = 'Other failure message!'
    fail_msg_json_data = {"resp_fail1": new_fail_msg}
    response = test_client.post("/orders/process/1", json=fail_msg_json_data)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()['message'] == new_fail_msg


def test_process_order_of_id_should_return_422_status_code_when_incorrect_order_id_value():
    response = test_client.post("/orders/process/-6")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_get_orders_should_return_accepted_status_code():
    response = test_client.get("/orders/get/all")
    assert response.status_code == status.HTTP_202_ACCEPTED


def test_get_orders_should_return_empty_list_when_no_orders_created():
    response = test_client.get("/orders/get/all")
    assert response.status_code == status.HTTP_202_ACCEPTED
    assert len(response.json()) == 0


def test_get_orders_should_return_list_with_created_orders():
    client_id = add_client(client1)
    order_id = get_next_order_id()
    new_order = Order(id=order_id, description="order1", client_id=client_id, creation_date=datetime.now())
    add_order(new_order)
    add_order_to_client(new_order, get_clients_by_ids([client_id])[0])
    order_id = get_next_order_id()
    new_order = Order(id=order_id, description="order2", client_id=client_id, creation_date=datetime.now())
    add_order(new_order)
    add_order_to_client(new_order, get_clients_by_ids([client_id])[0])
    response = test_client.get("/orders/get/all")
    assert response.status_code == status.HTTP_202_ACCEPTED
    orders = response.json()
    assert len(orders) == 2
    assert orders[0]['description'] == "order1"


def test_get_orders_counts_from_header_should_return_list_with_counted_given_users_orders():
    client_id1 = add_client(client1)
    order_id = get_next_order_id()
    new_order = Order(id=order_id, description="order1", client_id=client_id1, creation_date=datetime.now())
    add_order(new_order)
    add_order_to_client(new_order, get_clients_by_ids([client_id1])[0])
    order_id = get_next_order_id()
    new_order = Order(id=order_id, description="order2", client_id=client_id1, creation_date=datetime.now())
    add_order(new_order)
    add_order_to_client(new_order, get_clients_by_ids([client_id1])[0])
    client_id2 = add_client(client2)
    headers = {'clients-ids': str(client_id1) + ',' + str(client_id2)}
    response = test_client.get("/orders/get/headers", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    orders_count = response.json()['clients_orders_count']
    assert len(orders_count) == 2
    assert orders_count == [2, 0]


def test_get_orders_counts_from_header_should_return_list_ignoring_users_that_do_not_exist():
    client_id1 = add_client(client1)
    order_id = get_next_order_id()
    new_order = Order(id=order_id, description="order1", client_id=client_id1, creation_date=datetime.now())
    add_order(new_order)
    add_order_to_client(new_order, get_clients_by_ids([client_id1])[0])
    client_id2 = add_client(client2)
    headers = {'clients-ids': str(client_id1) + ',1555,' + str(client_id2)}
    response = test_client.get("/orders/get/headers", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    orders_count = response.json()['clients_orders_count']
    assert len(orders_count) == 2
    assert orders_count == [1, 0]


def test_get_orders_counts_from_header_should_return_404_status_code_when_all_ids_are_incorrect():
    headers = {'clients-ids': '0,1,1000'}
    response = test_client.get("/orders/get/headers", headers=headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_get_orders_counts_from_header_should_return_404_status_code_when_header_is_in_wrong_format():
    headers = {'clients-ids': '0,1,1000,,,aaa'}
    response = test_client.get("/orders/get/headers", headers=headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_get_orders_counts_from_header_should_return_404_status_code_when_header_is_empty():
    response = test_client.get("/orders/get/headers")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_get_orders_by_client_should_return_list_with_created_users_orders():
    client_id = add_client(client1)
    order_id = get_next_order_id()
    new_order = Order(id=order_id, description="order1", client_id=client_id, creation_date=datetime.now())
    add_order(new_order)
    add_order_to_client(new_order, get_clients_by_ids([client_id])[0])
    order_id = get_next_order_id()
    new_order = Order(id=order_id, description="order2", client_id=client_id + 1, creation_date=datetime.now())
    add_order(new_order)
    order_id = get_next_order_id()
    new_order = Order(id=order_id, description="order3", client_id=client_id, creation_date=datetime.now())
    add_order(new_order)
    add_order_to_client(new_order, get_clients_by_ids([client_id])[0])
    response = test_client.get("/orders/get/" + str(client_id))
    assert response.status_code == status.HTTP_200_OK
    orders = response.json()['orders']
    assert len(orders) == 2
    assert orders[0]['description'] == "order1"
    assert orders[1]['description'] == "order3"


def test_get_orders_by_client_should_return_empty_list_when_no_users_orders_created():
    client_id = add_client(client1)
    order_id = get_next_order_id()
    new_order = Order(id=order_id, description="order2", client_id=client_id + 1, creation_date=datetime.now())
    add_order(new_order)
    response = test_client.get("/orders/get/" + str(client_id))
    assert response.status_code == status.HTTP_200_OK
    orders = response.json()['orders']
    assert len(orders) == 0


def test_get_orders_by_client_should_return_404_status_code_when_client_id_is_incorrect():
    response = test_client.get("/orders/get/0")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_get_orders_by_status_should_return_list_with_created_orders_with_given_status():
    client_id = add_client(client1)
    order_id = get_next_order_id()
    new_order = Order(id=order_id, description="order1", client_id=client_id, creation_date=datetime.now())
    add_order(new_order)
    add_order_to_client(new_order, get_clients_by_ids([client_id])[0])
    order_id = get_next_order_id()
    new_order = Order(id=order_id, description="order2", client_id=client_id + 1,
                      creation_date=datetime.now(), status=OrderStatus.complete)
    add_order(new_order)
    order_id = get_next_order_id()
    new_order = Order(id=order_id, description="order3", client_id=client_id,
                      creation_date=datetime.now(), status=OrderStatus.complete)
    add_order(new_order)
    add_order_to_client(new_order, get_clients_by_ids([client_id])[0])
    response = test_client.get("/orders/get/status/" + OrderStatus.complete.value)
    assert response.status_code == status.HTTP_200_OK
    orders = response.json()['orders']
    assert len(orders) == 2
    assert orders[0]['description'] == "order2"
    assert orders[1]['description'] == "order3"


def test_get_orders_by_status_should_return_empty_list_when_no_created_orders_with_given_status():
    client_id = add_client(client1)
    order_id = get_next_order_id()
    new_order = Order(id=order_id, description="order2", client_id=client_id + 1, creation_date=datetime.now())
    add_order(new_order)
    response = test_client.get("/orders/get/status/" + OrderStatus.complete.value)
    assert response.status_code == status.HTTP_200_OK
    orders = response.json()['orders']
    assert len(orders) == 0


def test_get_orders_should_return_422_status_code_when_status_is_incorrect():
    response = test_client.get("/orders/get/status/cancelled")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_delete_order_should_remove_order():
    client_id = add_client(client1)
    order_id1 = get_next_order_id()
    new_order = Order(id=order_id1, description="order1", client_id=client_id, creation_date=datetime.now())
    add_order(new_order)
    add_order_to_client(new_order, get_clients_by_ids([client_id])[0])
    order_id2 = get_next_order_id()
    new_order = Order(id=order_id2, description="order2", client_id=client_id, creation_date=datetime.now())
    add_order(new_order)
    add_order_to_client(new_order, get_clients_by_ids([client_id])[0])
    response = test_client.delete("/orders/" + str(order_id1))
    assert response.status_code == status.HTTP_200_OK
    assert len(get_orders_by_client_id(client_id)) == 1
    assert get_orders_count() == 1


def test_delete_order_should_return_404_status_code_if_order_does_not_exist():
    client_id = add_client(client1)
    order_id1 = get_next_order_id()
    new_order = Order(id=order_id1, description="order1", client_id=client_id, creation_date=datetime.now())
    add_order(new_order)
    add_order_to_client(new_order, get_clients_by_ids([client_id])[0])
    order_id2 = get_next_order_id()
    new_order = Order(id=order_id2, description="order2", client_id=client_id, creation_date=datetime.now())
    add_order(new_order)
    add_order_to_client(new_order, get_clients_by_ids([client_id])[0])
    response = test_client.delete("/orders/" + str(order_id2 + 1))
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_delete_orders_of_ids_should_return_removed_orders_count_and_remove_all_orders_when_query_parameters_not_filled():
    client_id = add_client(client1)
    order_id1 = get_next_order_id()
    new_order = Order(id=order_id1, description="order1", client_id=client_id, creation_date=datetime.now())
    add_order(new_order)
    add_order_to_client(new_order, get_client_by_id(client_id))
    order_id2 = get_next_order_id()
    new_order = Order(id=order_id2, description="order2", client_id=client_id, creation_date=datetime.now())
    add_order(new_order)
    add_order_to_client(new_order, get_client_by_id(client_id))
    order_id3 = get_next_order_id()
    new_order = Order(id=order_id3, description="order3", client_id=client_id, creation_date=datetime.now())
    add_order(new_order)
    add_order_to_client(new_order, get_client_by_id(client_id))
    response = test_client.delete("/orders/remove")
    assert response.status_code == status.HTTP_200_OK
    assert get_orders_count() == 0
    assert response.json()['removed_count'] == 3


def test_delete_orders_of_ids_should_remove_all_orders_with_ids_between_given():
    client_id = add_client(client1)
    order_id1 = get_next_order_id()
    new_order = Order(id=order_id1, description="order1", client_id=client_id, creation_date=datetime.now())
    add_order(new_order)
    add_order_to_client(new_order, get_clients_by_ids([client_id])[0])
    order_id2 = get_next_order_id()
    new_order = Order(id=order_id2, description="order2", client_id=client_id, creation_date=datetime.now())
    add_order(new_order)
    add_order_to_client(new_order, get_clients_by_ids([client_id])[0])
    order_id3 = get_next_order_id()
    new_order = Order(id=order_id3, description="order3", client_id=client_id, creation_date=datetime.now())
    add_order(new_order)
    add_order_to_client(new_order, get_clients_by_ids([client_id])[0])
    order_id4 = get_next_order_id()
    new_order = Order(id=order_id4, description="order3", client_id=client_id, creation_date=datetime.now())
    add_order(new_order)
    add_order_to_client(new_order, get_clients_by_ids([client_id])[0])
    params = {"first": 1, "last": 2}
    response = test_client.delete("/orders/remove", params=params)
    assert response.status_code == status.HTTP_200_OK
    assert get_orders_count() == 2
    assert response.json()['removed_count'] == 2


def test_delete_orders_of_ids_should_return_412_status_code_when_first_id_greater_than_last_id_query_parameter():
    client_id = add_client(client1)
    order_id1 = get_next_order_id()
    new_order = Order(id=order_id1, description="order1", client_id=client_id, creation_date=datetime.now())
    add_order(new_order)
    params = {"first": 2, "last": 1}
    response = test_client.delete("/orders/remove", params=params)
    assert response.status_code == status.HTTP_412_PRECONDITION_FAILED


def test_swap_orders_client_should_change_task_owner():
    client_id1 = add_client(client1)
    order_id1 = get_next_order_id()
    new_order = Order(id=order_id1, description="order1", client_id=client_id1, creation_date=datetime.now())
    add_order(new_order)
    add_order_to_client(new_order, get_client_by_id(client_id1))
    client_id2 = add_client(client2)
    params = {'client_id': client_id2}
    response = test_client.post("/orders/swap/" + str(order_id1), params=params)
    assert response.status_code == status.HTTP_201_CREATED
    assert len(get_orders_by_client_id(client_id1)) == 0
    assert len(get_orders_by_client_id(client_id2)) == 1
    assert get_order_by_id(order_id1).client_id == client_id2


def test_swap_orders_client_should_change_task_owner_and_create_new_client():
    client_id1 = add_client(client1)
    order_id1 = get_next_order_id()
    new_order = Order(id=order_id1, description="order1", client_id=client_id1, creation_date=datetime.now())
    add_order(new_order)
    add_order_to_client(new_order, get_client_by_id(client_id1))
    new_client_id = client_id1 + 10
    params = {'client_id': new_client_id}
    response = test_client.post("/orders/swap/" + str(order_id1), params=params)
    assert response.status_code == status.HTTP_201_CREATED
    assert get_clients_count() == 2
    assert len(get_orders_by_client_id(client_id1)) == 0
    assert len(get_orders_by_client_name("New client" + str(new_client_id))) == 1


def test_swap_orders_client_should_return_404_status_code_when_order_does_not_exist():
    client_id1 = add_client(client1)
    order_id1 = get_next_order_id()
    new_order = Order(id=order_id1, description="order1", client_id=client_id1, creation_date=datetime.now())
    add_order(new_order)
    add_order_to_client(new_order, get_client_by_id(client_id1))
    new_client_id = client_id1 + 10
    params = {'client_id': new_client_id}
    response = test_client.post("/orders/swap/" + str(order_id1 + 10), params=params)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_swap_orders_client_should_remove_owner_from_order_when_query_parameter_is_empty():
    client_id1 = add_client(client1)
    order_id1 = get_next_order_id()
    new_order = Order(id=order_id1, description="order1", client_id=client_id1, creation_date=datetime.now())
    add_order(new_order)
    add_order_to_client(new_order, get_client_by_id(client_id1))
    response = test_client.post("/orders/swap/" + str(order_id1))
    assert response.status_code == status.HTTP_201_CREATED
    assert len(get_orders_by_client_id(client_id1)) == 0
    assert get_order_by_id(order_id1).client_id is None


def test_delete_clients_of_ids_should_return_removed_clients_count_and_remove_all_orders_when_query_parameters_not_filled():
    client_id = add_client(client1)
    order_id1 = get_next_order_id()
    new_order = Order(id=order_id1, description="order1", client_id=client_id, creation_date=datetime.now())
    add_order(new_order)
    add_order_to_client(new_order, get_client_by_id(client_id))
    order_id2 = get_next_order_id()
    new_order = Order(id=order_id2, description="order2", client_id=client_id, creation_date=datetime.now())
    add_order(new_order)
    add_order_to_client(new_order, get_client_by_id(client_id))
    response = test_client.delete("/clients/remove")
    assert response.status_code == status.HTTP_200_OK
    assert get_orders_count() == 0
    assert get_clients_count() == 0
    assert response.json()['removed_count'] == 1


def test_delete_clients_of_ids_should_remove_all_orders_with_ids_between_given():
    add_client(client1)
    client_id2 = add_client(client2)
    add_client(client3)
    params = {"first": client_id2, "last": client_id2}
    response = test_client.delete("/clients/remove", params=params)
    assert response.status_code == status.HTTP_200_OK
    assert get_clients_count() == 2
    assert response.json()['removed_count'] == 1


def test_delete_clients_of_ids_should_return_412_status_code_when_first_id_greater_than_last_id_query_parameter():
    add_client(client1)
    params = {"first": 2, "last": 1}
    response = test_client.delete("/clients/remove", params=params)
    assert response.status_code == status.HTTP_412_PRECONDITION_FAILED


def test_delete_clients_of_ids_should_remove_all_removed_client_orders():
    client_id1 = add_client(client1)
    client_id2 = add_client(client2)
    order_id1 = get_next_order_id()
    new_order = Order(id=order_id1, description="order1", client_id=client_id1, creation_date=datetime.now())
    add_order(new_order)
    add_order_to_client(new_order, get_client_by_id(client_id1))
    order_id2 = get_next_order_id()
    new_order = Order(id=order_id2, description="order2", client_id=client_id2, creation_date=datetime.now())
    add_order(new_order)
    add_order_to_client(new_order, get_client_by_id(client_id2))
    order_id3 = get_next_order_id()
    new_order = Order(id=order_id3, description="order3", client_id=client_id1, creation_date=datetime.now())
    add_order(new_order)
    add_order_to_client(new_order, get_client_by_id(client_id1))
    params = {"first": client_id1, "last": client_id1}
    response = test_client.delete("/clients/remove", params=params)
    assert response.status_code == status.HTTP_200_OK
    assert get_orders_count() == 1
    assert get_order_by_id(order_id1) is None
    assert get_order_by_id(order_id2) is not None


# todo: change_client_password
# todo: get_orders_by_current_client
# todo: real_login
