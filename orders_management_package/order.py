from pydantic import BaseModel

from orders_management_package import OrderStatus


class Order(BaseModel):
    id: int
    description: str
    time: int = 60
    status: OrderStatus = OrderStatus.received
    client_name: str | None

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if isinstance(other, Order):
            return self.id == other.id
        return False
