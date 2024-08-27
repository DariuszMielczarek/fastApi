import sys
from unittest.mock import patch
import jwt
import pytest
from fastapi import HTTPException
from starlette import status
from starlette.testclient import TestClient
from client_management_package import SECRET_KEY, ALGORITHM
from client_package.client import Client
from dependencies_package import (global_dependency_verify_key_common, dependency_with_yield,
                                  delete_of_ids_common_parameters, query_parameter_extractor, query_or_cookie_extractor,
                                  verify_key_common, get_current_client)
from app.main.main import app
from memory_package import set_calls_count
import memory_package

test_client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_db_status():
    memory_package.reset_db()
    set_calls_count(0)


def local_add_client(client: Client):
    memory_package.db.open_dbs()
    client_id = memory_package.db.add_client(client.name, client.password, client.photo, client.orders)
    memory_package.db.close_dbs()
    return client_id


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
    with (patch("dependencies_package.main.dependencies.memory_package.db.open_dbs") as mock_open_dbs,
          patch("dependencies_package.main.dependencies.memory_package.db.close_dbs") as mock_close_dbs,
          patch("dependencies_package.main.dependencies.memory_package.db.get_clients_db") as mock_get_clients_db,
          patch("dependencies_package.main.dependencies.memory_package.db.get_orders_db") as mock_get_orders_db):
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


@pytest.mark.asyncio
async def test_get_current_client_should_return_expected_client():
    name = 'name1'
    client = Client(name=name, password='abc')
    local_add_client(client)
    fake_token = {'sub': name}
    fake_encoded_token = jwt.encode(fake_token, SECRET_KEY, algorithm=ALGORITHM)
    returned_client = await get_current_client(fake_encoded_token)
    assert returned_client.name == client.name


@pytest.mark.asyncio
async def test_get_current_client_should_throw_exception_when_no_username_in_token():
    name = 'name1'
    fake_token = {'not_sub': name}
    fake_encoded_token = jwt.encode(fake_token, SECRET_KEY, algorithm=ALGORITHM)
    with pytest.raises(HTTPException) as exc_info:
        await get_current_client(fake_encoded_token)
    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_get_current_client_should_throw_exception_when_token_is_invalid():
    name = 'name1'
    fake_token = {'sub': name}
    with pytest.raises(HTTPException) as exc_info:
        await get_current_client(str(fake_token))
    assert exc_info.value.status_code == status.HTTP_406_NOT_ACCEPTABLE


@pytest.mark.asyncio
async def test_get_current_client_should_throw_exception_when_no_client_with_username_from_token():
    name = 'name1'
    client = Client(name=name, password='abc')
    local_add_client(client)
    fake_token = {'sub': name+'2'}
    fake_encoded_token = jwt.encode(fake_token, SECRET_KEY, algorithm=ALGORITHM)
    with pytest.raises(HTTPException) as exc_info:
        await get_current_client(fake_encoded_token)
    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
