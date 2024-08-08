from enum import Enum


class OrderStatus(str, Enum):
    received = 'received'
    in_progress = 'in_progress'
    complete = 'complete'
