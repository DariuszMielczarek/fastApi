from abc import ABC, abstractmethod

from client_package import Client, ClientInDb
from memory_package.blocking_list import BlockingList
from order_package import Order


class AbstractDb(ABC):
    @abstractmethod
    def set_new_orders_db(self, new_orders_db: BlockingList) -> None:
        pass

    @abstractmethod
    def set_new_clients_db(self, new_clients_db: BlockingList) -> None:
        pass

    @abstractmethod
    async def get_all_orders_as_dict(self) -> list[dict]:
        pass

    @abstractmethod
    async def get_first_order_with_status(self, status_str: str) -> Order | None:
        pass

    @abstractmethod
    def get_order_by_id(self, order_id: int) -> Order | None:
        pass

    @abstractmethod
    def add_order(self, order) -> int:
        pass

    @abstractmethod
    def add_client(self, name, password, photo=str(), orders=None):
        pass

    @abstractmethod
    def add_order_to_client(self, order, client) -> None:
        pass

    @abstractmethod
    def get_client_by_name(self, full_name: str) -> ClientInDb | None:
        pass

    @abstractmethod
    def get_clients_by_ids(self, client_ids: list[int]) -> list[Client]:
        pass

    @abstractmethod
    def get_client_by_id(self, client_id: int) -> Client | None:
        pass

    @abstractmethod
    def get_clients_db(self, count: int = None) -> list[ClientInDb]:
        pass

    @abstractmethod
    def get_orders_db(self) -> list[Order]:
        pass

    @abstractmethod
    def remove_order(self, order: Order) -> None:
        pass

    @abstractmethod
    def remove_client(self, client: ClientInDb) -> None:
        pass

    @abstractmethod
    def get_next_order_id(self) -> int:
        pass

    @abstractmethod
    def get_next_client_id(self) -> int:
        pass

    @abstractmethod
    def get_clients_count(self) -> int:
        pass

    @abstractmethod
    def get_orders_count(self) -> int:
        pass

    @abstractmethod
    def get_password_from_client_by_name(self, full_name: str) -> str:
        pass

    @abstractmethod
    def get_orders_by_client_id(self, client_id: int) -> list[Order]:
        pass

    @abstractmethod
    def get_orders_by_client_name(self, client_name: str) -> list[Order]:
        pass

    @abstractmethod
    def clear_db(self) -> None:
        pass

    @abstractmethod
    def open_dbs(self) -> None:
        pass

    @abstractmethod
    def close_dbs(self) -> None:
        pass

    @abstractmethod
    def remove_order_from_client(self, client, order) -> None:
        pass

    @abstractmethod
    def change_order_owner(self, client_id, order_id) -> None:
        pass

    @abstractmethod
    def get_client_id_from_client_by_name(self, client_name) -> int:
        pass

    @abstractmethod
    def replace_order_in_client_object(self, order) -> None:
        pass

    @abstractmethod
    def map_client(self, client):
        pass

    @abstractmethod
    def change_client_password(self, client, password) -> None:
        pass

    @abstractmethod
    def update_one_client(self, client_name: str, updated_client):
        pass

    @abstractmethod
    def remove_all_clients_orders(self, client) -> None:
        pass
