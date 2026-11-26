class LimoError(Exception):
    status = 500

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class NotFound(LimoError):
    status = 404


class Conflict(LimoError):
    status = 409


class ExternalError(LimoError):
    status = 502
