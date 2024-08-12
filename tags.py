from enum import Enum


class Tags(Enum):
    order_process = "process"
    clients = "clients"
    order_create = "create"
    order_get = "get"
    order_delete = "remove"
    order_update = "update"
