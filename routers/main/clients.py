import base64
from typing import Annotated
from fastapi import APIRouter, Depends, Path, Query, HTTPException, UploadFile, BackgroundTasks
from starlette import status
from starlette.responses import JSONResponse, Response
from app.main.background_tasks import send_notification_simulator
from client_management_package import hash_password
from client_package import ClientOut
from client_package.client import Client
from dependencies_package.main.dependencies import verify_key_common, CommonQueryParamsClass, CommonDependencyAnnotation
from memory_package import logger, orders_lock
from app.main.tags import Tags
import memory_package

client_router = APIRouter(prefix="/clients", tags=[Tags.clients])


@client_router.patch("/update/password/{client_name}",
                     response_model=None, dependencies=[Depends(verify_key_common)])
async def change_client_password(client_name: Annotated[str, Path()],
                                 password: Annotated[str | None, Query()] = None) -> JSONResponse | ClientOut:
    client = memory_package.db.get_client_by_name(client_name)
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"message": "Wrong name"})
    if password:
        memory_package.db.change_client_password(client, password)
    client_data = memory_package.db.map_client(client)
    return ClientOut(**client_data)


@client_router.put("/update/all/{client_name}", response_model=None)
async def change_client_data(client_name: Annotated[str, Path()],
                             name: Annotated[str | None, Query()] = None,
                             password: Annotated[str | None, Query()] = None) -> JSONResponse | ClientOut:
    client = memory_package.db.get_client_by_name(client_name)
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"message": "Wrong name"})
    client_data = memory_package.db.map_client(client)
    updated_client = Client(**client_data)
    updated_client.name = name if name is not None else updated_client.name
    updated_client.password = password if password is not None else updated_client.password
    memory_package.db.update_one_client(client_name, updated_client)
    client_data = memory_package.db.map_client(updated_client)
    return ClientOut(**client_data)


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
        client = memory_package.db.get_client_by_name(commons.name)
        client.photo = content
        memory_package.db.update_one_client(commons.name, client)
        client_data = memory_package.db.map_client(client)
        return ClientOut(**client_data)


@client_router.post("/fake_login", response_model=None)
async def fake_login(commons: Annotated[CommonQueryParamsClass, Depends()]) -> ClientOut | JSONResponse:
    client = memory_package.db.get_client_by_name(commons.name)
    if client and client.password == commons.password:
        client_data = memory_package.db.map_client(client)
        return ClientOut(**client_data)
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
        for client in memory_package.db.get_clients_db():
            if first <= client.id <= last:
                clients_to_remove.append(client)
        for client in clients_to_remove:
            memory_package.db.remove_all_clients_orders(client)
            memory_package.db.remove_client(client)
    return JSONResponse(status_code=status.HTTP_200_OK,
                        content={"message": "Success", "removed_count": len(clients_to_remove)})


@client_router.get('/', response_model=list[ClientOut])
async def get_clients(count: Annotated[int | None, Query(gt=0)] = None):
    clients = memory_package.db.get_clients_db(count)
    return clients


@client_router.post('/add', response_model_exclude_unset=True, response_model=None)
async def add_client_without_task(background_tasks: BackgroundTasks,
                                  client_name1: Annotated[
                                      str, Query(min_length=3, max_length=30, pattern="^.+$", title="Main name",
                                                 description="Obligatory part of the name")],
                                  client_name2: Annotated[str | None, Query(min_length=3, max_length=30, pattern="^.+$",
                                                                            deprecated=True)] = None,
                                  passwords: Annotated[
                                      list[str] | None, Query(alias="passes")] = None) -> Response | ClientOut:
    full_name = client_name1 if client_name2 is None else client_name1 + client_name2
    async with orders_lock:
        client = memory_package.db.get_client_by_name(full_name)
        if client is None:
            password = "".join(passwords) if passwords else "123"
            memory_package.db.add_client(name=full_name, password=hash_password(password))
            logger.info(f"Created new client without orders with name {full_name}")
            background_tasks.add_task(send_notification_simulator, name=full_name)
            return ClientOut(name=full_name)
        else:
            logger.warning('Client already exists')
            return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"message": "Name used"})
