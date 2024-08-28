from copy import deepcopy

from sqlalchemy import func
from sqlmodel import SQLModel, Session, select, col
from client_management_package.main.passwords import hash_password
from client_package import ClientInDb
from .models import Order, Client
from .db import engine
from memory_package import AbstractDb
from ..blocking_list import BlockingList


class SQLModelDb(AbstractDb):
    def __init__(self):
        SQLModel.metadata.drop_all(bind=engine)
        SQLModel.metadata.create_all(engine)
        self.blocked = False

    def set_new_orders_db(self, new_orders_db: BlockingList):
        with Session(engine) as session:
            for order in self.get_orders_db():
                session.delete(order)
            session.commit()
            for order in new_orders_db:
                session.add(order)
            session.commit()

    def set_new_clients_db(self, new_clients_db: BlockingList):
        with Session(engine) as session:
            for client in self.get_clients_db():
                session.delete(client)
            session.commit()
        for client in new_clients_db:
            self.add_client(client.name, client.password, client.photo, client.orders)

    async def get_all_orders_as_dict(self):
        statement = select(Order).order_by(Order.id) # noqa
        with Session(engine) as session:
            results = session.exec(statement).all()
        return [order.model_dump() for order in results]

    async def get_first_order_with_status(self, status_str: str):
        statement = select(Order).where(Order.status == status_str) # noqa
        with Session(engine) as session:
            result = session.exec(statement).first()
            return result

    def get_order_by_id(self, order_id: int):
        with Session(engine) as session:
            order = session.get(Order, order_id)
            return order

    def add_order(self, order: Order):
        if not self.blocked:
            with Session(engine) as session:
                session.add(order)
                session.commit()

    def add_client(self, name, password, photo=str(), orders=None):
        if not self.blocked:
            client = Client(name=name, photo=photo, password=password)
            with Session(engine) as session:
                session.add(client)
                session.commit()
                session.refresh(client)
                return client.id

    def add_order_to_client(self, order, client):
        pass

    def get_client_by_name(self, full_name: str):
        statement = select(Client).where(Client.name == full_name) # noqa
        with Session(engine) as session:
            result = session.exec(statement).first()
            return result

    def get_clients_by_ids(self, client_ids: list[int]):
        statement = select(Client).where(col(Client.id).in_(client_ids)) # noqa
        with Session(engine) as session:
            result = session.exec(statement)
            orders = result.all()
            return orders

    def get_client_by_id(self, client_id: int):
        with Session(engine) as session:
            client = session.get(Client, client_id)
            return client

    def get_clients_db(self, count: int = None):
        statement = select(Client).limit(count)
        with Session(engine) as session:
            results = session.exec(statement).all()
            for client in results:
                client.orders = deepcopy(client.orders)
            return results

    def get_orders_db(self):
        statement = select(Order).order_by(Order.id) # noqa
        with Session(engine) as session:
            results = session.exec(statement).all()
            return results

    def remove_order(self, order: Order):
        with Session(engine) as session:
            order = session.get(Order, order.id)
            session.delete(order)
            session.commit()

    def remove_client(self, client: ClientInDb):
        with Session(engine) as session:
            client = session.get(Client, client.id)
            session.delete(client)
            session.commit()

    def get_next_order_id(self):
        return self._get_next_id(Order)

    def get_next_client_id(self):
        return self._get_next_id(Client)

    @staticmethod
    def _get_next_id(table):
        statement = select(table.id).order_by(table.id)
        with Session(engine) as session:
            next_id = session.exec(statement).first()
            if not next_id:
                return 1
            else:
                return next_id + 1 # noqa

    def get_clients_count(self):
        statement = select(func.count()).select_from(Client)
        with Session(engine) as session:
            result = session.exec(statement).one()
            return result

    def get_orders_count(self):
        statement = select(func.count()).select_from(Order)
        with Session(engine) as session:
            result = session.exec(statement).one()
            return result

    def get_password_from_client_by_name(self, full_name: str):
        statement = select(Client.password).where(Client.name == full_name) # noqa
        with Session(engine) as session:
            result = session.exec(statement).first()
            return result

    def get_orders_by_client_id(self, client_id: int):
        with Session(engine) as session:
            client_exists = session.get(Client, client_id)

        if not client_exists:
            return None

        statement2 = select(Order).where(Order.client_id == client_id) # noqa
        with Session(engine) as session:
            orders = session.exec(statement2).all()

        return orders

    def get_orders_by_client_name(self, client_name: str):
        client = self.get_client_by_name(client_name)
        if client is None:
            return []
        return self.get_orders_by_client_id(client.id)

    def clear_db(self):
        self.set_new_orders_db(BlockingList())
        self.set_new_clients_db(BlockingList())

    def open_dbs(self):
        self.blocked = False

    def close_dbs(self):
        self.blocked = True

    def remove_order_from_client(self, client, order) -> None:
        pass

    def change_order_owner(self, client_id, order_id) -> None:
        with Session(engine) as session:
            order = session.get(Order, order_id)
            order.client_id = client_id
            session.add(order)
            session.commit()
            session.refresh(order)

    def get_client_id_from_client_by_name(self, client_name) -> int:
        statement = select(Client.id).where(Client.name == client_name) # noqa
        with Session(engine) as session:
            result = session.exec(statement).one()
            return result

    def replace_order_in_client_object(self, order) -> None:
        with Session(engine) as session:
            order_db = session.get(Order, order.id)
            order_db.description = order.description
            order_db.time = order.time
            order_db.status = order.status
            order_db.client_id = order.client_id
            order_db.creation_date = order.creation_date
            session.add(order_db)
            session.commit()
            session.refresh(order_db)

    def map_client(self, client):
        statement1 = select(Client).where(Client.name == client.name) # noqa
        with Session(engine) as session:
            client = session.exec(statement1).one()
            return Client.model_validate(client).model_dump()

    def change_client_password(self, client, password):
        with Session(engine) as session:
            client = session.get(Client, client.id)
            client.password = hash_password(password)
            session.add(client)
            session.commit()
            session.refresh(client)

    def update_one_client(self, client_name: str, updated_client):
        statement = select(Client).where(Client.name == client_name) # noqa
        with Session(engine) as session:
            client = session.exec(statement).one()
            client.name = updated_client.name
            client.password = updated_client.password
            client.photo = updated_client.photo
            session.add(client)
            session.commit()
            session.refresh(client)

    def remove_all_clients_orders(self, client) -> None:
        pass
