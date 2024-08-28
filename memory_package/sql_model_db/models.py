from datetime import datetime
from sqlalchemy import Column, Enum
from sqlmodel import SQLModel, Field, Relationship

from order_package import OrderStatus


class Client(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    password: str
    photo: str | None = Field(default=None)
    orders: list["Order"] = Relationship(back_populates="client", cascade_delete=True)


class Order(SQLModel, table=True):
    __tablename__ = "orders"
    id: int | None = Field(default=None, primary_key=True)
    description: str = Field(unique=True)
    time: int = Field(default=60)
    status: OrderStatus = Field(sa_column=Column(Enum(OrderStatus), default=OrderStatus.received))
    client_id: int | None = Field(default=None, foreign_key="client.id", ondelete='CASCADE')
    creation_date: datetime = Field(default=datetime.now())
    client: Client | None = Relationship(back_populates="orders")
