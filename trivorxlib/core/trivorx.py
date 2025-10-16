from base import *
from trivorxlib.storages import *

class TXUser(TXUserBase):

    _storage: TXStorageBase = None
    _stored: bool = False

    def __init__(self, storage: TXStorageBase, uuid: str = None, token: str = None, encrypted_password: str = None):
        super().__init__(uuid, token, encrypted_password)
        self._storage = storage 
        self._from_storage(uuid, token)

    def _from_storage(self, uuid: str = None, token: str = None, update: bool = True):
        if uuid or token:
            from_storage: list[TXUserBase] = self._storage.get_users(TXLogicalQuery(TXStorageQueryOps.OR, TXCondition(TXStorageQueryOps.EQUALS, 'uuid', uuid), TXCondition(TXStorageQueryOps.EQUALS, 'token', token)))
            if len(from_storage) == 1:
                if update:
                    self.from_base(from_storage[0])
                self._stored = True
                return
            if update:
                raise ValueError("The user with the specified UUID or token does not exist in the storage.")

    def from_base(self, user_base: TXUserBase):
        self._uuid = user_base.uuid
        self._token = user_base.token
        self._encrypted_password = user_base.password
        self.role = user_base.role
        self.full_name = user_base.full_name
        self.login = user_base.login
        self.twofa_seed = user_base.twofa_seed
        self.enabled = user_base.enabled
        self.creation_datetime = user_base.creation_datetime
        self._stored = False
        self._from_storage(self._uuid, self._token, update=False) 
        self.save()

    def save(self):
        if self._stored:
            self._storage.update_user(
                uuid=self.uuid,
                token=self.token,
                full_name=self.full_name,
                login=self.login,
                password=None,
                role=self.role,
                enabled=self.enabled,
                encrypted_password=self._encrypted_password,
                twofa_seed=self.twofa_seed,
            )
        else:
            self._storage.insert_user(
                full_name=self.full_name,
                login=self.login,
                role=self.role,
                password=None,
                encrypted_password=self._encrypted_password,
                uuid=self.uuid,
                token=self.token,
                twofa_seed=self.twofa_seed,
            )
            self._stored = True
    
    
