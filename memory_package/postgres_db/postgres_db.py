from datetime import datetime
from sqlalchemy import Column, Integer, Identity, String, ForeignKey, DateTime, Enum, create_engine, select, func, \
    delete, update, insert
from sqlalchemy.orm import declarative_base, Session, relationship, joinedload

from client_management_package.main.passwords import hash_password
from client_package import ClientInDb, Client as ClientFromPackage
from memory_package import AbstractDb
from memory_package.blocking_list import BlockingList
from order_package import OrderStatus
from order_package import Order as OrderInMemory

DATABASE_URL = 'postgresql+psycopg2://postgres:12345@localhost/fast_api_queue_app'
engine = create_engine(url=DATABASE_URL, echo=True)

Base = declarative_base()


class Client(Base):
    __tablename__ = 'clients'

    id = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    name = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    photo = Column(String, nullable=True)

    orders = relationship("Order", back_populates="client", passive_deletes=True)

    def __repr__(self):
        return f"Client: {self.id}){self.name} password {self.password}"


class Order(Base):
    __tablename__ = 'orders'

    id = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    description = Column(String, unique=True, nullable=False)
    time = Column(Integer, default=60)
    status = Column(Enum(OrderStatus), default=OrderStatus.received)
    client_id = Column(Integer, ForeignKey('clients.id', ondelete='SET NULL'))
    creation_date = Column(DateTime, default=datetime.now())

    client = relationship("Client", back_populates="orders")

    def __repr__(self):
        return f"Order: {self.id}){self.description} owner {self.client_id}"


def map_order_postgres_to_order_in_memory(order: Order) -> OrderInMemory:
    return OrderInMemory(id=order.id, description=order.description, time=order.time,
                         client_id=order.client_id, creation_date=order.creation_date, status=order.status)


class PostgresDb(AbstractDb):
    def __init__(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.blocked = False

    def set_new_orders_db(self, new_orders_db: BlockingList):
        with Session(engine) as session:
            session.query(Order).delete()
            for order in new_orders_db:
                order_as_dict = vars(order)
                order_as_dict.pop('_sa_instance_state')
                statement = insert(Order).values(order_as_dict)
                session.execute(statement)
            session.commit()

    def set_new_clients_db(self, new_clients_db: BlockingList):
        with Session(engine) as session:
            session.query(Client).delete()
            session.commit()
        for client in new_clients_db:
            self.add_client(client.name, client.password, client.photo, client.orders)

    async def get_all_orders_as_dict(self):
        statement = select(Order).order_by(Order.id)
        with Session(engine) as session:
            result = session.execute(statement)
            fetched = result.fetchall()
        return [map_order_postgres_to_order_in_memory(order[0]).model_dump() for order in fetched]

    async def get_first_order_with_status(self, status_str: str):
        statement = select(Order).filter(Order.status == status_str).limit(1)  # noqa
        with Session(engine) as session:
            fetched = session.execute(statement).fetchall()
            return fetched[0][0] if fetched else None

    def get_order_by_id(self, order_id: int):
        statement = select(Order).filter(Order.id == order_id).limit(1)  # noqa
        with Session(engine) as session:
            result = session.execute(statement)
            fetched = result.fetchall()
            return fetched[0][0] if fetched else None

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
                return client.id

    def add_order_to_client(self, order, client):
        pass

    def get_client_by_name(self, full_name: str):
        statement = select(Client).filter(Client.name == full_name).limit(1)  # noqa
        with Session(engine) as session:
            result = session.execute(statement)
            fetched = result.fetchall()
            return fetched[0][0] if fetched else None

    def get_clients_by_ids(self, client_ids: list[int]):
        statement = select(Client).where(Client.id.in_(client_ids))
        with Session(engine) as session:
            result = session.execute(statement)
            orders = result.scalars().all()
            return orders

    def get_client_by_id(self, client_id: int):
        statement = select(Client).filter(Client.id == client_id).limit(1)  # noqa
        with Session(engine) as session:
            result = session.execute(statement)
            fetched = result.fetchall()
            return fetched[0][0] if fetched else None

    def get_clients_db(self, count: int = None):
        statement = select(Client).options(joinedload(Client.orders)).order_by(Client.id).limit(count)
        with Session(engine) as session:
            result = session.execute(statement).unique()
            fetched = result.fetchall()
            clients = [client[0] for client in fetched]
            return clients

    def get_orders_db(self):
        statement = select(Order).order_by(Order.id)
        with Session(engine) as session:
            result = session.execute(statement)
            fetched = result.fetchall()
            orders = [order[0] for order in fetched]
            return orders

    def remove_order(self, order: Order):
        statement = delete(Order).where(Order.id == order.id)  # noqa
        with Session(engine) as session:
            session.execute(statement)
            session.commit()

    def remove_client(self, client: ClientInDb):
        self.remove_all_clients_orders(client)
        statement = delete(Client).where(Client.id == client.id)  # noqa
        with Session(engine) as session:
            session.execute(statement)
            session.commit()

    def get_next_order_id(self):
        return self._get_next_id(Order)

    def get_next_client_id(self):
        return self._get_next_id(Client)

    @staticmethod
    def _get_next_id(table):
        statement = select(table.id).order_by(table.id).limit(1)
        with Session(engine) as session:
            result = session.execute(statement)
            next_id = result.fetchall()
            if not next_id:
                return 1

            return next_id[0][0] + 1

    def get_clients_count(self):
        statement = select(func.count()).select_from(Client)
        with Session(engine) as session:
            result = session.execute(statement)
            return result.fetchall()[0][0]

    def get_orders_count(self):
        statement = select(func.count()).select_from(Order)
        with Session(engine) as session:
            result = session.execute(statement)
            return result.fetchall()[0][0]

    def get_password_from_client_by_name(self, full_name: str):
        statement = select(Client.password).where(Client.name == full_name).limit(1)  # noqa
        with Session(engine) as session:
            result = session.execute(statement)
            fetched = result.fetchall()
            return fetched[0][0] if fetched else None

    def get_orders_by_client_id(self, client_id: int):
        statement1 = select(Client).filter(Client.id == client_id)  # noqa
        with Session(engine) as session:
            client_exists = session.execute(statement1).scalars().first()

        if not client_exists:
            return None

        statement2 = select(Order).filter(Order.client_id == client_id)  # noqa
        with Session(engine) as session:
            orders = session.execute(statement2).scalars().all()

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
        statement = update(Order).filter(Order.id == order_id).values(client_id=client_id)
        with Session(engine) as session:
            session.execute(statement)
            session.commit()

    def get_client_id_from_client_by_name(self, client_name) -> int:
        statement = select(Client.id).where(Client.name == client_name).limit(1)
        with Session(engine) as session:
            result = session.execute(statement)
            return result.fetchall()[0][0]

    def replace_order_in_client_object(self, order) -> None:
        statement = update(Order).where(Order.id == order.id).values(status=order.status)
        with Session(engine) as session:
            session.execute(statement)
            session.commit()

    def map_client(self, client):
        with Session(engine) as session:
            client = session.query(Client).options(joinedload(Client.orders)).filter_by(name=client.name).one()
            return ClientFromPackage.model_validate(client).model_dump()

    def change_client_password(self, client, password):
        statement = update(Client).where(Client.id == client.id).values(password=hash_password(password))
        with Session(engine) as session:
            session.execute(statement)
            session.commit()

    def update_one_client(self, client_name: str, updated_client):
        with Session(engine) as session:
            client = session.query(Client).filter_by(name=client_name).first()
            client.name = updated_client.name
            client.password = updated_client.password
            client.photo = updated_client.photo
            session.commit()

    def remove_all_clients_orders(self, client) -> None:
        statement = delete(Order).where(Order.client_id == client.id)
        with Session(engine) as session:
            session.execute(statement)
            session.commit()
