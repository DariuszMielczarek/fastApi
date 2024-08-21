class NoOrderException(Exception):
    def __init__(self, order_id: int | None = None, message: str | None = None):
        self.order_id = order_id
        self.message = message


class WrongDeltaException(Exception):
    def __init__(self, message: str | None = None):
        self.message = message
