class AuthError(Exception):
    def __init__(self, msg: str, *, code: int = 40101):
        self.msg = msg
        self.code = code
        super().__init__(msg)
