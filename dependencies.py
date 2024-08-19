import sys
from typing import Annotated

import jwt
from fastapi import Header, HTTPException, Form, Depends, Cookie
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from starlette import status

from client_management_package import SECRET_KEY, ALGORITHM
from memory_package import get_client_by_name, orders_lock, open_dbs, get_clients_db, get_orders_db, close_dbs


class CommonQueryParamsClass:
    def __init__(self, name: Annotated[str, Form()], password: Annotated[str, Form()]):
        self.name = name
        self.password = password


async def verify_key_common(verification_key: Annotated[str, Header()]):
    if verification_key != "key":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid key")
    return verification_key


def query_parameter_extractor(q: str | None = None):
    return q


def query_or_cookie_extractor(q: Annotated[str | None, Depends(query_parameter_extractor)],
                              ads_id: Annotated[str | None, Cookie()] = None):
    return q if q else ads_id


async def delete_of_ids_common_parameters(first: int = 0, last: int = sys.maxsize):
    return {"first": first, "last": last}


CommonDependencyAnnotation = Annotated[dict, Depends(delete_of_ids_common_parameters)]


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def get_current_client(token: Annotated[str, Depends(oauth2_scheme)]):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No username in token",
                                headers={"WWW-Authenticate": "Bearer"})
    except InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail="Invalid token error",
                            headers={"WWW-Authenticate": "Bearer"})
    client = get_client_by_name(username)
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No client with given username",
                            headers={"WWW-Authenticate": "Bearer"})
    return client


async def global_dependency_verify_key_common(key: Annotated[str | None, Header()] = None):
    if key == "yek":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid key from global dependency")


async def dependency_with_yield():
    try:
        async with orders_lock:
            open_dbs()
            clients_db = get_clients_db()
            orders_db = get_orders_db()
        yield clients_db, orders_db
    except Exception:
        raise
    finally:
        close_dbs()
