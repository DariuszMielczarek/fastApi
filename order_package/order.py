from datetime import datetime

from pydantic import BaseModel
from .order_status import OrderStatus


class Order(BaseModel):
    id: int
    description: str
    time: int = 60
    status: OrderStatus = OrderStatus.received
    client_id: int | None
    creation_date: datetime

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if isinstance(other, Order):
            return self.id == other.id
        return False
