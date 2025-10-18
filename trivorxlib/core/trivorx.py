from .base import *
from trivorxlib.storages.base import *

class TXUser(TXUserBase):

    _storage: TXStorageBase = None
    _stored: bool = False

    def __init__(self, storage: TXStorageBase, uuid: str = None, token: str = None, encrypted_password: str = None):
        super().__init__(uuid, token, encrypted_password)
        self._storage = storage 
        self._from_storage(uuid, token)

    def _from_storage(self, uuid: str = None, token: str = None, update: bool = True):
        if uuid or token:
            from_storage: list[TXUserBase] = self._storage.get_users(TXLogicalQuery(TXStorageQueryOps.OR, TXCondition(TXStorageQueryOps.EQUALS, 'user_uuid', uuid), TXCondition(TXStorageQueryOps.EQUALS, 'token', token)))
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
    
    
class TXBot(TXBotBase):

    _storage: TXStorageBase = None
    _stored: bool = False

    def __init__(
        self,
        storage: TXStorageBase,
        user: TXUserBase, 
        algo_uuid: str, 
        name: str, 
        algo_name: str, 
        algo_ver: str, 
        algo_settings: str, 
        uuid: str = None
    ):
        super().__init__(user, algo_uuid, name, algo_name, algo_ver, algo_settings, uuid)
        self._storage = storage
        self._from_storage(uuid)

    def _from_storage(self, uuid: str | None = None, update: bool = True):
        if uuid:
            from_storage: list[TXBotBase] = self._storage.get_bots(
                TXCondition(TXStorageQueryOps.EQUALS, 'bot_uuid', uuid)
            )
            if len(from_storage) == 1:
                if update:
                    self.from_base(from_storage[0])
                self._stored = True
                return
            if update:
                raise ValueError("The bot with the specified UUID does not exist in the storage.")

    def from_base(self, bot_base: TXBotBase):
        self._uuid = bot_base.uuid
        self.user = bot_base.user
        self.algo_uuid = bot_base.algo_uuid
        self.name = bot_base.name
        self.algo_ver = bot_base.algo_ver
        self.algo_settings = bot_base.algo_settings
        self.annotations = bot_base.annotations
        self.active = bot_base.active
        self.creation_datetime = bot_base.creation_datetime
        self.algo_name = bot_base.algo_name
        self._stored = False
        self._from_storage(self._uuid, update=False)
        self.save()

    def save(self):
        if self._stored:
            self._storage.update_bot(
                uuid=self.uuid,
                user_uuid=self.user.uuid,
                algo_uuid=self.algo_uuid,
                name=self.name,
                algo_name=self.algo_name,
                algo_ver=self.algo_ver,
                algo_settings=self.algo_settings,
                annotations=self._annotations,
                active=self.active,
            )
        else:
            self._uuid = self._storage.insert_bot(
                user_uuid=self.user.uuid,
                algo_uuid=self.algo_uuid,
                name=self.name,
                algo_name=self.algo_name,
                algo_ver=self.algo_ver,
                algo_settings=self.algo_settings,
                annotations=self.annotations,
                active=self.active,
                uuid=self._uuid,
            )
            self._stored = True


class TXCurrency(TXCurrencyBase):

    _storage: TXStorageBase = None
    _stored: bool = False

    def __init__(
        self,
        storage: TXStorageBase,
        long_name: str,
        short_name: str,
        currency_type: TXCurrencyType,
        uuid: str = None
    ):
        super().__init__(uuid)
        self._storage = storage
        self._from_storage(uuid)

    def _from_storage(self, uuid: str | None = None, update: bool = True):
        if uuid:
            from_storage: list[TXCurrencyBase] = self._storage.get_currencies(
                TXCondition(TXStorageQueryOps.EQUALS, 'currency_uuid', uuid)
            )
            if len(from_storage) == 1:
                if update:
                    self.from_base(from_storage[0])
                self._stored = True
                return
            if update:
                raise ValueError("The currency with the specified UUID does not exist in the storage.")

    def from_base(self, currency_base: TXCurrencyBase):
        self._uuid = currency_base.uuid
        self.long_name = currency_base.long_name
        self.short_name = currency_base.short_name
        self.currency_type = currency_base.currency_type
        self._stored = False
        self._from_storage(self._uuid, update=False)
        self.save()

    def save(self):
        if self._stored:
            self._storage.update_currency(
                uuid=self.uuid,
                long_name=self.long_name,
                short_name=self.short_name,
                currency_type=self.currency_type,
            )
        else:
            self._uuid = self._storage.insert_currency(
                long_name=self.long_name,
                short_name=self.short_name,
                currency_type=self.currency_type,
                uuid=self._uuid,
            )
            self._stored = True


class TXExchangeDataSource(TXExchangeDataSourceBase):

    _storage: TXStorageBase = None
    _stored: bool = False

    def __init__(
        self,
        storage: TXStorageBase,
        name: str,
        avaiable_currency_types: set[TXCurrencyType],
        connection_data_required: bool,
        uuid: str = None
    ):
        super().__init__(name, avaiable_currency_types, connection_data_required, uuid)
        self._storage = storage
        self._from_storage(uuid)

    def _from_storage(self, uuid: str | None = None, update: bool = True):
        if uuid:
            from_storage: list[TXExchangeDataSourceBase] = self._storage.get_exchange_data_sources(
                TXCondition(TXStorageQueryOps.EQUALS, 'exchange_data_source_uuid', uuid)
            )
            if len(from_storage) == 1:
                if update:
                    self.from_base(from_storage[0])
                self._stored = True
                return
            if update:
                raise ValueError("The exchange data source with the specified UUID does not exist in the storage.")

    def from_base(self, exchange_data_source_base: TXExchangeDataSourceBase):
        self._uuid = exchange_data_source_base.uuid
        self.name = exchange_data_source_base.name
        self.avaiable_currency_types = exchange_data_source_base.avaiable_currency_types
        self.connection_data_required = exchange_data_source_base.connection_data_required
        self.default_for_types = exchange_data_source_base.default_for_types
        self.notes = exchange_data_source_base.notes
        self._stored = False
        self._from_storage(self._uuid, update=False)
        self.save()

    def save(self):
        if self._stored:
            self._storage.update_exchange_data_source(
                uuid=self.uuid,
                name=self.name,
                available_currency_types=self.avaiable_currency_types,
                connection_data_required=self.connection_data_required,
                default_for_types=self.default_for_types,
                notes=self.notes,
            )
        else:
            self._uuid = self._storage.insert_exchange_data_source(
                name=self.name,
                available_currency_types=self.avaiable_currency_types,
                connection_data_required=self.connection_data_required,
                default_for_types=self.default_for_types,
                notes=self.notes,
                uuid=self._uuid,
            )
            self._stored = True            

class TXExchangeDataSourceConnectionData(TXExchangeDataSourceConnectionDataBase):

    _storage: TXStorageBase = None
    _stored: bool = False

    def __init__(
        self,
        storage: TXStorageBase,
        user: TXUserBase,
        data_source: TXExchangeDataSourceBase,
        connection_data: str,
        uuid: str = None
    ):
        super().__init__(user, data_source, connection_data, uuid)
        self._storage = storage
        self._from_storage(uuid)

    def _from_storage(self, uuid: str | None = None, update: bool = True):
        if uuid:
            from_storage: list[TXExchangeDataSourceConnectionDataBase] = self._storage.get_exchange_data_source_connection_data(
                TXCondition(TXStorageQueryOps.EQUALS, 'exchange_data_source_connection_data_uuid', uuid)
            )
            if len(from_storage) == 1:
                if update:
                    self.from_base(from_storage[0])
                self._stored = True
                return
            if update:
                raise ValueError("The exchange data source connection data with the specified UUID does not exist in the storage.")

    def from_base(self, conn_base: TXExchangeDataSourceConnectionDataBase):
        self._uuid = conn_base.uuid
        self.user = conn_base.user
        self.data_source = conn_base.data_source
        self.connection_data = conn_base.connection_data
        self._stored = False
        self._from_storage(self._uuid, update=False)
        self.save()

    def save(self):
        if self._stored:
            self._storage.update_exchange_data_source_connection_data(
                uuid=self.uuid,
                exchange_data_source_uuid=self.data_source.uuid,
                user_uuid=self.user.uuid,
                connection_data=self.connection_data,
            )
        else:
            self._uuid = self._storage.insert_exchange_data_source_connection_data(
                exchange_data_source_uuid=self.data_source.uuid,
                user_uuid=self.user.uuid,
                connection_data=self.connection_data,
                uuid=self.uuid,
            )
            self._stored = True


class TXCurrencyExchange(TXCurrencyExchangeBase):

    _storage: TXStorageBase = None
    _stored: bool = False

    def __init__(
        self,
        storage: TXStorageBase,
        currency_source: TXCurrencyBase,
        currency_target: TXCurrencyBase,
        value: float,
        datetime: int,
        uuid: str = None
    ):
        super().__init__(currency_source, currency_target, value, datetime, uuid)
        self._storage = storage
        self._from_storage(uuid)

    def _from_storage(self, uuid: str = None, update: bool = True):
        if uuid is not None:
            currency_exchanges = self._storage.get_currency_exchanges(
                TXCondition(TXStorageQueryOps.EQUALS, "currency_exchange_uuid", uuid)
            )
            if len(currency_exchanges) == 1:
                if update:
                    self.from_base(currency_exchanges[0])
                self._stored = True
                return
            if update:
                raise ValueError("The currency exchange with the specified UUID or token does not exist in the storage.")

    def from_base(self, currency_exchange_base: TXCurrencyExchangeBase):
        self._uuid = currency_exchange_base.uuid
        self.currency_source = currency_exchange_base.currency_source
        self.currency_target = currency_exchange_base.currency_target
        self.value = currency_exchange_base.value
        self.datetime = currency_exchange_base.datetime
        self.data_source = currency_exchange_base.data_source
        self._stored = False
        self._from_storage(self._uuid, update=False)
        self.save()

    def save(self):
        if self._stored:
            self._storage.update_currency_exchange(
                uuid=self.uuid,
                currency_uuid_source=self.currency_source.uuid,
                currency_uuid_target=self.currency_target.uuid,
                value=self.value,
                exchange_data_source_uuid=self.data_source.uuid
            )
        else:
            self._uuid = self._storage.insert_currency_exchange(
                currency_uuid_source=self.currency_source.uuid,
                currency_uuid_target=self.currency_target.uuid,
                value=self.value,
                exchange_data_source_uuid=self.data_source.uuid,
                uuid=self._uuid,
            )
            self._stored = True


class TXFinancialHub(TXFinancialHubBase):

    _storage: TXStorageBase = None
    _stored: bool = False

    def __init__(
        self,
        storage: TXStorageBase,
        name: str,
        allowed_operations: set[TXAssetType],
        uuid: str = None
    ):
        super().__init__(name, allowed_operations, uuid)
        self._storage = storage
        self._from_storage(uuid)

    def _from_storage(self, uuid: str | None = None, update: bool = True):
        if uuid:
            from_storage: list[TXFinancialHubBase] = self._storage.get_financial_hubs(
                TXCondition(TXStorageQueryOps.EQUALS, 'financial_hub_uuid', uuid)
            )
            if len(from_storage) == 1:
                if update:
                    self.from_base(from_storage[0])
                self._stored = True
                return
            if update:
                raise ValueError("The financial hub with the specified UUID does not exist in the storage.")

    def from_base(self, hub_base: TXFinancialHubBase):
        self._uuid = hub_base.uuid
        self.name = hub_base.name
        self.allowed_operations = hub_base.allowed_operations
        self.notes = hub_base.notes
        self._stored = False
        self._from_storage(self._uuid, update=False)
        self.save()

    def save(self):
        if self._stored:
            self._storage.update_financial_hub(
                uuid=self.uuid,
                name=self.name,
                allowed_operations=self.allowed_operations,
                notes=self.notes,
            )
        else:
            self._uuid = self._storage.insert_financial_hub(
                name=self.name,
                allowed_operations=self.allowed_operations,
                notes=self.notes,
                uuid=self._uuid,
            )
            self._stored = True


class TXFinancialHubConnectionData(TXFinancialHubConnectionDataBase):

    _storage: TXStorageBase = None
    _stored: bool = False

    def __init__(
        self,
        storage: TXStorageBase,
        user: TXUserBase,
        financial_hub: TXFinancialHubBase,
        connection_data: str,
        uuid: str = None
    ):
        super().__init__(user, financial_hub, connection_data, uuid)
        self._storage = storage
        self._from_storage(uuid)

    def _from_storage(self, uuid: str | None = None, update: bool = True):
        if uuid:
            from_storage: list[TXFinancialHubConnectionDataBase] = self._storage.get_financial_hub_connection_data(
                TXCondition(TXStorageQueryOps.EQUALS, 'financial_hub_connection_data_uuid', uuid)
            )
            if len(from_storage) == 1:
                if update:
                    self.from_base(from_storage[0])
                self._stored = True
                return
            if update:
                raise ValueError("The financial hub connection data with the specified UUID does not exist in the storage.")

    def from_base(self, conn_base: TXFinancialHubConnectionDataBase):
        self._uuid = conn_base.uuid
        self.user = conn_base.user
        self.financial_hub = conn_base.financial_hub
        self.connection_data = conn_base.connection_data
        self._stored = False
        self._from_storage(self._uuid, update=False)
        self.save()

    def save(self):
        if self._stored:
            self._storage.update_financial_hub_connection_data(
                uuid=self.uuid,
                financial_hub_uuid=self.financial_hub.uuid,
                user_uuid=self.user.uuid,
                connection_data=self.connection_data,
            )
        else:
            self._uuid = self._storage.insert_financial_hub_connection_data(
                financial_hub_uuid=self.financial_hub.uuid,
                user_uuid=self.user.uuid,
                connection_data=self.connection_data,
                uuid=self.uuid,
            )
            self._stored = True


class TXWallet(TXWalletBase):

    _storage: TXStorageBase = None
    _stored: bool = False

    def __init__(
        self,
        storage: TXStorageBase,
        user: TXUserBase,
        financial_hub: TXFinancialHubBase,
        currency: TXCurrencyBase | None,
        name: str,
        content_type: TXAssetType,
        uuid: str | None = None,
    ):
        super().__init__(user, financial_hub, currency, name, content_type, uuid)
        self._storage = storage
        self._from_storage(uuid)

    def _from_storage(self, uuid: str | None = None, update: bool = True):
        if uuid:
            from_storage: list[TXWalletBase] = self._storage.get_wallets(
                TXCondition(TXStorageQueryOps.EQUALS, 'wallet_uuid', uuid)
            )
            if len(from_storage) == 1:
                if update:
                    self.from_base(from_storage[0])
                self._stored = True
                return
            if update:
                raise ValueError("The wallet with the specified UUID does not exist in the storage.")

    def from_base(self, wallet_base: TXWalletBase):
        self._uuid = wallet_base.uuid
        self.user = wallet_base.user
        self.financial_hub = wallet_base.financial_hub
        self.asset = wallet_base.asset
        self.currency = wallet_base.currency
        self.name = wallet_base.name
        self.content_type = wallet_base.content_type
        self.details_data = wallet_base.details_data
        self.initial_value = wallet_base.initial_value
        self.initial_value_datetime = wallet_base.initial_value_datetime
        self.total_value = wallet_base.total_value
        self.total_value_datetime = wallet_base.total_value_datetime
        self.connection_data = wallet_base.connection_data
        self._stored = False
        self._from_storage(self._uuid, update=False)
        self.save()

    def save(self):
        if self._stored:
            self._storage.update_wallet(
                uuid=self.uuid,
                user_uuid=self.user.uuid,
                financial_hub_uuid=self.financial_hub.uuid,
                name=self.name,
                content_type=self.content_type,
                currency_uuid=(self.currency.uuid if self.currency else None),
                details_data=self.details_data,
                initial_value=self.initial_value,
                initial_value_datetime=self.initial_value_datetime,
                total_value=self.total_value,
                total_value_datetime=self.total_value_datetime,
                connection_data=self.connection_data,
            )
        else:
            self._uuid = self._storage.insert_wallet(
                user_uuid=self.user.uuid,
                financial_hub_uuid=self.financial_hub.uuid,
                name=self.name,
                content_type=self.content_type,
                asset_uuid=(self.asset.uuid if self.asset else None),
                currency_uuid=(self.currency.uuid if self.currency else None),
                details_data=self.details_data,
                initial_value=self.initial_value,
                initial_value_datetime=self.initial_value_datetime,
                total_value=self.total_value,
                total_value_datetime=self.total_value_datetime,
                connection_data=self.connection_data,
                uuid=self._uuid,
            )
            self._stored = True


class TXTransaction(TXTransactionBase):

    _storage: TXStorageBase = None
    _stored: bool = False

    def __init__(
        self,
        storage: TXStorageBase,
        uuid: str | None = None,
    ):
        super().__init__(uuid)
        self._storage = storage
        self._from_storage(uuid)

    def _from_storage(self, uuid: str | None = None, update: bool = True):
        if uuid:
            from_storage: list[TXTransactionBase] = self._storage.get_transactions(
                TXCondition(TXStorageQueryOps.EQUALS, 'transaction_uuid', uuid)
            )
            if len(from_storage) == 1:
                if update:
                    self.from_base(from_storage[0])
                self._stored = True
                return
            if update:
                raise ValueError("The transaction with the specified UUID does not exist in the storage.")

    def from_base(self, transaction_base: TXTransactionBase):
        self._uuid = transaction_base.uuid
        self.origin_transaction = transaction_base.origin_transaction
        self.source_wallet = transaction_base.source_wallet
        self.target_wallet = transaction_base.target_wallet
        self.bot = transaction_base.bot
        self.start_datetime = transaction_base.start_datetime
        self.end_datetime = transaction_base.end_datetime
        self.operational_mode = transaction_base.operational_mode
        self.source_value = transaction_base.source_value
        self.target_value = transaction_base.target_value
        self.status = transaction_base.status
        self.annotations = transaction_base.annotations
        self.order = transaction_base.order
        self._stored = False
        self._from_storage(self._uuid, update=False)
        self.save()

    def save(self):
        if self._stored:
            self._storage.update_transaction(
                uuid=self.uuid,
                origin_transaction_uuid=(self.origin_transaction.uuid if self.origin_transaction else None),
                source_wallet_uuid=(self.source_wallet.uuid if self.source_wallet else None),
                target_wallet_uuid=(self.target_wallet.uuid if self.target_wallet else None),
                bot_uuid=(self.bot.uuid if self.bot else None),
                start_datetime=self.start_datetime,
                end_datetime=self.end_datetime,
                operational_mode=self.operational_mode,
                source_value=self.source_value,
                target_value=self.target_value,
                status=self.status,
                annotations=self.annotations,
                order=self.order,
            )
        else:
            self._uuid = self._storage.insert_transaction(
                origin_transaction_uuid=(self.origin_transaction.uuid if self.origin_transaction else None),
                source_wallet_uuid=(self.source_wallet.uuid if self.source_wallet else None),
                target_wallet_uuid=(self.target_wallet.uuid if self.target_wallet else None),
                bot_uuid=(self.bot.uuid if self.bot else None),
                start_datetime=self.start_datetime,
                end_datetime=self.end_datetime,
                operational_mode=self.operational_mode,
                source_value=self.source_value,
                target_value=self.target_value,
                status=self.status,
                annotations=self.annotations,
                order=self.order,
                uuid=self._uuid,
            )
            self._stored = True

