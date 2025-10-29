from __future__ import annotations

class NotFoundError(Exception):
    def __init__(self, what: str = "Resource"):
        super().__init__(what)
        self.what = what

class ConflictError(Exception):
    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail

class BadRequestError(Exception):
    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail
