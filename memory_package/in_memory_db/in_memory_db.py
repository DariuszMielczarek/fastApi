import copy
from client_package.client import ClientInDb
from memory_package.blocking_list import BlockingList
from memory_package import AbstractDb
from order_package import Order
from memory_package.in_memory_vars import orders_lock


class InMemoryDb(AbstractDb):
    def __init__(self):
        self.orders_db = BlockingList()
        self.clients_db = BlockingList()

    def set_new_orders_db(self, new_orders_db: BlockingList):
        self.orders_db = copy.deepcopy(new_orders_db)

    def set_new_clients_db(self, new_clients_db: BlockingList):
        self.clients_db = copy.deepcopy(new_clients_db)

    async def get_all_orders_as_dict(self):
        async with orders_lock:
            return [order.model_dump() for order in self.orders_db]

    async def get_first_order_with_status(self, status_str: str):
        async with orders_lock:
            return next((order for order in self.orders_db if order.status.value == status_str), None)

    def get_order_by_id(self, order_id: int):
        return next((order for order in self.orders_db if order.id == order_id), None)

    def add_order(self, order):
        self.orders_db.append(order)

    def add_client(self, client):
        client_id = self.get_next_client_id()
        self.clients_db.append(ClientInDb(**client.model_dump(), id=client_id))
        return client_id

    def add_order_to_client(self, order, client):
        if client and order:
            client.orders.append(order)

    def get_client_by_name(self, full_name: str):
        return next((client for client in self.clients_db if client.name == full_name), None)

    def get_clients_by_ids(self, client_ids: list[int]):
        return [client for client in self.clients_db if client.id in client_ids]

    def get_client_by_id(self, client_id: int):
        return self.get_clients_by_ids([client_id])[0] if self.get_clients_by_ids([client_id]) else None

    def get_clients_db(self, count: int = None):
        return self.clients_db[:count] if count else self.clients_db

    def get_orders_db(self):
        return self.orders_db

    def remove_order(self, order: Order):
        self.orders_db.remove(order)

    def remove_client(self, client: ClientInDb):
        self.clients_db.remove(client)

    def get_next_order_id(self):
        return 0 if len(self.get_orders_db()) == 0 else max(self.get_orders_db(), key=lambda order: order.id).id + 1

    def get_next_client_id(self):
        return 0 if len(self.get_clients_db()) == 0 else max(self.get_clients_db(), key=lambda client: client.id).id + 1

    def get_clients_count(self):
        return len(self.clients_db)

    def get_orders_count(self):
        return len(self.orders_db)

    def get_password_from_client_by_name(self, full_name: str):
        client = self.get_client_by_name(full_name)
        return client.password if client else None

    def get_orders_by_client_id(self, client_id: int):
        clients = self.get_clients_by_ids([client_id])
        return clients[0].orders if len(clients) > 0 else None

    def get_orders_by_client_name(self, client_name: str):
        client = self.get_client_by_name(client_name)
        return client.orders if client else None

    def clear_db(self):
        self.orders_db.clear()
        self.clients_db.clear()

    def open_dbs(self):
        self.orders_db.unblock()
        self.clients_db.unblock()

    def close_dbs(self):
        self.orders_db.block()
        self.clients_db.block()
