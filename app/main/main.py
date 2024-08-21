import os
import sys
from datetime import timedelta
from typing import Annotated
import uvicorn
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from starlette import status
from starlette.requests import Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))  # noqa: E402
import memory_package
import routers
from client_management_package import hash_password, EXPIRE_TIME_TOKEN, verify_password, create_access_token, Token
from dependencies_package.main.dependencies import (query_or_cookie_extractor, global_dependency_verify_key_common,
                                                    dependency_with_yield)
from app.main.exceptions import NoOrderException
from memory_package import logger, get_client_by_name, increment_calls_count
from memory_package.in_memory_db import ClientInDb
from app.main.tags import Tags

description = """
FastApiQueueApp possibilities:
## Clients management
####    Update client data
####    Delete one client
####    Delete multiple clients
####    Get clients
####    Add client without orders

## Security management
####    Fake login to account
####    Fake login and setting account data
####    Real login with JWT Token

## Orders management
####    Swap order's owners
####    Delete multiple orders
####    Delete one order
####    Get orders:
      by status
      by multiple clients
      by one client
      all
      by current client (with tokens)
####    Process next order
####    Process any order
####    Create new order
"""

tags_metadata = [
    {
        "name": Tags.clients,
        "description": "Operations with clients & with login + authentication",
    },
    {
        "name": "process",
        "description": "Processing orders which simulates usage of asynchronous code",
    },
    {
        "name": "create",
        "description": "Creating new orders and sometimes also new clients",
    },
    {
        "name": "get",
        "description": "Getting orders list with response body",
    },
    {
        "name": "remove",
        "description": "Deleting existing orders",
    },
    {
        "name": "update",
        "description": "Now, only swapping owners, maybe more later...",
    },
]

app = FastAPI(dependencies=[Depends(global_dependency_verify_key_common), Depends(dependency_with_yield)],
              title='FastApiQueueApp',
              description=description,
              summary='Test - training app with FastApi',
              version='v1.5.1',
              contact={
                  'name': 'DM',
                  'email': '240752@edu.p.lodz.pl',
              },
              license_info={
                  'name': 'License: ???',
                  'identifier': 'MIT'
              },
              openapi_tags=tags_metadata,
              openapi_url="/api/v1/openapi.json",
              redoc_url=None
              )
app.include_router(routers.client_router)
app.include_router(routers.order_router)
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

origins = [
    "http://localhost",
    "https://localhost",
    "http://localhost:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def count_calls_and_send_counter(request: Request, call_next):
    logger.info('Middleware called before request call')
    response = await call_next(request)
    if request.url.path != '/favicon.ico':
        response.headers["calls_count"] = str(await increment_calls_count())
    return response


@app.exception_handler(NoOrderException)
async def no_order_exception_handler(request: Request, exc: NoOrderException):
    return JSONResponse(
        status_code=404,
        content={"message": exc.message if exc.message is not None else "ID: " + str(exc.order_id) + ") No order"},
    )


@app.get('/', tags=[Tags.order_get])
def send_app_info(query_or_ads_id: Annotated[str, Depends(query_or_cookie_extractor)] = None):
    """
    Get info if app works and how many tasks are currently saved

    **query_or_ads_id**: query data or, if empty, cookie data
    """
    if query_or_ads_id is not None:
        logger.info('App info function query/cookies value: ' + query_or_ads_id)
    else:
        logger.info('App info function called without query/cookies value')
    return JSONResponse(status_code=status.HTTP_200_OK,
                        content={"message": "Success", "query_or_ads_id": query_or_ads_id,
                                 "tasks_count": len(memory_package.get_orders_db())})


@app.post("/token")
async def real_login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    client: ClientInDb = get_client_by_name(form_data.username)
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incorrect username")
    hashed_password = hash_password(form_data.password)
    if not verify_password(client.password, hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")

    access_token_expires = timedelta(minutes=EXPIRE_TIME_TOKEN)
    access_token = create_access_token(
        data={"sub": client.name}, expires_delta=access_token_expires
    )

    return Token(access_token=access_token, token_type="bearer")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
