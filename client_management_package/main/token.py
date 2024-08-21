from datetime import timedelta, datetime
import jwt
from pydantic import BaseModel
from client_management_package.main.token_vars import EXPIRE_TIME_TOKEN, SECRET_KEY, ALGORITHM
from app.main.exceptions import WrongDeltaException


class Token(BaseModel):
    access_token: str
    token_type: str


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    if expires_delta and expires_delta < timedelta(0):
        raise WrongDeltaException('Expires delta is less than zero')
    to_encode = data.copy()
    expire = datetime.now() + expires_delta if expires_delta is not None \
        else datetime.now() + timedelta(EXPIRE_TIME_TOKEN)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
