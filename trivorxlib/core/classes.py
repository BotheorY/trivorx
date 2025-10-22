from .base import *
from trivorxlib.storages.base import *
from abc import abstractmethod
import json

class TXUtilsEx(TXUtils):
    """
    Extended utility class providing additional helper methods for TrivorX operations.
    
    This class extends the base TXUtils class with specialized methods for handling currency exchanges and connection data management.
    """

    @staticmethod
    def insert_currency_exchange_if_not_exists(storage: TXStorageBase, currency_exchange: TXCurrencyExchangeBase):
        """
        Insert a currency exchange record into storage if it doesn't already exist.
        
        This method checks if a currency exchange record with the same datetime, source currency, and target currency already exists. If not, it inserts the new record to avoid duplicates.
        
        Args:
            storage (TXStorageBase): The storage instance to use for database operations.
            currency_exchange (TXCurrencyExchangeBase): The currency exchange object to insert.
            
        Returns:
            None
            
        Note:
            This method performs a query to check for existing records before insertion,
            which helps maintain data integrity and prevents duplicate entries.
        """
        rows: list[TXCurrencyExchangeBase] = storage.get_currency_exchanges(
            TXLogicalQuery(
                TXStorageQueryOps.AND, 
                TXCondition(
                    TXStorageQueryOps.EQUALS, 'UNIX_TIMESTAMP(datetime)', currency_exchange.datetime
                ),
                TXLogicalQuery(
                    TXStorageQueryOps.AND, 
                    TXCondition(
                        TXStorageQueryOps.EQUALS, 'currency_uuid_source', currency_exchange.currency_source.uuid
                    ),
                    TXCondition(
                        TXStorageQueryOps.EQUALS, 'currency_uuid_target', currency_exchange.currency_target.uuid
                    )
                )
            )
        )
        if not rows:
            storage.insert_currency_exchange(currency_exchange.currency_source.uuid, currency_exchange.currency_target.uuid, currency_exchange.value, currency_exchange.data_source.uuid, currency_exchange.datetime, currency_exchange.uuid)

    @staticmethod
    def get_exchange_connection_data(exchange_uuid: str, storage: TXStorageBase, user: TXUserBase) -> tuple[dict, str]:
        """
        Retrieve exchange connection data for a specific user and exchange data source.
        
        Args:
            exchange_uuid (str): The UUID of the exchange data source.
            storage (TXStorageBase): The storage instance to use for database operations.
            user (TXUserBase): The user for whom to retrieve connection data.
            
        Returns:
            tuple[dict, str]: A tuple containing the parsed connection data as a dictionary and the connection data UUID as a string.
                            
        Raises:
            ValueError: If no connection data is found for the given user and exchange.
            
        Note:
            The connection data is stored as JSON string and is parsed before returning.
        """
        rows: list[TXExchangeDataSourceConnectionDataBase] = storage.get_exchange_data_source_connection_data(
            TXLogicalQuery(
                TXStorageQueryOps.AND, 
                TXCondition(TXStorageQueryOps.EQUALS, 'exchange_data_source_uuid', exchange_uuid),
                TXCondition(TXStorageQueryOps.EQUALS, 'user_uuid', user.uuid)
            )
        )
        if not rows:
            raise ValueError("No connection data found for the given user")
        return json.loads(rows[0].connection_data), rows[0].uuid

class TXUser(TXUserBase):
    """
    User management class with storage persistence capabilities.
    
    This class extends TXUserBase to provide automatic storage synchronization, allowing users to be loaded from and saved to persistent storage. It manages the lifecycle of user objects including creation, updates, and storage state tracking.
    
    Attributes:
        _storage (TXStorageBase): The storage backend for persistence operations.
        _stored (bool): Flag indicating whether the user exists in storage.
    """

    _storage: TXStorageBase = None
    _stored: bool = False

    def __init__(self, storage: TXStorageBase, uuid: Optional[str] = None, token: Optional[str] = None, encrypted_password: Optional[str] = None):
        """
        Initialize a TXUser instance with storage backend.
        
        Args:
            storage (TXStorageBase): The storage backend to use for persistence.
            uuid (Optional[str]): The user's UUID. If provided, loads user from storage.
            token (Optional[str]): The user's authentication token. If provided, loads user from storage.
            encrypted_password (Optional[str]): The user's encrypted password for new users.
            
        Note:
            If either uuid or token is provided, the constructor will attempt to load the user from storage. If both are None, a new user instance is created.
        """
        super().__init__(uuid, token, encrypted_password)
        self._storage = storage 
        self._from_storage(uuid, token)

    def _from_storage(self, uuid: Optional[str] = None, token: Optional[str] = None, update: Optional[bool] = True):
        """
        Load user data from storage using UUID or token.
        
        Args:
            uuid (Optional[str]): The user's UUID to search for.
            token (Optional[str]): The user's token to search for.
            update (Optional[bool]): Whether to update the current instance with loaded data.
            Defaults to True.
                                   
        Raises:
            ValueError: If update is True and no user is found with the specified UUID or token.
            
        Note:
            This method uses OR logic to search by either UUID or token. If a user is found, the _stored flag is set to True to indicate the user exists in storage.
        """
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
        """
        Update this user instance with data from a base user object.
        
        Args:
            user_base (TXUserBase): The base user object containing the data to copy.
            
        Note:
            This method copies all user attributes from the base object and automatically saves the changes to storage. The _stored flag is temporarily set to False during the operation to ensure proper storage synchronization.
        """
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
        """
        Persist the user data to storage.
        
        This method either updates an existing user record or inserts a new one, depending on the _stored flag. After successful operation, _stored is set to True.
        
        Note:
            The method automatically determines whether to perform an INSERT or UPDATE operation based on the current storage state of the user.
        """
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
    """
    Bot management class with storage persistence capabilities.
    
    This class extends TXBotBase to provide automatic storage synchronization for trading bots. It manages bot lifecycle including creation, updates, and algorithm configuration persistence.
    
    Attributes:
        _storage (TXStorageBase): The storage backend for persistence operations.
        _stored (bool): Flag indicating whether the bot exists in storage.
    """

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
        uuid: Optional[str] = None
    ):
        """
        Initialize a TXBot instance with storage backend.
        
        Args:
            storage (TXStorageBase): The storage backend to use for persistence.
            user (TXUserBase): The user who owns this bot.
            algo_uuid (str): The UUID of the algorithm this bot uses.
            name (str): The display name for this bot.
            algo_name (str): The name of the algorithm.
            algo_ver (str): The version of the algorithm.
            algo_settings (str): JSON string containing algorithm configuration settings.
            uuid (Optional[str]): The bot's UUID. If provided, loads bot from storage.
        """
        super().__init__(user, algo_uuid, name, algo_name, algo_ver, algo_settings, uuid)
        self._storage = storage
        self._from_storage(uuid)

    def _from_storage(self, uuid: Optional[str] = None, update: Optional[bool] = True): 
        """
        Load bot data from storage using UUID.
        
        Args:
            uuid (Optional[str]): The bot's UUID to search for.
            update (Optional[bool]): Whether to update the current instance with loaded data. Defaults to True.
                                   
        Raises:
            ValueError: If update is True and no bot is found with the specified UUID.
        """
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
        """
        Update this bot instance with data from a base bot object.
        
        Args:
            bot_base (TXBotBase): The base bot object containing the data to copy.
            
        Note:
            This method copies all bot attributes from the base object and automatically saves the changes to storage.
        """
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
        """
        Persist the bot data to storage.
        
        This method either updates an existing bot record or inserts a new one, depending on the _stored flag. After successful operation, _stored is set to True.
        """
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
    """
    Currency management class with storage persistence capabilities.
    
    This class extends TXCurrencyBase to provide automatic storage synchronization for currency objects. 
    It manages the lifecycle of currency entities including creation, updates, and storage state tracking.
    
    Attributes:
        _storage (TXStorageBase): The storage backend for persistence operations.
        _stored (bool): Flag indicating whether the currency exists in storage.
    """

    _storage: TXStorageBase = None
    _stored: bool = False

    def __init__(
        self,
        storage: TXStorageBase,
        long_name: str,
        short_name: str,
        currency_type: TXCurrencyType,
        uuid: Optional[str] = None
    ):
        """
        Initialize a TXCurrency instance with storage backend.
        
        Args:
            storage (TXStorageBase): The storage backend to use for persistence.
            long_name (str): The full name of the currency (e.g., "United States Dollar").
            short_name (str): The abbreviated name of the currency (e.g., "USD").
            currency_type (TXCurrencyType): The type/category of the currency.
            uuid (Optional[str]): The currency's UUID. If provided, loads currency from storage.
            
        Note:
            If uuid is provided, the constructor will attempt to load the currency from storage.
            If uuid is None, a new currency instance is created.
        """
        super().__init__(uuid)
        self.long_name = long_name
        self.short_name = short_name
        self.currency_type = currency_type
        self._storage = storage
        self._from_storage(uuid)

    def _from_storage(self, uuid: Optional[str] = None, update: Optional[bool] = True):
        """
        Load currency data from storage using UUID.
        
        Args:
            uuid (Optional[str]): The currency's UUID to search for.
            update (Optional[bool]): Whether to update the current instance with loaded data. Defaults to True.
                                   
        Raises:
            ValueError: If update is True and no currency is found with the specified UUID.
            
        Note:
            If a currency is found, the _stored flag is set to True to indicate the currency exists in storage.
        """
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
        """
        Update this currency instance with data from a base currency object.
        
        Args:
            currency_base (TXCurrencyBase): The base currency object containing the data to copy.
            
        Note:
            This method copies all currency attributes from the base object and automatically saves the changes to storage. The _stored flag is temporarily set to False during the operation to ensure proper storage synchronization.
        """
        self._uuid = currency_base.uuid
        self.long_name = currency_base.long_name
        self.short_name = currency_base.short_name
        self.currency_type = currency_base.currency_type
        self._stored = False
        self._from_storage(self._uuid, update=False)
        self.save()

    def save(self):
        """
        Persist the currency data to storage.
        
        This method either updates an existing currency record or inserts a new one, depending on the _stored flag. After successful operation, _stored is set to True.
        
        Note:
            The method automatically determines whether to perform an INSERT or UPDATE operation based on the current storage state of the currency.
        """
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
    """
    Exchange data source management class with storage persistence capabilities.
    
    This class extends TXExchangeDataSourceBase to provide automatic storage synchronization for exchange data sources. It manages data source configurations and connection requirements for currency exchange rate providers.
    
    Attributes:
        _storage (TXStorageBase): The storage backend for persistence operations.
        _stored (bool): Flag indicating whether the exchange data source exists in storage.
    """

    _storage: TXStorageBase = None
    _stored: bool = False

    def __init__(
        self,
        storage: TXStorageBase,
        uuid: Optional[str] = None
    ):
        """
        Initialize a TXExchangeDataSource instance with storage backend.
        
        Args:
            storage (TXStorageBase): The storage backend to use for persistence.
            uuid (Optional[str]): The exchange data source's UUID. If provided, loads from storage.
            
        Note:
            If uuid is provided, the constructor will attempt to load the exchange data source 
            from storage. If uuid is None, a new instance is created.
        """
        super().__init__(uuid)
        self._storage = storage
        self._from_storage(uuid)

    def get_currency_exchange(self, currency_source: TXCurrencyBase, currency_target: TXCurrencyBase, user: Optional[TXUserBase] = None, datetime: Optional[int] = None, force_live_data: Optional[bool] = False) -> TXCurrencyExchangeBase:
        """
        Retrieve a currency exchange rate between two currencies at a specific datetime.
        
        This method fetches exchange rate data for converting from a source currency to a target currency.
        If datetime is None, the current datetime is used.

        Args:
            currency_source (TXCurrencyBase): The source currency to convert from.
            currency_target (TXCurrencyBase): The target currency to convert to.
            user (Optional[TXUserBase]): The user requesting the exchange rate (may be required for some data sources).
            datetime (Optional[int]): The datetime for which to retrieve the exchange rate (Unix timestamp). If None, uses current time.
            force_live_data (Optional[bool]): Whether to force retrieval of live data instead of cached data. Defaults to False.

        Returns:
            TXCurrencyExchangeBase: An object representing the exchange rate between the currencies.
            
        Returns:
            None: If the exchange rate cannot be retrieved for the given parameters.
            
        Note:
            This is an abstract method that must be implemented by concrete subclasses.
            The implementation should handle data source-specific logic for retrieving exchange rates.
        """
        return None

    def _from_storage(self, uuid: Optional[str] = None, update: Optional[bool] = True):
        """
        Load exchange data source from storage using UUID.
        
        Args:
            uuid (Optional[str]): The exchange data source's UUID to search for.
            update (Optional[bool]): Whether to update the current instance with loaded data. Defaults to True.
                                   
        Raises:
            ValueError: If update is True and no exchange data source is found with the specified UUID.
            
        Note:
            If an exchange data source is found, the _stored flag is set to True to indicate it exists in storage.
        """
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
        """
        Update this exchange data source instance with data from a base object.
        
        Args:
            exchange_data_source_base (TXExchangeDataSourceBase): The base exchange data source object containing the data to copy.
            
        Note:
            This method copies all exchange data source attributes from the base object and automatically saves the changes to storage. The _stored flag is temporarily set to False during the operation to ensure proper storage synchronization.
        """
        self._uuid = exchange_data_source_base.uuid
        self._name = exchange_data_source_base._name
        self._available_currency_types = exchange_data_source_base._available_currency_types
        self._connection_data_required = exchange_data_source_base._connection_data_required
        self._default_for_types = exchange_data_source_base._default_for_types
        self.notes = exchange_data_source_base.notes
        self._stored = False
        self._from_storage(self._uuid, update=False)
        self.save()

    def save(self):
        """
        Persist the exchange data source data to storage.
        
        This method either updates an existing exchange data source record or inserts a new one, depending on the _stored flag. After successful operation, _stored is set to True.
        
        Note:
            The method automatically determines whether to perform an INSERT or UPDATE operation based on the current storage state of the exchange data source.
        """
        if self._stored:
            self._storage.update_exchange_data_source(
                uuid=self.uuid,
                name=self._name,
                available_currency_types=self._available_currency_types,
                connection_data_required=self._connection_data_required,
                default_for_types=self._default_for_types,
                notes=self.notes,
            )
        else:
            self._uuid = self._storage.insert_exchange_data_source(
                name=self._name,
                available_currency_types=self._available_currency_types,
                connection_data_required=self._connection_data_required,
                default_for_types=self._default_for_types,  
                notes=self.notes,
                uuid=self.uuid,
            )
            self._stored = True            

class TXExchangeDataSourceConnectionData(TXExchangeDataSourceConnectionDataBase):
    """
    Exchange data source connection data management class with storage persistence capabilities.
    
    This class extends TXExchangeDataSourceConnectionDataBase to provide automatic storage synchronization for user-specific connection data required by exchange data sources. 
    It manages authentication credentials and configuration data needed to access external exchange rate APIs.
    
    Attributes:
        _storage (TXStorageBase): The storage backend for persistence operations.
        _stored (bool): Flag indicating whether the connection data exists in storage.
    """

    _storage: TXStorageBase = None
    _stored: bool = False

    def __init__(
        self,
        storage: TXStorageBase,
        user: TXUserBase,
        data_source: TXExchangeDataSourceBase,
        connection_data: str,
        uuid: Optional[str] = None
    ):
        """
        Initialize a TXExchangeDataSourceConnectionData instance with storage backend.
        
        Args:
            storage (TXStorageBase): The storage backend to use for persistence.
            user (TXUserBase): The user who owns this connection data.
            data_source (TXExchangeDataSourceBase): The exchange data source this connection data is for.
            connection_data (str): JSON string containing the connection configuration and credentials.
            uuid (Optional[str]): The connection data's UUID. If provided, loads from storage.
            
        Note:
            The connection_data parameter should contain all necessary authentication and configuration information required by the specific exchange data source.
        """
        super().__init__(user, data_source, connection_data, uuid)
        self._storage = storage
        self._from_storage(uuid)

    def _from_storage(self, uuid: Optional[str] = None, update: Optional[bool] = True):
        """
        Load exchange data source connection data from storage using UUID.
        
        Args:
            uuid (Optional[str]): The connection data's UUID to search for.
            update (Optional[bool]): Whether to update the current instance with loaded data. Defaults to True.
                                   
        Raises:
            ValueError: If update is True and no connection data is found with the specified UUID.
            
        Note:
            If connection data is found, the _stored flag is set to True to indicate it exists in storage.
        """
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
        """
        Update this connection data instance with data from a base object.
        
        Args:
            conn_base (TXExchangeDataSourceConnectionDataBase): The base connection data object containing the data to copy.
            
        Note:
            This method copies all connection data attributes from the base object and automatically saves the changes to storage. The _stored flag is temporarily set to False during the operation to ensure proper storage synchronization.
        """
        self._uuid = conn_base.uuid
        self.user = conn_base.user
        self.data_source = conn_base.data_source
        self.connection_data = conn_base.connection_data
        self._stored = False
        self._from_storage(self._uuid, update=False)
        self.save()

    def save(self):
        """
        Persist the connection data to storage.
        
        This method either updates an existing connection data record or inserts a new one, depending on the _stored flag. After successful operation, _stored is set to True.
        
        Note:
            The method automatically determines whether to perform an INSERT or UPDATE operation based on the current storage state of the connection data.
        """
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
    """
    Currency exchange rate management class with storage persistence capabilities.
    
    This class extends TXCurrencyExchangeBase to provide automatic storage synchronization for currency exchange rate records. It manages historical and real-time exchange rate data between different currencies.
    
    Attributes:
        _storage (TXStorageBase): The storage backend for persistence operations.
        _stored (bool): Flag indicating whether the currency exchange exists in storage.
    """

    _storage: TXStorageBase = None
    _stored: bool = False

    def __init__(
        self,
        storage: TXStorageBase,
        currency_source: TXCurrencyBase,
        currency_target: TXCurrencyBase,
        value: float,
        datetime: int,
        uuid: Optional[str] = None
    ):
        """
        Initialize a TXCurrencyExchange instance with storage backend.
        
        Args:
            storage (TXStorageBase): The storage backend to use for persistence.
            currency_source (TXCurrencyBase): The source currency being converted from.
            currency_target (TXCurrencyBase): The target currency being converted to.
            value (float): The exchange rate value (how much of target currency equals 1 unit of source currency).
            datetime (int): The timestamp when this exchange rate was valid (Unix timestamp).
            uuid (Optional[str]): The currency exchange's UUID. If provided, loads from storage.
            
        Note:
            The value represents the conversion rate from source to target currency.
            For example, if converting USD to EUR with value=0.85, then 1 USD = 0.85 EUR.
        """
        super().__init__(currency_source, currency_target, value, datetime, uuid)
        self._storage = storage
        self._from_storage(uuid)

    def _from_storage(self, uuid: Optional[str] = None, update: Optional[bool] = True):
        """
        Load currency exchange data from storage using UUID.
        
        Args:
            uuid (Optional[str]): The currency exchange's UUID to search for.
            update (Optional[bool]): Whether to update the current instance with loaded data. Defaults to True.
                                   
        Raises:
            ValueError: If update is True and no currency exchange is found with the specified UUID.
            
        Note:
            If a currency exchange is found, the _stored flag is set to True to indicate it exists in storage.
        """
        if uuid:
            currency_exchanges: list[TXCurrencyExchangeBase] = self._storage.get_currency_exchanges(
                TXCondition(TXStorageQueryOps.EQUALS, "currency_exchange_uuid", uuid)
            )
            if len(currency_exchanges) == 1:
                if update:
                    self.from_base(currency_exchanges[0])
                self._stored = True
                return
            if update:
                raise ValueError("The currency exchange with the specified UUID does not exist in the storage.")

    def from_base(self, currency_exchange_base: TXCurrencyExchangeBase):
        """
        Update this currency exchange instance with data from a base object.
        
        Args:
            currency_exchange_base (TXCurrencyExchangeBase): The base currency exchange object containing the data to copy.
            
        Note:
            This method copies all currency exchange attributes from the base object and automatically saves the changes to storage. The _stored flag is temporarily set to False during the operation to ensure proper storage synchronization.
        """
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
        """
        Persist the currency exchange data to storage.
        
        This method either updates an existing currency exchange record or inserts a new one, depending on the _stored flag. After successful operation, _stored is set to True.
        
        Note:
            The method automatically determines whether to perform an INSERT or UPDATE operation based on the current storage state of the currency exchange.
        """
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
    """
    Financial hub management class with storage persistence capabilities.
    
    This class extends TXFinancialHubBase to provide automatic storage synchronization for financial hubs.
    Financial hubs represent external financial service providers or platforms that can execute transactions and manage financial operations. This class manages the lifecycle of financial hub configurations including creation, updates, and connection requirements.
    
    Attributes:
        _storage (TXStorageBase): The storage backend for persistence operations.
        _stored (bool): Flag indicating whether the financial hub exists in storage.
    """

    _storage: TXStorageBase = None
    _stored: bool = False

    @staticmethod
    def get_connection_data_schema() -> dict[str, TXDataSchemaItem]:
        """
        Get the schema definition for connection data required by this financial hub.
        
        This abstract method must be implemented by concrete subclasses to define the structure and validation rules for connection data specific to each financial hub type.
        
        Returns:
            dict[str, TXDataSchemaItem]: A dictionary mapping field names to their schema definitions, including data types, validation rules, and requirements.
                                       
        Note:
            The schema is used to validate connection data before storing it and to generate user interfaces for connection configuration.
        """
        return None

    def __init__(
        self,
        storage: TXStorageBase,
        uuid: Optional[str] = None
    ):
        """
        Initialize a TXFinancialHub instance with storage backend.
        
        Args:
            storage (TXStorageBase): The storage backend to use for persistence.
            uuid (Optional[str]): The financial hub's UUID. If provided, loads from storage.
            
        Note:
            If uuid is provided, the constructor will attempt to load the financial hub from storage. If uuid is None, a new instance is created.
        """
        super().__init__(uuid)
        self._storage = storage
        self._from_storage(uuid)

    def create_transaction(self, transaction: TXTransactionBase) -> TXTransactionBase:
        """
        Create and execute a transaction through this financial hub.
        
        This abstract method must be implemented by concrete subclasses to handle the specific transaction creation logic for each financial hub type.
        
        Args:
            transaction (TXTransactionBase): The transaction object containing all necessary information for execution.
                                           
        Returns:
            TXTransactionBase: The updated transaction object with execution results, including status, timestamps, and any additional data.
                             
        Note:
            Implementations should handle all aspects of transaction execution including validation, submission to the financial hub, and status tracking.
        """
        return None

    def _from_storage(self, uuid: Optional[str] = None, update: Optional[bool] = True):
        """
        Load financial hub data from storage using UUID.
        
        Args:
            uuid (Optional[str]): The financial hub's UUID to search for.
            update (Optional[bool]): Whether to update the current instance with loaded data. Defaults to True.
                                   
        Raises:
            ValueError: If update is True and no financial hub is found with the specified UUID.
            
        Note:
            If a financial hub is found, the _stored flag is set to True to indicate it exists in storage.
        """
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
        """
        Update this financial hub instance with data from a base object.
        
        Args:
            hub_base (TXFinancialHubBase): The base financial hub object containing the data to copy.
            
        Note:
            This method copies all financial hub attributes from the base object and automatically saves the changes to storage. The _stored flag is temporarily set to False during the
            operation to ensure proper storage synchronization.
        """
        self._uuid = hub_base.uuid
        self._name = hub_base._name
        self._allowed_operations = hub_base._allowed_operations
        self.notes = hub_base.notes
        self._stored = False
        self._from_storage(self._uuid, update=False)
        self.save()

    def save(self):
        """
        Persist the financial hub data to storage.
        
        This method either updates an existing financial hub record or inserts a new one, depending on the _stored flag. After successful operation, _stored is set to True.
        
        Note:
            The method automatically determines whether to perform an INSERT or UPDATE operation based on the current storage state of the financial hub.
        """
        if self._stored:
            self._storage.update_financial_hub(
                uuid=self.uuid,
                name=self._name,
                allowed_operations=self._allowed_operations,
                notes=self.notes,
            )
        else:
            self._uuid = self._storage.insert_financial_hub(
                name=self._name,
                allowed_operations=self._allowed_operations,
                notes=self.notes,
                uuid=self._uuid,
            )
            self._stored = True


class TXFinancialHubConnectionData(TXFinancialHubConnectionDataBase):
    """
    Financial hub connection data management class with storage persistence capabilities.
    
    This class extends TXFinancialHubConnectionDataBase to provide automatic storage synchronization for user-specific connection data required by financial hubs. It manages authentication credentials
    and configuration data needed to access external financial service providers and execute transactions through their APIs or interfaces.
    
    Attributes:
        _storage (TXStorageBase): The storage backend for persistence operations.
        _stored (bool): Flag indicating whether the connection data exists in storage.
    """

    _storage: TXStorageBase = None
    _stored: bool = False

    def __init__(
        self,
        storage: TXStorageBase,
        user: TXUserBase,
        financial_hub: TXFinancialHubBase,
        connection_data: str,
        uuid: Optional[str] = None
    ):
        """
        Initialize a TXFinancialHubConnectionData instance with storage backend.
        
        Args:
            storage (TXStorageBase): The storage backend to use for persistence.
            user (TXUserBase): The user who owns this connection data.
            financial_hub (TXFinancialHubBase): The financial hub this connection data is for.
            connection_data (str): JSON string containing the connection configuration and credentials.
            uuid (Optional[str]): The connection data's UUID. If provided, loads from storage.
            
        Note:
            The connection_data parameter should contain all necessary authentication and configuration information required by the specific financial hub, formatted as a JSON string.
        """
        super().__init__(user, financial_hub, connection_data, uuid)
        self._storage = storage
        self._from_storage(uuid)

    def _from_storage(self, uuid: Optional[str] = None, update: Optional[bool] = True):
        """
        Load financial hub connection data from storage using UUID.
        
        Args:
            uuid (Optional[str]): The connection data's UUID to search for.
            update (Optional[bool]): Whether to update the current instance with loaded data. Defaults to True.
                                   
        Raises:
            ValueError: If update is True and no connection data is found with the specified UUID.
            
        Note:
            If connection data is found, the _stored flag is set to True to indicate it exists in storage.
        """
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
        """
        Update this connection data instance with data from a base object.
        
        Args:
            conn_base (TXFinancialHubConnectionDataBase): The base connection data object containing the data to copy.
            
        Note:
            This method copies all connection data attributes from the base object and automatically saves the changes to storage. The _stored flag is temporarily set to False during the
            operation to ensure proper storage synchronization.
        """
        self._uuid = conn_base.uuid
        self.user = conn_base.user
        self.financial_hub = conn_base.financial_hub
        self.connection_data = conn_base.connection_data
        self._stored = False
        self._from_storage(self._uuid, update=False)
        self.save()

    def save(self):
        """
        Persist the connection data to storage.
        
        This method either updates an existing connection data record or inserts a new one, depending on the _stored flag. After successful operation, _stored is set to True.
        
        Note:
            The method automatically determines whether to perform an INSERT or UPDATE operation based on the current storage state of the connection data.
        """
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
    """
    Wallet management class with storage persistence capabilities.
    
    This class extends TXWalletBase to provide automatic storage synchronization for digital wallets.
    Wallets represent containers for financial assets (currencies, cryptocurrencies, stocks, etc.) within specific financial hubs. They track asset balances, transaction history, and connection details required to access the underlying financial accounts or services.
    
    Attributes:
        _storage (TXStorageBase): The storage backend for persistence operations.
        _stored (bool): Flag indicating whether the wallet exists in storage.
    """

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
        uuid: Optional[str] = None,
    ):
        """
        Initialize a TXWallet instance with storage backend.
        
        Args:
            storage (TXStorageBase): The storage backend to use for persistence.
            user (TXUserBase): The user who owns this wallet.
            financial_hub (TXFinancialHubBase): The financial hub where this wallet is hosted.
            currency (TXCurrencyBase | None): The primary currency for this wallet, if applicable.
            name (str): The display name for this wallet.
            content_type (TXAssetType): The type of assets this wallet can contain.
            uuid (Optional[str]): The wallet's UUID. If provided, loads wallet from storage.
            
        Note:
            The currency parameter can be None for wallets that contain multiple currencies or non-currency assets like stocks or commodities.
        """
        super().__init__(user, financial_hub, currency, name, content_type, uuid)
        self._storage = storage
        self._from_storage(uuid)

    def _from_storage(self, uuid: Optional[str] = None, update: Optional[bool] = True):
        """
        Load wallet data from storage using UUID.
        
        Args:
            uuid (Optional[str]): The wallet's UUID to search for.
            update (Optional[bool]): Whether to update the current instance with loaded data. Defaults to True.
                                   
        Raises:
            ValueError: If update is True and no wallet is found with the specified UUID.
            
        Note:
            If a wallet is found, the _stored flag is set to True to indicate it exists in storage.
        """
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
        """
        Update this wallet instance with data from a base wallet object.
        
        Args:
            wallet_base (TXWalletBase): The base wallet object containing the data to copy.
            
        Note:
            This method copies all wallet attributes from the base object and automatically saves the changes to storage. The _stored flag is temporarily set to False during the operation to ensure proper storage synchronization.
        """
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
        """
        Persist the wallet data to storage.
        
        This method either updates an existing wallet record or inserts a new one, depending on the _stored flag. After successful operation, _stored is set to True.
        
        Note:
            The method automatically determines whether to perform an INSERT or UPDATE operation based on the current storage state of the wallet. It handles both asset_uuid and currency_uuid fields appropriately based on the wallet's content type.
        """
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
    """
    Transaction management class with storage persistence capabilities.
    
    This class extends TXTransactionBase to provide automatic storage synchronization for financial transactions.
    Transactions represent the movement of assets between wallets, either manually initiated by users or automatically executed by trading bots. They track the complete lifecycle of financial operations
    including initiation, execution, and completion status.
    
    Attributes:
        _storage (TXStorageBase): The storage backend for persistence operations.
        _stored (bool): Flag indicating whether the transaction exists in storage.
    """

    _storage: TXStorageBase = None
    _stored: bool = False

    def __init__(
        self,
        storage: TXStorageBase,
        uuid: Optional[str] = None,
    ):
        """
        Initialize a TXTransaction instance with storage backend.
        
        Args:
            storage (TXStorageBase): The storage backend to use for persistence.
            uuid (Optional[str]): The transaction's UUID. If provided, loads transaction from storage.
            
        Note:
            If uuid is provided, the constructor will attempt to load the transaction from storage.
            If uuid is None, a new transaction instance is created that can be populated with data before saving.
        """
        super().__init__(uuid)
        self._storage = storage
        self._from_storage(uuid)

    def _from_storage(self, uuid: Optional[str] = None, update: Optional[bool] = True):
        """
        Load transaction data from storage using UUID.
        
        Args:
            uuid (Optional[str]): The transaction's UUID to search for.
            update (Optional[bool]): Whether to update the current instance with loaded data. Defaults to True.
                                   
        Raises:
            ValueError: If update is True and no transaction is found with the specified UUID.
            
        Note:
            If a transaction is found, the _stored flag is set to True to indicate it exists in storage.
        """
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
        """
        Update this transaction instance with data from a base transaction object.
        
        Args:
            transaction_base (TXTransactionBase): The base transaction object containing the data to copy.
            
        Note:
            This method copies all transaction attributes from the base object and automatically saves the changes to storage. The _stored flag is temporarily set to False during the operation to ensure proper storage synchronization.
        """
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
        """
        Persist the transaction data to storage.
        
        This method either updates an existing transaction record or inserts a new one, depending on the _stored flag. After successful operation, _stored is set to True.
        
        Note:
            The method automatically determines whether to perform an INSERT or UPDATE operation based on the current storage state of the transaction. It properly handles optional foreign key references (origin_transaction, source_wallet, target_wallet, bot) by checking for None values before accessing UUID attributes.
        """
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

