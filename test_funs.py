import sys
from unittest.mock import patch
import pytest
from fastapi import HTTPException
from starlette import status
from starlette.testclient import TestClient

from main import global_dependency_verify_key_common, dependency_with_yield, app, delete_of_ids_common_parameters, \
    query_parameter_extractor, query_or_cookie_extractor, verify_key_common
from memory_package import clear_db

test_client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_db_status():
    clear_db()


@pytest.mark.asyncio
async def test_global_dependency_verify_key_common_should_not_throw_exception_when_called_with_correct_key():
    try:
        await global_dependency_verify_key_common('test_key')
    except Exception as e:
        pytest.fail('Unexpected exception: ' + str(e))


@pytest.mark.asyncio
async def test_global_dependency_verify_key_common_should_throw_exception_when_called_with_incorrect_key():
    with pytest.raises(HTTPException) as exc_info:
        await global_dependency_verify_key_common('yek')
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "Invalid key from global dependency"


@pytest.mark.asyncio
async def test_dependency_with_yield_should_open_yield_close_and_open_dbs():
    with (patch("main.open_dbs") as mock_open_dbs, patch("main.close_dbs") as mock_close_dbs,
          patch("main.get_clients_db") as mock_get_clients_db,
          patch("main.get_orders_db") as mock_get_orders_db):
        mock_open_dbs.return_value = None
        mock_close_dbs.return_value = None
        mock_get_clients_db.return_value = "mocked_clients_db"
        mock_get_orders_db.return_value = "mocked_orders_db"

        generator = dependency_with_yield()
        async for clients_db, orders_db in generator:
            assert clients_db == "mocked_clients_db"
            assert orders_db == "mocked_orders_db"
        mock_open_dbs.assert_called_once()

        async for _ in generator:
            pass

        assert mock_open_dbs.call_count == 1
        assert mock_close_dbs.call_count == 1


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


@pytest.mark.asyncio
async def test_delete_of_ids_common_parameters_should_return_default_values_when_not_given():
    return_dict = await delete_of_ids_common_parameters()
    assert return_dict == {'first': 0, 'last': sys.maxsize}


@pytest.mark.asyncio
async def test_delete_of_ids_common_parameters_should_return_given_values():
    return_dict = await delete_of_ids_common_parameters(10, 111)
    assert return_dict == {'first': 10, 'last': 111}


def test_query_parameter_extractor_should_return_query_parameter():
    q = None
    return_q = query_parameter_extractor(q)
    assert return_q == q
    q = '1234'
    return_q = query_parameter_extractor(q)
    assert return_q == q


def test_query_or_cookie_extractor_should_return_q_when_given():
    q = '1234'
    ads_id = None
    return_q_or_ads_id = query_or_cookie_extractor(q, ads_id)
    assert return_q_or_ads_id == q
    ads_id = '9876'
    return_q_or_ads_id = query_or_cookie_extractor(q, ads_id)
    assert return_q_or_ads_id == q


def test_query_or_cookie_extractor_should_return_ads_id_when_q_not_given():
    q = None
    ads_id = None
    return_q_or_ads_id = query_or_cookie_extractor(q, ads_id)
    assert return_q_or_ads_id == ads_id
    q = None
    ads_id = '9876'
    return_q_or_ads_id = query_or_cookie_extractor(q, ads_id)
    assert return_q_or_ads_id == ads_id


@pytest.mark.asyncio
async def test_verify_key_common_should_return_key_when_called_with_correct_key():
    expected_key = 'key'
    returned_key = await verify_key_common(expected_key)
    assert returned_key == expected_key


@pytest.mark.asyncio
async def test_verify_key_common_should_throw_exception_when_called_with_incorrect_key():
    with pytest.raises(HTTPException) as exc_info:
        await verify_key_common('key2')
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "Invalid key"



# todo: hash_password
# todo: verify_password
# todo: create_access_token
# todo: get_current_client
