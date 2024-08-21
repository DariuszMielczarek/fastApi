class BlockingList(list):
    def __init__(self, items=None):
        super().__init__()
        self._is_blocked = False
        if items:
            for item in items:
                self.append(item)

    def append(self, item):
        if not self._is_blocked:
            super().append(item)

    def remove(self, value):
        if not self._is_blocked:
            super().remove(value)

    def block(self):
        self._is_blocked = True

    def unblock(self):
        self._is_blocked = False
