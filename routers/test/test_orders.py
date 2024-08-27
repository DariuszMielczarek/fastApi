from datetime import datetime
import jwt
import pytest
from starlette import status
from starlette.testclient import TestClient
from client_management_package import SECRET_KEY, ALGORITHM
from app.main.main import app
from memory_package import set_calls_count, InMemoryDb
from order_package import Order, OrderStatus
from commons import (client1, client2, local_add_order_to_db_and_client, local_add_order,
                     local_add_client)
import memory_package


test_client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_db_status():
    memory_package.reset_db()
    set_calls_count(0)


def test_swap_orders_client_should_change_task_owner():
    client_id1 = local_add_client(client1)
    order_id = local_add_order_to_db_and_client(client_id1, "order1")
    client_id2 = local_add_client(client2)
    params = {'client_id': client_id2}
    print("/orders/swap/" + str(order_id))
    response = test_client.post("/orders/swap/" + str(order_id), params=params)
    assert response.status_code == status.HTTP_201_CREATED
    assert len(memory_package.db.get_orders_by_client_id(client_id1)) == 0
    assert len(memory_package.db.get_orders_by_client_id(client_id2)) == 1
    assert memory_package.db.get_order_by_id(order_id).client_id == client_id2


def test_swap_orders_client_should_change_task_owner_and_create_new_client():
    client_id1 = local_add_client(client1)
    order_id = local_add_order_to_db_and_client(client_id1, "order1")
    new_client_id = client_id1 + 10
    params = {'client_id': new_client_id}
    response = test_client.post("/orders/swap/" + str(order_id), params=params)
    assert response.status_code == status.HTTP_201_CREATED
    assert memory_package.db.get_clients_count() == 2
    assert len(memory_package.db.get_orders_by_client_id(client_id1)) == 0
    assert len(memory_package.db.get_orders_by_client_name("New client" + str(new_client_id))) == 1


def test_swap_orders_client_should_return_404_status_code_when_order_does_not_exist():
    client_id1 = local_add_client(client1)
    order_id = local_add_order_to_db_and_client(client_id1, "order1")
    new_client_id = client_id1 + 10
    params = {'client_id': new_client_id}
    response = test_client.post("/orders/swap/" + str(order_id + 10), params=params)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_swap_orders_client_should_remove_owner_from_order_when_query_parameter_is_empty():
    client_id1 = local_add_client(client1)
    order_id = local_add_order_to_db_and_client(client_id1, "order1")
    response = test_client.post("/orders/swap/" + str(order_id))
    assert response.status_code == status.HTTP_201_CREATED
    assert len(memory_package.db.get_orders_by_client_id(client_id1)) == 0
    assert memory_package.db.get_order_by_id(order_id).client_id is None


def test_delete_order_should_remove_order():
    client_id = local_add_client(client1)
    order_id1 = local_add_order_to_db_and_client(client_id, "order1")
    local_add_order_to_db_and_client(client_id, "order2")
    response = test_client.delete("/orders/" + str(order_id1))
    assert response.status_code == status.HTTP_200_OK
    assert len(memory_package.db.get_orders_by_client_id(client_id)) == 1
    assert memory_package.db.get_orders_count() == 1


def test_delete_order_should_return_404_status_code_if_order_does_not_exist():
    client_id = local_add_client(client1)
    local_add_order_to_db_and_client(client_id, "order1")
    order_id2 = local_add_order_to_db_and_client(client_id, "order2")
    response = test_client.delete("/orders/" + str(order_id2 + 1))
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_delete_orders_of_ids_should_return_removed_orders_count_and_remove_all_orders_when_query_parameters_not_filled():  # noqa: E501
    client_id = local_add_client(client1)
    local_add_order_to_db_and_client(client_id, "order1")
    local_add_order_to_db_and_client(client_id, "order2")
    local_add_order_to_db_and_client(client_id, "order3")
    response = test_client.delete("/orders/remove")
    assert response.status_code == status.HTTP_200_OK
    assert memory_package.db.get_orders_count() == 0
    assert response.json()['removed_count'] == 3


def test_delete_orders_of_ids_should_remove_all_orders_with_ids_between_given():
    client_id = local_add_client(client1)
    local_add_order_to_db_and_client(client_id, "order1")
    local_add_order_to_db_and_client(client_id, "order2")
    local_add_order_to_db_and_client(client_id, "order3")
    local_add_order_to_db_and_client(client_id, "order4")
    params = {"first": 1, "last": 2}
    response = test_client.delete("/orders/remove", params=params)
    assert response.status_code == status.HTTP_200_OK
    assert memory_package.db.get_orders_count() == 2
    assert response.json()['removed_count'] == 2


def test_delete_orders_of_ids_should_return_412_status_code_when_first_id_greater_than_last_id_query_parameter():
    params = {"first": 2, "last": 1}
    response = test_client.delete("/orders/remove", params=params)
    assert response.status_code == status.HTTP_412_PRECONDITION_FAILED


def test_get_orders_by_current_client_should_return_current_clients_orders():
    client_id1 = local_add_client(client1)
    local_add_order_to_db_and_client(client_id1, "order1")
    local_add_order_to_db_and_client(client_id1, "order2")
    encoded_token = jwt.encode({'sub': client1.name}, SECRET_KEY, algorithm=ALGORITHM)
    header = {"Authorization": f"Bearer {encoded_token}"}
    response = test_client.get("/orders/get/current", headers=header)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) == 2


def test_get_orders_by_current_client_should_return_401_status_code_when_incorrect_header():
    local_add_client(client1)
    encoded_token = jwt.encode({'sub': client1.name}, SECRET_KEY, algorithm=ALGORITHM)
    header = {"Authorization": f"Bear {encoded_token}"}
    response = test_client.get("/orders/get/current", headers=header)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_orders_by_current_client_should_return_400_status_code_when_no_username_in_header():
    encoded_token = jwt.encode({'subs': client1.name}, SECRET_KEY, algorithm=ALGORITHM)
    header = {"Authorization": f"Bearer {encoded_token}"}
    response = test_client.get("/orders/get/current", headers=header)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_get_orders_by_current_client_should_return_406_status_code_when_token_is_incorrect():
    encoded_token = jwt.encode({'sub': client1.name}, SECRET_KEY + 'A', algorithm=ALGORITHM)
    header = {"Authorization": f"Bearer {encoded_token}"}
    response = test_client.get("/orders/get/current", headers=header)
    assert response.status_code == status.HTTP_406_NOT_ACCEPTABLE


def test_get_orders_by_current_client_should_return_404_status_code_when_client_does_not_exist():
    encoded_token = jwt.encode({'sub': client1.name}, SECRET_KEY, algorithm=ALGORITHM)
    header = {"Authorization": f"Bearer {encoded_token}"}
    response = test_client.get("/orders/get/current", headers=header)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_get_orders_should_return_accepted_status_code():
    encoded_token = jwt.encode({'subs': client1.name}, SECRET_KEY, algorithm=ALGORITHM)
    header = {"Authorization": f"Bearer {encoded_token}"}
    response = test_client.get("/orders/get/all", headers=header)
    assert response.status_code == status.HTTP_202_ACCEPTED


def test_get_orders_should_return_empty_list_when_no_orders_created():
    encoded_token = jwt.encode({'subs': client1.name}, SECRET_KEY, algorithm=ALGORITHM)
    header = {"Authorization": f"Bearer {encoded_token}"}
    response = test_client.get("/orders/get/all", headers=header)
    assert response.status_code == status.HTTP_202_ACCEPTED
    assert len(response.json()) == 0


def test_get_orders_should_return_list_with_created_orders():
    client_id = local_add_client(client1)
    local_add_order_to_db_and_client(client_id, "order1")
    local_add_order_to_db_and_client(client_id, "order2")
    encoded_token = jwt.encode({'subs': client1.name}, SECRET_KEY, algorithm=ALGORITHM)
    header = {"Authorization": f"Bearer {encoded_token}"}
    response = test_client.get("/orders/get/all", headers=header)
    assert response.status_code == status.HTTP_202_ACCEPTED
    orders = response.json()
    assert len(orders) == 2
    assert orders[0]['description'] == "order1"


def test_get_orders_counts_from_header_should_return_list_with_counted_given_users_orders():
    client_id1 = local_add_client(client1)
    local_add_order_to_db_and_client(client_id1, "order1")
    local_add_order_to_db_and_client(client_id1, "order2")
    client_id2 = local_add_client(client2)
    headers = {'clients-ids': str(client_id1) + ',' + str(client_id2)}
    response = test_client.get("/orders/get/headers", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    orders_count = response.json()['clients_orders_count']
    assert len(orders_count) == 2
    assert orders_count == [2, 0]


def test_get_orders_counts_from_header_should_return_list_ignoring_users_that_do_not_exist():
    client_id1 = local_add_client(client1)
    local_add_order_to_db_and_client(client_id1, "order1")
    client_id2 = local_add_client(client2)
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
    client_id1 = local_add_client(client1)
    client_id2 = local_add_client(client2)
    local_add_order_to_db_and_client(client_id1, "order1")
    local_add_order_to_db_and_client(client_id2, "order2")
    local_add_order_to_db_and_client(client_id1, "order3")
    response = test_client.get("/orders/get/" + str(client_id1))
    assert response.status_code == status.HTTP_200_OK
    orders = response.json()['orders']
    assert len(orders) == 2
    assert orders[0]['description'] == "order1"
    assert orders[1]['description'] == "order3"


def test_get_orders_by_client_should_return_empty_list_when_no_users_orders_created():
    client_id1 = local_add_client(client1)
    client_id2 = local_add_client(client2)
    local_add_order_to_db_and_client(client_id2, "order1")
    response = test_client.get("/orders/get/" + str(client_id1))
    assert response.status_code == status.HTTP_200_OK
    orders = response.json()['orders']
    assert len(orders) == 0


def test_get_orders_by_client_should_return_404_status_code_when_client_id_is_incorrect():
    response = test_client.get("/orders/get/10")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_get_orders_by_status_should_return_list_with_created_orders_with_given_status():
    client_id1 = local_add_client(client1)
    local_add_order_to_db_and_client(client_id1, "order1")
    client_id2 = local_add_client(client2)
    local_add_order_to_db_and_client(client_id2, "order2", OrderStatus.complete)
    local_add_order_to_db_and_client(client_id1, "order3", OrderStatus.complete)
    response = test_client.get("/orders/get/status/" + OrderStatus.complete.value)
    assert response.status_code == status.HTTP_200_OK
    orders = response.json()['orders']
    assert len(orders) == 2
    assert orders[0]['description'] == "order2"
    assert orders[1]['description'] == "order3"


def test_get_orders_by_status_should_return_empty_list_when_no_created_orders_with_given_status():
    local_add_client(client1)
    client_id2 = local_add_client(client2)
    local_add_order_to_db_and_client(client_id2, "order1")
    response = test_client.get("/orders/get/status/" + OrderStatus.complete.value)
    assert response.status_code == status.HTTP_200_OK
    orders = response.json()['orders']
    assert len(orders) == 0


def test_get_orders_should_return_422_status_code_when_status_is_incorrect():
    response = test_client.get("/orders/get/status/cancelled")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_process_next_order_should_return_first_order_id():
    client_id = local_add_client(client1)
    order_id = local_add_order_to_db_and_client(client_id, "order1")
    response = test_client.post("/orders/process")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()['orderId'] == order_id


def test_process_next_order_should_change_order_status():
    client_id = local_add_client(client1)
    order_id = local_add_order_to_db_and_client(client_id, "order1")
    response = test_client.post("/orders/process")
    assert response.status_code == status.HTTP_200_OK
    order = memory_package.db.get_order_by_id(order_id)
    assert order.status == OrderStatus.in_progress


def test_process_next_order_should_return_404_status_code_when_no_awaiting_order():
    response = test_client.post("/orders/process")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    client_id = local_add_client(client1)
    local_add_order_to_db_and_client(client_id, "order1")
    response = test_client.post("/orders/process")
    assert response.status_code == status.HTTP_200_OK
    response = test_client.post("/orders/process")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_process_order_of_id_should_return_processed_order_id_and_message():
    client_id = local_add_client(client1)
    order_id1 = local_add_order_to_db_and_client(client_id, "order1")
    response = test_client.post("/orders/process/" + str(order_id1))
    assert response.status_code == status.HTTP_200_OK
    assert response.json()['orderId'] == order_id1
    assert response.json()['message'] == 'Success'
    order_id2 = local_add_order_to_db_and_client(client_id, "order2")
    new_success_msg = 'Other success message!'
    params = {"resp_success": new_success_msg}
    response = test_client.post("/orders/process/" + str(order_id2), params=params)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()['orderId'] == order_id2
    assert response.json()['message'] == new_success_msg


def test_process_order_of_id_should_return_409_status_code_and_message_when_order_status_is_not_received():
    client_id = local_add_client(client1)
    order_id = local_add_order_to_db_and_client(client_id, "order1", OrderStatus.in_progress)
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


def test_create_order_should_return_created_response():
    client_id = local_add_client(client1)
    order_data = {"description": "order1", "time": 44}
    response = test_client.post("/orders/" + str(client_id), json=order_data)
    assert response.status_code == status.HTTP_201_CREATED


def test_create_order_should_save_order_with_given_data():
    client_id = local_add_client(client1)
    order_data = {"description": "order1", "time": 44}
    response = test_client.post("/orders/" + str(client_id), json=order_data)
    assert response.status_code == status.HTTP_201_CREATED
    assert memory_package.db.get_orders_count() == 1
    assert memory_package.db.get_clients_count() == 1
    clients_orders = memory_package.db.get_orders_by_client_id(client_id)
    assert len(clients_orders) == 1
    assert clients_orders[0].description == order_data['description']
    assert clients_orders[0].time == order_data['time']
    assert clients_orders[0].client_id == client_id


def test_create_order_should_create_new_client_when_client_with_given_client_id_does_not_exist():
    client_id = 100
    order_data = {"description": "order1", "time": 44}
    response = test_client.post("/orders/" + str(client_id), json=order_data)
    assert response.status_code == status.HTTP_201_CREATED
    assert memory_package.db.get_orders_count() == 1
    assert memory_package.db.get_clients_count() == 1
    clients_orders = memory_package.db.get_orders_by_client_name("New client100")
    assert len(clients_orders) == 1
    assert clients_orders[0].description == order_data['description']
    assert clients_orders[0].time == order_data['time']
    assert clients_orders[0].client_id == 1


def test_create_order_should_return_404_status_code_when_no_order_was_sent():
    client_id = local_add_client(client1)
    response = test_client.post("/orders/" + str(client_id))
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_create_order_should_return_422_status_code_when_json_body_is_invalid():
    client_id = local_add_client(client1)
    order_data = {"time": 44}
    response = test_client.post("/orders/" + str(client_id), json=order_data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
