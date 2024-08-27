from pydantic import BaseModel
from order_package import Order


class ClientBase(BaseModel):
    name: str
    orders: list[Order] = []
    photo: str = str()

    model_config = {
        'from_attributes': True
    }


class Client(ClientBase):
    password: str = Ellipsis


class ClientOut(ClientBase):
    pass


class ClientInDb(BaseModel):
    name: str
    orders: list[Order] = list()
    password: str = Ellipsis
    photo: str = str()
    id: int
