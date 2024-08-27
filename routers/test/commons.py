from datetime import datetime

import memory_package
from client_management_package.main.passwords import hash_password
from client_package import Client
from order_package import Order, OrderStatus
from memory_package import OrderPostgres as OrderInDb


order1 = Order(id=0, description='Order1', creation_date=datetime.now(), client_id=None)
order2 = Order(id=1, description='Order2', creation_date=datetime.now(), client_id=None)
name1 = "Client"
name2 = "Test"
name3 = "333"
password_list = ["abc", "def"]
client1 = Client(name=name1, password=hash_password('abc'))
client2 = Client(name=name2, password=hash_password('abc'))
client3 = Client(name=name3, password=hash_password('abc'))


def local_add_client(client: Client):
    memory_package.db.open_dbs()
    client_id = memory_package.db.add_client(name=client.name, password=client.password)
    memory_package.db.close_dbs()
    return client_id


def local_add_order(order: Order) -> None:
    memory_package.db.open_dbs()
    memory_package.db.add_order(order)
    memory_package.db.close_dbs()


def local_add_order_to_db_and_client(client_id: int, order_desc: str, order_status: OrderStatus = OrderStatus.received) -> int:
    order_id1 = memory_package.db.get_next_order_id()
    if memory_package.db_type == 'in_memory':
        new_order = Order(id=order_id1, description=order_desc, client_id=client_id, creation_date=datetime.now(),
                          status=order_status)
        local_add_order(new_order)
        memory_package.db.add_order_to_client(new_order, memory_package.db.get_client_by_id(client_id))
    elif memory_package.db_type == 'postgres':
        new_order = OrderInDb(description=order_desc, client_id=client_id, creation_date=datetime.now(),
                              status=order_status)
        local_add_order(new_order)
        memory_package.db.add_order_to_client(new_order, memory_package.db.get_client_by_id(client_id))
    return order_id1
