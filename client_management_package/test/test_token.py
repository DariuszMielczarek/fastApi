from datetime import datetime, timedelta
import jwt
import pytest
from app.main import exceptions
from client_management_package import SECRET_KEY, ALGORITHM, create_access_token


def test_create_access_token_should_return_valid_access_token():
    start_time = datetime.now()
    data_dict = {"sub": "Client1"}
    token = create_access_token(data_dict)
    decoded_data = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert decoded_data["sub"] == "Client1"
    assert datetime.fromtimestamp(decoded_data["exp"]) > start_time


def test_create_access_token_should_throw_exception_when_expires_delta_is_less_than_zero():
    data_dict = {"sub": "Client1"}
    with pytest.raises(exceptions.WrongDeltaException):
        create_access_token(data_dict, timedelta(-10))
