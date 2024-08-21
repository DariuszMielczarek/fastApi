from memory_package import get_next_order_id
from order_package import Order
from orders_management_package import OrderDTO


def map_orderDto_to_Order(orderDto: OrderDTO, client_id: int | None = None) -> Order:
    return Order(id=get_next_order_id(), description=orderDto.description,
                 time=orderDto.time, client_id=client_id, creation_date=orderDto.timestamp)
