import base64
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, HTTPException, UploadFile
from starlette import status
from starlette.responses import JSONResponse, Response

import memory_package
from client_management_package import hash_password
from dependencies import verify_key_common, CommonQueryParamsClass, CommonDependencyAnnotation
from memory_package import ClientOut, Client, get_clients_db, set_new_clients_db, logger, orders_lock, remove_client
from tags import Tags

client_router = APIRouter(prefix="/clients", tags=[Tags.clients])


@client_router.patch("/update/password/{client_name}",
              response_model=None, dependencies=[Depends(verify_key_common)])
async def change_client_password(client_name: Annotated[str, Path()],
                                 password: Annotated[str | None, Query()] = None) -> JSONResponse | ClientOut:
    client = memory_package.get_client_by_name(client_name)
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"message": "Wrong name"})
    client.password = password if password is not None else hash_password(client.password)
    return ClientOut(**client.model_dump())


@client_router.put("/update/all/{client_name}", response_model=None)
async def change_client_data(client_name: Annotated[str, Path()],
                             name: Annotated[str | None, Query()] = None,
                             password: Annotated[str | None, Query()] = None) -> JSONResponse | ClientOut:
    client = memory_package.get_client_by_name(client_name)
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"message": "Wrong name"})
    updated_client = Client(**client.model_dump())
    updated_client.name = name if name is not None else updated_client.name
    updated_client.password = password if password is not None else updated_client.password
    clients_db = get_clients_db()
    for i, client in enumerate(clients_db):
        if client.name == client_name:
            clients_db[i] = updated_client
    set_new_clients_db(clients_db)
    return ClientOut(**updated_client.model_dump())


@client_router.post("/login_set_photo", response_model=None, summary="Set photo for client",
             description="With correct login parameters and file, simulates uploading photo")
async def fake_login_and_set_photo(commons: Annotated[CommonQueryParamsClass, Depends()],
                                   file: UploadFile | None = None) -> JSONResponse | ClientOut:
    if file is None:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Wrong photo"})
    response = await fake_login(commons)
    if isinstance(response, JSONResponse):
        return response
    else:
        content = file.file.read()
        content = base64.b64encode(content).decode('utf-8')
        client = memory_package.get_client_by_name(commons.name)
        client.photo = content
        return ClientOut(**client.model_dump())


@client_router.post("/fake_login", response_model=None)
async def fake_login(commons: Annotated[CommonQueryParamsClass, Depends()]) -> ClientOut | JSONResponse:
    client = memory_package.get_client_by_name(commons.name)
    if client and client.password == commons.password:
        return ClientOut(**client.model_dump())
    elif client and client.password != commons.password:
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"message": "Wrong password"})
    else:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Wrong name"})


@client_router.delete('/remove', response_description="Number of removed clients")
async def delete_clients_of_ids(commons: CommonDependencyAnnotation):
    first = commons['first']
    last = commons['last']
    if last < first:
        logger.warning(f"Tried to remove order with greater first id then last id")
        return JSONResponse(status_code=status.HTTP_412_PRECONDITION_FAILED,
                            content={"message": "First id greater than last id"})
    clients_to_remove = []
    async with orders_lock:
        for client in memory_package.get_clients_db():
            if first <= client.id <= last:
                clients_to_remove.append(client)
        for client in clients_to_remove:
            for order in client.orders:
                memory_package.remove_order(order)
                logger.info(f"Removing order with id {order.id}")
            remove_client(client)
    return JSONResponse(status_code=status.HTTP_200_OK,
                        content={"message": "Success", "removed_count": len(clients_to_remove)})


@client_router.get('/', response_model=list[ClientOut])
async def get_clients(count: Annotated[int | None, Query(gt=0)] = None):
    return memory_package.get_clients_db(count)


@client_router.post('/add', response_model_exclude_unset=True, response_model=None)
async def add_client_without_task(client_name1: Annotated[str, Query(min_length=3, max_length=30, pattern="^.+$", title="Main name", description="Obligatory part of the name")],
                                client_name2: Annotated[str | None, Query(min_length=3, max_length=30, pattern="^.+$", deprecated=True)] = None,
                                passwords: Annotated[list[str] | None, Query(alias="passes")] = None) -> Response | ClientOut:
    full_name = client_name1 if client_name2 is None else client_name1 + client_name2
    async with orders_lock:
        client = memory_package.get_client_by_name(full_name)
        if client is None:
            password = "".join(passwords) if passwords else "123"
            memory_package.add_client(Client(name=full_name, password=hash_password(password)))
            logger.info(f"Created new client without orders with name {full_name}")
            return ClientOut(name=full_name)
        else:
            logger.warning('Client already exists')
            return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"message": "Name used"})
