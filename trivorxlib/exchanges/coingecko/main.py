from trivorxlib.core import TXUserBase, TXDataSchemaItem, TXCurrencyBase, TXCurrencyExchangeBase, TXExchangeDataSource, TXUtilsEx, TXCurrencyType
from trivorxlib.storages.base import TXStorageBase, TXStorageQueryOps, TXCondition, TXLogicalQuery, TXSortCriterion, TXSortDirection
from time import time
import requests
import json
from datetime import datetime as dt
from typing import Optional

class TXCoingecko(TXExchangeDataSource):

    _DEMO_MAX_MONTHLY_API_CALLS = 10000
    _DEMO_MAX_REQUESTS_PER_MINUTE = 30
    _HISTORICAL_DATA_MAX_DAYS = 90

    @staticmethod
    def get_connection_data_schema() -> dict[str, TXDataSchemaItem]:
        return {
            "api_key": TXDataSchemaItem(name="API Key", type=str),
            "pro": TXDataSchemaItem(name="Pro account", type=bool)
        }    

    def __init__(
        self,
        storage: TXStorageBase,
        uuid: Optional[str] = None
    ):
        super().__init__(storage, uuid)
        self._name = "Coingecko"
        self._connection_data_required = True
        self._available_currency_types = [TXCurrencyType.CRYPTO]
        self._default_for_types = [TXCurrencyType.CRYPTO]
        self.save()

    def _check_api_rate_limit(self, conn_data: dict[str, any], curr_datetime: int) -> bool:
        """Check if the API rate limit is reached.

        Args:
            conn_data (dict[str, any]): The connection data.
            curr_datetime (int): The current datetime in seconds.

        Returns:
            bool: True if the API rate limit is not reached, False otherwise.
        """
        if conn_data.get("pro", False):
            return True
        last_api_call_dt = conn_data["last_api_call_dt"]
        if curr_datetime - last_api_call_dt >= 60:
            conn_data["last_minute_requests"] = 0
        current_day = dt.now().day
        if curr_datetime - last_api_call_dt >= current_day *24 * 60 * 60:
            conn_data["last_month_requests"] = 0
        if conn_data["last_month_requests"] >= self._DEMO_MAX_MONTHLY_API_CALLS:
            return False
        if conn_data["last_minute_requests"] >= self._DEMO_MAX_REQUESTS_PER_MINUTE:
            return False
        conn_data["last_month_requests"] += 1
        conn_data["last_minute_requests"] += 1      
        return True
    
    def get_currency_exchange(self, currency_source: TXCurrencyBase, currency_target: TXCurrencyBase, user: Optional[TXUserBase] = None, datetime: Optional[int] = None, force_live_data: Optional[bool] = False) -> TXCurrencyExchangeBase:
        if user is None:
            raise ValueError("User is required")        
        conn_data, connection_data_uuid = TXUtilsEx.get_exchange_connection_data(self._uuid, self._storage, user)
        curr_datetime = int(time())
        if datetime:
            if datetime > curr_datetime:
                raise ValueError("Datetime must be in the past")
        else:
            datetime = curr_datetime
        days_diff = (dt.now() - dt.fromtimestamp(datetime)).days
        if days_diff > self._HISTORICAL_DATA_MAX_DAYS:
            raise ValueError(f"Coingecko API only provides historical data up to {self._HISTORICAL_DATA_MAX_DAYS} days")
        stored_data_only = False
        last_api_call_dt = conn_data.get("last_api_call_dt", None)
        last_month_requests = conn_data.get("last_month_requests", None)
        last_minute_requests = conn_data.get("last_minute_requests", None)
        if last_api_call_dt and last_month_requests and last_minute_requests:
            if not self._check_api_rate_limit(conn_data, curr_datetime):
                if force_live_data:
                    raise ValueError("Coingecko API rate limit reached")
                else:
                    stored_data_only = True
        else:
            conn_data["last_month_requests"] = 1
            conn_data["last_minute_requests"] = 1
        conn_data["last_api_call_dt"] = curr_datetime
        if not stored_data_only:
            days = 1 if days_diff <= 1 else days_diff
            coin_part= TXUtilsEx.normalize_coin_name(currency_source.long_name)
            params: dict[str, str] = {
                "vs_currency": TXUtilsEx.normalize_coin_name(currency_target.short_name),   
                "days": str(days)
            }
            if conn_data["pro"]:
                url = f"https://pro-api.coingecko.com/api/v3/coins/{coin_part}/market_chart"    
                params["x_cg_pro_api_key"] = conn_data["api_key"]
            else:
                url = f"https://api.coingecko.com/api/v3/coins/{coin_part}/market_chart"
                params["x_cg_demo_api_key"] = conn_data["api_key"]
            try:            
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                if response.status_code != 200:
                    raise ValueError(f"Coingecko API error: {response.status_code} {response.text}")
                try:
                    data = response.json()
                    if "prices" not in data:
                        raise ValueError(f"Coingecko API error: {response.status_code} {response.text}")
                    prices = data["prices"]
                    if not prices:
                        raise ValueError(f"Coingecko API error: {response.status_code} {response.text}")
                    for price in prices:
                        date_time = int(price[0] / 1000)
                        priceval = float(price[1])
                        exchange = TXCurrencyExchangeBase(
                            currency_source=currency_source,
                            currency_target=currency_target,
                            value=priceval,
                            datetime=date_time
                        )
                        exchange.data_source = self
                        TXUtilsEx.insert_currency_exchange_if_not_exists(self._storage, exchange)
                finally:
                    self._storage.update_exchange_data_source_connection_data(
                        uuid=connection_data_uuid, connection_data=json.dumps(conn_data)
                    )
            except requests.exceptions.RequestException as e:
                raise ValueError(f"Coingecko API error: {e}")
            except Exception as e:
                raise ValueError(f"Coingecko API error: {e}")
        rows1 = self._storage.get_currency_exchanges(            
            TXLogicalQuery(
                TXStorageQueryOps.AND, 
                TXLogicalQuery(
                    TXStorageQueryOps.AND, 
                    TXCondition(
                        TXStorageQueryOps.EQUALS, 'currency_uuid_source', currency_source.uuid
                    ),
                    TXCondition(
                        TXStorageQueryOps.EQUALS, 'currency_uuid_target', currency_target.uuid
                    )
                ),
                TXLogicalQuery(
                    TXStorageQueryOps.OR, 
                    TXCondition(
                        TXStorageQueryOps.EQUALS, 'UNIX_TIMESTAMP(datetime)', datetime
                    ),
                    TXCondition(
                        TXStorageQueryOps.LESS_THAN, 'UNIX_TIMESTAMP(datetime)', datetime
                    )
                )
            ),
            [
                TXSortCriterion('datetime', TXSortDirection.DESC)
            ]
        )
        rows2 = self._storage.get_currency_exchanges(            
            TXLogicalQuery(
                TXStorageQueryOps.AND, 
                TXLogicalQuery(
                    TXStorageQueryOps.AND, 
                    TXCondition(
                        TXStorageQueryOps.EQUALS, 'currency_uuid_source', currency_source.uuid
                    ),
                    TXCondition(
                        TXStorageQueryOps.EQUALS, 'currency_uuid_target', currency_target.uuid
                    )
                ),
                TXLogicalQuery(
                    TXStorageQueryOps.OR, 
                    TXCondition(
                        TXStorageQueryOps.EQUALS, 'UNIX_TIMESTAMP(datetime)', datetime
                    ),
                    TXCondition(
                        TXStorageQueryOps.GREATER_THAN, 'UNIX_TIMESTAMP(datetime)', datetime
                    )
                )
            ),
            [
                TXSortCriterion('datetime', TXSortDirection.ASC)
            ]
        )
        row1: TXCurrencyExchangeBase = None
        row2: TXCurrencyExchangeBase = None
        datetime1 = None
        datetime2 = None
        if len(rows1) > 0:
            row1 = rows1[0]
            datetime1 = row1.datetime
        if len(rows2) > 0:
            row2 = rows2[0]
            datetime2 = row2.datetime
        if row1 and row2:
            datediff1 = abs(datetime - datetime1)
            datediff2 = abs(datetime - datetime2)
            return row1 if datediff1 < datediff2 else row2        
        else:
            if row1 is None and row2 is None:
                raise ValueError(f"Coingecko API error: No data found for {currency_source.long_name} to {currency_target.long_name} on {dt.fromtimestamp(datetime).strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                return row1 if row1 else row2

EXCHANGE_CLASS = TXCoingecko
