from memory_package import db
from order_package import Order
from orders_management_package import OrderDTO


def map_order_dto_to_order(order_dto: OrderDTO, client_id: int | None = None) -> Order:
    return Order(id=db.get_next_order_id(), description=order_dto.description,
                 time=order_dto.time, client_id=client_id, creation_date=order_dto.timestamp)
