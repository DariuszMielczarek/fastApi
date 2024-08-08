from pydantic import BaseModel, Field

from orders_process_package import OrderStatus


class Order(BaseModel):
    id: int
    description: str
    time: int = 60
    status: OrderStatus = OrderStatus.received
    client_name: str
