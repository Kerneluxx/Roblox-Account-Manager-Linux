class ManagerError(Exception):
    def __init__(self, key, **params):
        super().__init__(key)
        self.key = key
        self.params = params

    def __str__(self):
        from .idiomas import tr
        return tr(self.key, **self.params)


class ValidationError(ManagerError):
    pass


class VaultError(ManagerError):
    pass


class WrongPassword(VaultError):
    pass


class SessionError(ManagerError):
    pass


class ClientError(ManagerError):
    pass
