from trivorxlib.core.base import *
from trivorxlib.storages.base import *
from typing import Any, Dict, Tuple, Optional
import mysql.connector
from mysql.connector.connection_cext import CMySQLConnection
from mysql.connector import Error as MySQLError
import warnings
import pathlib
import json
from datetime import datetime as dt

class TXSQLBuilder:
    """SQL generator for TXQueryNode trees supporting CRUD operations (MySQL dialect).

    Returns SQL strings with parameter lists to use with parameterized queries.
    """

    placeholder: str = "%s"  # MySQL-style placeholder

    @staticmethod
    def select(
        table: str,
        columns: Optional[list[str]] = None,
        where: Optional[TXQueryNode] = None,
        order_by: Optional[list[TXSortCriterion]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        field_types: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, list[Any]]:
        cols = ", ".join(columns) if columns else "*"
        where_sql, params = TXSQLBuilder._build_where(where, field_types)
        sql = f"SELECT {cols} FROM `{table}`"
        if where_sql:
            sql += f" {where_sql}"
        if order_by:
            sort_parts = [f"`{crit.field}` {crit.direction.value}" for crit in order_by]
            sql += f" ORDER BY {', '.join(sort_parts)}"
        if limit is not None:
            sql += f" LIMIT {limit}"
        if offset is not None:
            sql += f" OFFSET {offset}"
        return sql, params

    @staticmethod
    def insert(
        table: str,
        data: Dict[str, Any],
        field_types: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, list[Any]]:
        if not data:
            raise ValueError("Insert data cannot be empty")
        cols = ", ".join(f"`{c}`" for c in data.keys())
        placeholders = ", ".join(TXSQLBuilder.placeholder for _ in data)
        values = [TXSQLBuilder._param_value(k, v, field_types) for k, v in data.items()]
        sql = f"INSERT INTO `{table}` ({cols}) VALUES ({placeholders})"
        return sql, values

    @staticmethod
    def update(
        table: str,
        data: Dict[str, Any],
        where: Optional[TXQueryNode] = None,
        field_types: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, list[Any]]:
        if not data:
            raise ValueError("Update data cannot be empty")
        set_parts: list[str] = []
        params: list[Any] = []
        for k, v in data.items():
            set_parts.append(f"`{k}` = {TXSQLBuilder.placeholder}")
            params.append(TXSQLBuilder._param_value(k, v, field_types))
        where_sql, where_params = TXSQLBuilder._build_where(where, field_types)
        sql = f"UPDATE `{table}` SET {', '.join(set_parts)}"
        if where_sql:
            sql += f" {where_sql}"
            params.extend(where_params)
        return sql, params

    @staticmethod
    def delete(
        table: str,
        where: Optional[TXQueryNode] = None,
        field_types: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, list[Any]]:
        where_sql, params = TXSQLBuilder._build_where(where, field_types)
        sql = f"DELETE FROM `{table}`"
        if where_sql:
            sql += f" {where_sql}"
        return sql, params

    # --- Internal helpers ---
    @staticmethod
    def _build_where(
        node: Optional[TXQueryNode],
        field_types: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, list[Any]]:
        if node is None:
            return "", []
        clause, params = TXSQLBuilder._node_to_sql(node, field_types)
        return f"WHERE {clause}", params

    @staticmethod
    def _node_to_sql(
        node: TXQueryNode,
        field_types: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, list[Any]]:
        if isinstance(node, TXCondition):
            return TXSQLBuilder._condition_sql(node, field_types)
        if isinstance(node, TXUnaryQuery):
            inner_sql, inner_params = TXSQLBuilder._node_to_sql(node.operand, field_types)
            return f"NOT ({inner_sql})", inner_params
        if isinstance(node, TXLogicalQuery):
            left_sql, left_params = TXSQLBuilder._node_to_sql(node.left, field_types)
            right_sql, right_params = TXSQLBuilder._node_to_sql(node.right, field_types)
            op = "AND" if node.operator == TXStorageQueryOps.AND else "OR"
            return f"({left_sql}) {op} ({right_sql})", left_params + right_params
        raise ValueError("Unsupported TXQueryNode subclass")

    @staticmethod
    def _condition_sql(cond: TXCondition, field_types: Optional[Dict[str, str]]) -> Tuple[str, list[Any]]:
        col = f"`{cond.field}`"
        op = cond.operator
        val = cond.value

        # Handle NULL semantics
        if val is None:
            if op == TXStorageQueryOps.EQUALS:
                return f"{col} IS NULL", []
            if op == TXStorageQueryOps.NOT_EQUALS:
                return f"{col} IS NOT NULL", []

        if op == TXStorageQueryOps.EQUALS:
            return f"{col} = {TXSQLBuilder.placeholder}", [TXSQLBuilder._param_value(cond.field, val, field_types)]
        if op == TXStorageQueryOps.NOT_EQUALS:
            return f"{col} <> {TXSQLBuilder.placeholder}", [TXSQLBuilder._param_value(cond.field, val, field_types)]
        if op == TXStorageQueryOps.GREATER_THAN:
            return f"{col} > {TXSQLBuilder.placeholder}", [TXSQLBuilder._param_value(cond.field, val, field_types)]
        if op == TXStorageQueryOps.LESS_THAN:
            return f"{col} < {TXSQLBuilder.placeholder}", [TXSQLBuilder._param_value(cond.field, val, field_types)]
        if op == TXStorageQueryOps.STARTS_WITH:
            return f"{col} LIKE {TXSQLBuilder.placeholder}", [TXSQLBuilder._like_prefix(val)]
        if op == TXStorageQueryOps.ENDS_WITH:
            return f"{col} LIKE {TXSQLBuilder.placeholder}", [TXSQLBuilder._like_suffix(val)]
        if op == TXStorageQueryOps.CONTAINS:
            return f"{col} LIKE {TXSQLBuilder.placeholder}", [TXSQLBuilder._like_contains(val)]
        if op == TXStorageQueryOps.INCLUDES_VALUES:
            # MySQL JSON: ensure column contains all specified values
            # JSON_CONTAINS(col, CAST(? AS JSON))
            candidate = json.dumps(val)
            return (
                f"JSON_CONTAINS({col}, CAST({TXSQLBuilder.placeholder} AS JSON))",
                [candidate],
            )
        if op == TXStorageQueryOps.NOT_INCLUDES_VALUES:
            candidate = json.dumps(val)
            return (
                f"NOT JSON_CONTAINS({col}, CAST({TXSQLBuilder.placeholder} AS JSON))",
                [candidate],
            )
        raise ValueError(f"Unsupported operator: {op}")

    @staticmethod
    def _param_value(field: str, value: Any, field_types: Optional[Dict[str, str]]) -> Any:
        t = (field_types or {}).get(field)
        if isinstance(value, bool):
            return 1 if value else 0
        if t == "json":
            return json.dumps(value)
        return value

    @staticmethod
    def _like_prefix(value: Any) -> str:
        s = str(value)
        return f"{s}%"

    @staticmethod
    def _like_suffix(value: Any) -> str:
        s = str(value)
        return f"%{s}"

    @staticmethod
    def _like_contains(value: Any) -> str:
        s = str(value)
        return f"%{s}%"

class TXMySQLStorage(TXStorageBase):
    _conn: CMySQLConnection = None

    def __init__(self, settings_json: str):
        super().__init__(settings_json)
        self._create_tables()

    @property
    @settings_json.setter
    def settings_json(self, value: str) -> None:
        super().settings_json = value
        required_keys = {"host", "user", "password", "database"}
        missing = required_keys - self._settings.keys()
        if missing:
            raise ValueError(f"Missing required MySQL connection parameters: {', '.join(sorted(missing))}")
        if not isinstance(self._settings["host"], str):
            raise TypeError("The 'host' parameter must be a string.")
        if not isinstance(self._settings["user"], str):
            raise TypeError("The 'user' parameter must be a string.")
        if not isinstance(self._settings["password"], str):
            raise TypeError("The 'password' parameter must be a string.")
        if not isinstance(self._settings["database"], str):
            raise TypeError("The 'database' parameter must be a string.")
        if "port" in self._settings and not isinstance(self._settings["port"], int):
            raise TypeError("The 'port' parameter must be an integer.")
        if "charset" in self._settings and not isinstance(self._settings["charset"], str):
            raise TypeError("The 'charset' parameter must be a string.")
        if "collation" in self._settings and not isinstance(self._settings["collation"], str):
            raise TypeError("The 'collation' parameter must be a string.")
        if "connect_timeout" in self._settings and not isinstance(self._settings["connect_timeout"], int):
            raise TypeError("The 'connect_timeout' parameter must be an integer.")
        if "read_timeout" in self._settings and not isinstance(self._settings["read_timeout"], int):
            raise TypeError("The 'read_timeout' parameter must be an integer.")
        if "write_timeout" in self._settings and not isinstance(self._settings["write_timeout"], int):
            raise TypeError("The 'write_timeout' parameter must be an integer.")        
        self._connect()

    def _connect(self) -> None:
        """Establish a robust MySQL connection with comprehensive error handling."""
        try:
            self._conn = mysql.connector.connect(
                host=self._settings["host"],
                user=self._settings["user"],
                password=self._settings["password"],
                database=self._settings["database"],
                port=self._settings.get("port", 3306),
                charset=self._settings.get("charset", "utf8mb4"),
                collation=self._settings.get("collation", "utf8mb4_general_ci"),
                connect_timeout=self._settings.get("connect_timeout", 10),
                read_timeout=self._settings.get("read_timeout", 30),
                write_timeout=self._settings.get("write_timeout", 30),
                autocommit=False,
                use_unicode=True,
                raise_on_warnings=True,
            )
        except MySQLError as exc:
            raise RuntimeError(f"MySQL connection failed: {exc}") from exc
        except Exception as exc:
            raise RuntimeError(f"Unexpected error while connecting to MySQL: {exc}") from exc

    def close(self) -> None:
        """Safely close the MySQL connection."""
        if self._conn and self._conn.is_connected():
            try:
                self._conn.close()
            except Exception as exc:
                # Log the exception but do not propagate to avoid masking caller errors
                warnings.warn(f"Error while closing MySQL connection: {exc}", RuntimeWarning)
        self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _ensure_connection(self) -> None:
        """Restore the MySQL connection if it has expired."""
        if self._conn is None or not self._conn.is_connected():
            self._connect()

    def _create_tables(self) -> None:
        """Create all tables by executing the statements contained in db_mysql.sql."""
        sql_file = pathlib.Path(__file__).with_name("db_mysql.sql")
        if not sql_file.exists():
            raise FileNotFoundError(f"Schema file not found: {sql_file}")

        with sql_file.open("r", encoding="utf-8") as f:
            raw = f.read()

        # Split on semicolon, strip blanks, drop empty statements
        statements = [stmt.strip() for stmt in raw.split(";") if stmt.strip()]
        self._ensure_connection()
        cursor = self._conn.cursor()
        try:
            for stmt in statements:
                cursor.execute(stmt)                
            self._conn.commit()
        # [START] CHECK IF THE PRIMARY ADMINISTRATOR USER EXISTS AND CREATE IT IF NOT
            sql, params = TXSQLBuilder.select(
                table="user",
                columns=[
                    "user_uuid",
                    "login"
                ],
                where=TXCondition(TXStorageQueryOps.EQUALS, "login", "admin")
            )
            try:
                cursor = self._conn.cursor(dictionary=True)
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                cursor.close()
            except MySQLError as exc:
                raise RuntimeError(f"Failed to fetch primary administrator user: {exc}") from exc
            if len(rows) == 0:
                sql, params = TXSQLBuilder.insert(
                    table="user",
                    data={
                        "full_name": "Administrator",
                        "login": "admin",
                        "password": TXUtils.encrypt_password("admin"),
                        "token": TXUtils.generate_token(),
                        "role": TXUserRole.ADMIN.value
                    }
                )
                try:
                    cursor.execute(sql, params)
                    self._conn.commit()
                except MySQLError as exc:
                    self._conn.rollback()
                    raise RuntimeError(f"Failed to create primary administrator user: {exc}") from exc
        # [END] CHECK IF THE PRIMARY ADMINISTRATOR USER EXISTS AND CREATE IT IF NOT
        except MySQLError as exc:
            self._conn.rollback()
            raise RuntimeError(f"Table creation failed: {exc}") from exc
        finally:
            cursor.close()

    # --- Internal: query field translation helpers ---
    def _translate_query_fields(self, node: Optional[TXQueryNode], mapping: Dict[str, str]) -> Optional[TXQueryNode]:
        """Recursively translate condition fields using provided mapping."""
        if node is None:
            return None
        if isinstance(node, TXCondition):
            new_field = mapping.get(node.field, node.field)
            return TXCondition(node.operator, new_field, node.value)
        if isinstance(node, TXUnaryQuery):
            return TXUnaryQuery(node.operator, self._translate_query_fields(node.operand, mapping))
        if isinstance(node, TXLogicalQuery):
            left = self._translate_query_fields(node.left, mapping)
            right = self._translate_query_fields(node.right, mapping)
            return TXLogicalQuery(node.operator, left, right)
        return node

    def get_users(
        self,
        query: TXQueryNode | None = None,
        sort: list[TXSortCriterion] | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[TXUserBase]:
        """
        Retrieve users matching the given query, sort, offset, and limit.
        Returns a list of TXUserBase objects.
        """
        self._ensure_connection()
        sql, params = TXSQLBuilder.select(
            table="user",
            columns=[
                "user_uuid",
                "full_name",
                "login",
                "password",
                "token",
                "role",
                "2fa_seed",
                "enabled",
                "UNIX_TIMESTAMP(creation_datetime) AS creation_ts"
            ],
            where=TXCondition(TXStorageQueryOps.EQUALS, "deleted", 0) if query is None else TXLogicalQuery(TXStorageQueryOps.AND, query, TXCondition(TXStorageQueryOps.EQUALS, "deleted", 0)),
            order_by=sort,
            limit=limit,
            offset=offset,
        )
        try:
            cursor = self._conn.cursor(dictionary=True)
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to fetch users: {exc}") from exc
        users: list[TXUserBase] = []
        for row in rows:
            user = TXUserBase(
                uuid=row["user_uuid"],
                token=row["token"],
                encrypted_password=row["password"],
            )
            if row["role"] == "ADMIN":
                user.role = TXUserRole.ADMIN
            else:
                user.role = TXUserRole.STANDARD
            user.full_name = row["full_name"]
            user.login = row["login"]
            user.twofa_seed = row.get("2fa_seed")
            user.enabled = bool(row["enabled"])
            user.creation_datetime = int(row["creation_ts"])            
            users.append(user)
        return users

    def update_user(
        self,
        uuid: str, 
        token: str | None = None,
        full_name: str | None = None,
        login: str | None = None,
        password: str | None = None,
        role: TXUserRole | None = None,
        enabled: bool | None = None,
        encrypted_password: str | None = None,
        twofa_seed: str | None = None
    ) -> None:
        """
        Update an existing user in the storage.        
        """
        self._ensure_connection()
        data: Dict[str, Any] = {}
        if token is not None:
            data["token"] = token
        if full_name is not None:
            data["full_name"] = full_name
        if login is not None:
            data["login"] = login
        if password and encrypted_password is None:
            data["password"] = TXUtils.encrypt_password(password)
        elif encrypted_password is not None:
            data["password"] = encrypted_password
        if role is not None:
            data["role"] = role.value
        if enabled is not None:
            data["enabled"] = int(enabled)
        # Always synchronize 2FA seed; allow NULL when value is None
        data["2fa_seed"] = twofa_seed
        sql, params = TXSQLBuilder.update(
            table="user",
            data=data,
            where=TXCondition(TXStorageQueryOps.EQUALS, "user_uuid", uuid),
        )
        try:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            self._conn.commit()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to update user: {exc}") from exc

    def delete_user(self, uuid: str) -> None:
        """
        Delete a user from the storage.

        Args:
            uuid: The UUID of the user to delete.
        """
        self._ensure_connection()
        sql, params = TXSQLBuilder.update(
            table="user",
            data={
                "deleted": 1
            },
            where=TXCondition(TXStorageQueryOps.EQUALS, "user_uuid", uuid)
        )
        try:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            self._conn.commit()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to delete user: {exc}") from exc

    def insert_user(
        self,
        full_name: str,
        login: str,
        role: TXUserRole,
        password: str | None = None,
        encrypted_password: str | None = None,
        uuid: str | None = None,
        token: str | None = None,
        twofa_seed: str | None = None
    ) -> tuple[str, str]:
        """
        Insert a new user into the storage.
        """
        self._ensure_connection()
        uuid = TXUtils.generate_uuid() if uuid is None else uuid
        token = TXUtils.generate_token() if token is None else token
        if password is not None and encrypted_password is None:
            encrypted_password = TXUtils.encrypt_password(password)
        elif encrypted_password is None:
            raise ValueError("Either password or encrypted_password must be provided.")
        sql, params = TXSQLBuilder.insert(
            table="user",
            data={
                "user_uuid": uuid,
                "full_name": full_name,
                "login": login,
                "password": encrypted_password,
                "token": token,
                "role": role.value,
                "2fa_seed": twofa_seed,
            },
        )
        try:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            self._conn.commit()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to insert user: {exc}") from exc
        return uuid, token

    # --- BOT CRUD ---
    def get_bots(
        self,
        query: TXQueryNode | None = None,
        sort: list[TXSortCriterion] | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[TXBotBase]:
        """
        Retrieve bots matching the given query, sort, offset, and limit.
        Returns a list of TXBotBase-compatible objects.
        """
        self._ensure_connection()
        sql, params = TXSQLBuilder.select(
            table="bot",
            columns=[
                "bot_uuid",
                "user_uuid",
                "algo_uuid",
                "name",
                "algo_name",
                "algo_version",
                "algo_settings",
                "annotations",
                "active",
                "UNIX_TIMESTAMP(creation_datetime) AS creation_ts",
            ],
            where=TXCondition(TXStorageQueryOps.EQUALS, "deleted", 0) if query is None else TXLogicalQuery(TXStorageQueryOps.AND, query, TXCondition(TXStorageQueryOps.EQUALS, "deleted", 0)),
            order_by=sort,
            limit=limit,
            offset=offset,
        )
        try:
            cursor = self._conn.cursor(dictionary=True)
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to fetch bots: {exc}") from exc
        bots: list[TXBotBase] = []
        for row in rows:
            user = self.get_users(TXCondition(TXStorageQueryOps.EQUALS, "user_uuid", row["user_uuid"]))[0],
            bot = TXBotBase(
                user=user,
                algo_uuid=row["algo_uuid"],
                name=row["name"],
                algo_name = row["algo_name"],
                algo_ver=row["algo_version"],
                algo_settings=row["algo_settings"],
                uuid=row["bot_uuid"],
            )
            bot.annotations = row.get("annotations")
            bot.active = bool(row["active"])
            bot.creation_datetime = int(row["creation_ts"])
            bots.append(bot)
        return bots

    def insert_bot(
        self,
        user_uuid: str,
        algo_uuid: str,
        name: str,
        algo_name: str,
        algo_ver: str,
        algo_settings: str,
        annotations: str | None = None,
        active: bool | None = None,
        uuid: str | None = None,
    ) -> str:
        """Insert a new bot and return its UUID."""
        self._ensure_connection()
        bot_uuid = TXUtils.generate_uuid() if uuid is None else uuid
        data = {
            "bot_uuid": bot_uuid,
            "user_uuid": user_uuid,
            "algo_uuid": algo_uuid,
            "name": name,
            "algo_name": algo_name,
            "algo_version": algo_ver,
            "algo_settings": algo_settings,
            "annotations": annotations,
            "active": int(active) if active is not None else 0,
        }
        sql, params = TXSQLBuilder.insert(
            table="bot",
            data=data,
        )
        try:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            self._conn.commit()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to insert bot: {exc}") from exc
        return bot_uuid

    def update_bot(
        self,
        uuid: str,
        user_uuid: str | None = None,
        algo_uuid: str | None = None,
        name: str | None = None,
        algo_name: str | None = None,
        algo_ver: str | None = None,
        algo_settings: str | None = None,
        annotations: str | None = None,
        active: bool | None = None,
    ) -> None:
        """Update an existing bot by UUID."""
        self._ensure_connection()
        data: Dict[str, Any] = {}
        if user_uuid is not None:
            data["user_uuid"] = user_uuid
        if algo_uuid is not None:
            data["algo_uuid"] = algo_uuid
        if name is not None:
            data["name"] = name
        if algo_name is not None:
            data["algo_name"] = algo_name
        if algo_ver is not None:
            data["algo_version"] = algo_ver
        if algo_settings is not None:
            data["algo_settings"] = algo_settings
        if annotations is not None:
            data["annotations"] = annotations
        if active is not None:
            data["active"] = int(active)
        sql, params = TXSQLBuilder.update(
            table="bot",
            data=data,
            where=TXCondition(TXStorageQueryOps.EQUALS, "bot_uuid", uuid),
        )
        try:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            self._conn.commit()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to update bot: {exc}") from exc

    def delete_bot(self, uuid: str) -> None:
        """Soft-delete a bot by setting deleted = 1."""
        self._ensure_connection()
        sql, params = TXSQLBuilder.update(
            table="bot",
            data={"deleted": 1},
            where=TXCondition(TXStorageQueryOps.EQUALS, "bot_uuid", uuid),
        )
        try:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            self._conn.commit()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to delete bot: {exc}") from exc

    # --- CURRENCY CRUD ---
    def get_currencies(
        self,
        query: TXQueryNode | None = None,
        sort: list[TXSortCriterion] | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[TXCurrencyBase]:
        """
        Retrieve currencies matching the given query, sort, offset, and limit.
        Returns a list of TXCurrencyBase objects.
        """
        self._ensure_connection()
        sql, params = TXSQLBuilder.select(
            table="currency",
            columns=[
                "currency_uuid",
                "long_name",
                "short_name",
                "currency_type",
            ],
            where=TXCondition(TXStorageQueryOps.EQUALS, "deleted", 0) if query is None else TXLogicalQuery(TXStorageQueryOps.AND, query, TXCondition(TXStorageQueryOps.EQUALS, "deleted", 0)),
            order_by=sort,
            limit=limit,
            offset=offset,
        )
        try:
            cursor = self._conn.cursor(dictionary=True)
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to fetch currencies: {exc}") from exc
        currencies: list[TXCurrencyBase] = []
        for row in rows:
            currency = TXCurrencyBase(
                long_name=row["long_name"],
                short_name=row["short_name"],
                currency_type=TXCurrencyType(row["currency_type"]), 
                uuid=row["currency_uuid"],
            )
            currencies.append(currency)
        return currencies

    def insert_currency(
        self,
        long_name: str,
        short_name: str,
        currency_type: TXCurrencyType,
        uuid: str | None = None,
    ) -> str:
        """Insert a new currency and return its UUID."""
        self._ensure_connection()
        currency_uuid = TXUtils.generate_uuid() if uuid is None else uuid
        data = {
            "currency_uuid": currency_uuid,
            "long_name": long_name,
            "short_name": short_name,
            "currency_type": currency_type.value,
        }
        sql, params = TXSQLBuilder.insert(
            table="currency",
            data=data,
        )
        try:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            self._conn.commit()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to insert currency: {exc}") from exc
        return currency_uuid

    def update_currency(
        self,
        uuid: str,
        long_name: str | None = None,
        short_name: str | None = None,
        currency_type: TXCurrencyType | None = None,
    ) -> None:
        """Update an existing currency by UUID."""
        self._ensure_connection()
        data: Dict[str, Any] = {}
        if long_name is not None:
            data["long_name"] = long_name
        if short_name is not None:
            data["short_name"] = short_name
        if currency_type is not None:
            data["currency_type"] = currency_type.value
        sql, params = TXSQLBuilder.update(
            table="currency",
            data=data,
            where=TXCondition(TXStorageQueryOps.EQUALS, "currency_uuid", uuid),
        )
        try:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            self._conn.commit()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to update currency: {exc}") from exc

    def delete_currency(self, uuid: str) -> None:
        """Soft-delete a currency by setting deleted = 1."""
        self._ensure_connection()
        sql, params = TXSQLBuilder.update(
            table="currency",
            data={"deleted": 1},
            where=TXCondition(TXStorageQueryOps.EQUALS, "currency_uuid", uuid),
        )
        try:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            self._conn.commit()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to delete currency: {exc}") from exc

    # --- EXCHANGE DATA SOURCE CRUD ---
    def get_exchange_data_sources(
        self,
        query: TXQueryNode | None = None,
        sort: list[TXSortCriterion] | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[TXExchangeDataSourceBase]:
        """
        Retrieve exchange data sources matching the given query, sort, offset, and limit.
        Returns a list of TXExchangeDataSourceBase objects.
        """
        self._ensure_connection()
        sql, params = TXSQLBuilder.select(
            table="exchange_data_source",
            columns=[
                "exchange_data_source_uuid",
                "name",
                "avaiable_currency_types",
                "default_for_types",
                "notes",
                "connection_data_required",
            ],
            where=TXCondition(TXStorageQueryOps.EQUALS, "deleted", 0) if query is None else TXLogicalQuery(TXStorageQueryOps.AND, query, TXCondition(TXStorageQueryOps.EQUALS, "deleted", 0)),
            order_by=sort,
            limit=limit,
            offset=offset,
        )
        try:
            cursor = self._conn.cursor(dictionary=True)
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to fetch exchange data sources: {exc}") from exc
        
        exchange_data_sources: list[TXExchangeDataSourceBase] = []
        for row in rows:
            # Parse the SET fields from MySQL
            available_currency_types = set()
            if row["avaiable_currency_types"]:
                for currency_type in row["avaiable_currency_types"].split(','):
                    available_currency_types.add(TXCurrencyType(currency_type))
            
            default_for_types = set()
            if row["default_for_types"]:
                for currency_type in row["default_for_types"].split(','):
                    default_for_types.add(TXCurrencyType(currency_type))
            
            exchange_data_source = TXExchangeDataSourceBase(
                name=row["name"],
                avaiable_currency_types=available_currency_types,
                connection_data_required=bool(row["connection_data_required"]),
                uuid=row["exchange_data_source_uuid"],
            )
            exchange_data_source.default_for_types = default_for_types if default_for_types else None
            exchange_data_source.notes = row["notes"]
            exchange_data_sources.append(exchange_data_source)
        
        return exchange_data_sources

    def insert_exchange_data_source(
        self,
        name: str,
        available_currency_types: set[TXCurrencyType],
        connection_data_required: bool,
        default_for_types: set[TXCurrencyType] | None = None,
        notes: str | None = None,
        uuid: str | None = None,
    ) -> str:
        """Insert a new exchange data source and return its UUID."""
        self._ensure_connection()
        exchange_data_source_uuid = TXUtils.generate_uuid() if uuid is None else uuid
        
        # Convert sets to comma-separated strings for MySQL SET type
        available_types_str = ','.join([ct.value for ct in available_currency_types])
        default_types_str = ','.join([ct.value for ct in default_for_types]) if default_for_types else None
        
        data = {
            "exchange_data_source_uuid": exchange_data_source_uuid,
            "name": name,
            "avaiable_currency_types": available_types_str,
            "default_for_types": default_types_str,
            "notes": notes,
            "connection_data_required": int(connection_data_required),
        }
        sql, params = TXSQLBuilder.insert(
            table="exchange_data_source",
            data=data,
        )
        try:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            self._conn.commit()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to insert exchange data source: {exc}") from exc
        
        return exchange_data_source_uuid

    def update_exchange_data_source(
        self,
        uuid: str,
        name: str | None = None,
        available_currency_types: set[TXCurrencyType] | None = None,
        connection_data_required: bool | None = None,
        default_for_types: set[TXCurrencyType] | None = None,
        notes: str | None = None,
    ) -> None:
        """Update an existing exchange data source by UUID."""
        self._ensure_connection()
        data: Dict[str, Any] = {}
        
        if name is not None:
            data["name"] = name
        if available_currency_types is not None:
            data["avaiable_currency_types"] = ','.join([ct.value for ct in available_currency_types])
        if connection_data_required is not None:
            data["connection_data_required"] = int(connection_data_required)
        if default_for_types is not None:
            data["default_for_types"] = ','.join([ct.value for ct in default_for_types]) if default_for_types else None
        if notes is not None:
            data["notes"] = notes
            
        sql, params = TXSQLBuilder.update(
            table="exchange_data_source",
            data=data,
            where=TXCondition(TXStorageQueryOps.EQUALS, "exchange_data_source_uuid", uuid),
        )
        try:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            self._conn.commit()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to update exchange data source: {exc}") from exc

    def delete_exchange_data_source(self, uuid: str) -> None:
        """Soft-delete an exchange data source by setting deleted = 1."""
        self._ensure_connection()
        sql, params = TXSQLBuilder.update(
            table="exchange_data_source",
            data={"deleted": 1},
            where=TXCondition(TXStorageQueryOps.EQUALS, "exchange_data_source_uuid", uuid),
        )
        try:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            self._conn.commit()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to delete exchange data source: {exc}") from exc

    def get_currency_exchanges(
        self,
        query: TXQueryNode | None = None,
        sort: list[TXSortCriterion] | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[TXCurrencyExchangeBase]:
        """
        Retrieve currency exchanges matching the given query, sort, offset, and limit.
        Returns a list of TXCurrencyExchangeBase objects.
        """
        self._ensure_connection()
        sql, params = TXSQLBuilder.select(
            table="currency_exchange",
            columns=[
                "currency_exchange_uuid",
                "currency_uuid_source",
                "currency_uuid_target",
                "exchange_data_source_uuid",
                "value",
                "UNIX_TIMESTAMP(datetime) AS datetime_ts"
            ],
            where=query,
            order_by=sort,
            limit=limit,
            offset=offset,
        )
        try:
            cursor = self._conn.cursor(dictionary=True)
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to fetch currency exchanges: {exc}") from exc        
        currency_exchanges: list[TXCurrencyExchangeBase] = []
        for row in rows:
            # Get source currency
            source_currency = self.get_currencies(
                TXCondition(TXStorageQueryOps.EQUALS, "currency_uuid", row["currency_uuid_source"])
            )[0]            
            # Get target currency
            target_currency = self.get_currencies(
                TXCondition(TXStorageQueryOps.EQUALS, "currency_uuid", row["currency_uuid_target"])
            )[0]
            exchange = TXCurrencyExchangeBase(
                currency_source=source_currency,
                currency_target=target_currency,
                value=float(row["value"]),
                datetime=int(row["datetime_ts"]),
                uuid=row["currency_exchange_uuid"]
            )            
            # Set data source if available
            if row["exchange_data_source_uuid"]:
                exchange.data_source = self.get_exchange_data_sources(
                    TXCondition(TXStorageQueryOps.EQUALS, "exchange_data_source_uuid", row["exchange_data_source_uuid"])
                )[0]            
            currency_exchanges.append(exchange)        
        return currency_exchanges

    def insert_currency_exchange(
        self,
        currency_uuid_source: str,
        currency_uuid_target: str,
        value: float,
        exchange_data_source_uuid: str | None = None,
        date_time: int | None = None,
        uuid: str | None = None,
    ) -> str:
        """
        Insert a new currency exchange into the storage.

        Args:
            currency_uuid_source: The UUID of the source currency.
            currency_uuid_target: The UUID of the target currency.
            value: The exchange rate value.
            exchange_data_source_uuid: Optional UUID of the exchange data source.
            uuid: Optional currency exchange UUID (auto-generated if None).

        Returns:
            The UUID of the inserted currency exchange.
        """
        self._ensure_connection()
        currency_exchange_uuid = TXUtils.generate_uuid() if uuid is None else uuid
        data={
            "currency_exchange_uuid": currency_exchange_uuid,
            "currency_uuid_source": currency_uuid_source,
            "currency_uuid_target": currency_uuid_target,
            "exchange_data_source_uuid": exchange_data_source_uuid,
            "value": value
        }
        if date_time is not None:
            data["datetime"] = dt.fromtimestamp(date_time).strftime('%Y-%m-%d %H:%M:%S')
        sql, params = TXSQLBuilder.insert(
            table="currency_exchange",
            data=data
        )
        try:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            self._conn.commit()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to insert currency exchange: {exc}") from exc
        
        return currency_exchange_uuid

    def update_currency_exchange(
        self,
        uuid: str,
        currency_uuid_source: str | None = None,
        currency_uuid_target: str | None = None,
        value: float | None = None,
        exchange_data_source_uuid: str | None = None,
        date_time: int | None = None
    ) -> None:
        """
        Update an existing currency exchange in the storage.

        Args:
            uuid: The UUID of the currency exchange to update.
            currency_uuid_source: Optional new source currency UUID.
            currency_uuid_target: Optional new target currency UUID.
            value: Optional new exchange rate value.
            exchange_data_source_uuid: Optional new exchange data source UUID.
        """
        self._ensure_connection()
        data: Dict[str, Any] = {}
        
        if currency_uuid_source is not None:
            data["currency_uuid_source"] = currency_uuid_source
        if currency_uuid_target is not None:
            data["currency_uuid_target"] = currency_uuid_target
        if value is not None:
            data["value"] = value
        if exchange_data_source_uuid is not None:
            data["exchange_data_source_uuid"] = exchange_data_source_uuid
        if date_time is not None:
            data["datetime"] = dt.fromtimestamp(date_time).strftime('%Y-%m-%d %H:%M:%S')                 
        sql, params = TXSQLBuilder.update(
            table="currency_exchange",
            data=data,
            where=TXCondition(TXStorageQueryOps.EQUALS, "currency_exchange_uuid", uuid),
        )
        try:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            self._conn.commit()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to update currency exchange: {exc}") from exc

    def delete_currency_exchange(self, uuid: str) -> None:
        """
        Delete a currency exchange from the storage.

        Args:
            uuid: The UUID of the currency exchange to delete.
        """
        self._ensure_connection()
        sql, params = TXSQLBuilder.delete(
            table="currency_exchange",
            where=TXCondition(TXStorageQueryOps.EQUALS, "currency_exchange_uuid", uuid),
        )
        try:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            self._conn.commit()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to delete currency exchange: {exc}") from exc

    # --- EXCHANGE DATA SOURCE CONNECTION DATA CRUD ---
    def get_exchange_data_source_connection_data(
        self,
        query: TXQueryNode | None = None,
        sort: list[TXSortCriterion] | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[TXExchangeDataSourceConnectionDataBase]:
        """
        Retrieve connection data entries with optional filtering, ordering, and pagination.
        Returns a list of TXExchangeDataSourceConnectionDataBase objects.
        """
        self._ensure_connection()
        sql, params = TXSQLBuilder.select(
            table="exchange_data_source_connection_data",
            columns=[
                "exchange_data_source_connection_data_uuid",
                "exchange_data_source_uuid",
                "user_uuid",
                "connection_data",
            ],
            where=query,
            order_by=sort,
            limit=limit,
            offset=offset,
        )
        try:
            cursor = self._conn.cursor(dictionary=True)
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to fetch exchange data source connection data: {exc}") from exc
        results: list[TXExchangeDataSourceConnectionDataBase] = []
        for row in rows:
            user = self.get_users(
                TXCondition(TXStorageQueryOps.EQUALS, "user_uuid", row["user_uuid"])
            )[0]
            data_source = self.get_exchange_data_sources(
                TXCondition(TXStorageQueryOps.EQUALS, "exchange_data_source_uuid", row["exchange_data_source_uuid"])
            )[0]
            conn = TXExchangeDataSourceConnectionDataBase(
                user=user,
                data_source=data_source,
                connection_data=row["connection_data"],
                uuid=row["exchange_data_source_connection_data_uuid"],
            )
            results.append(conn)
        return results

    def insert_exchange_data_source_connection_data(
        self,
        exchange_data_source_uuid: str,
        user_uuid: str,
        connection_data: str,
        uuid: str | None = None,
    ) -> str:
        """Insert a new connection data entry and return its UUID."""
        self._ensure_connection()
        TXUtils.validate_json(connection_data)
        conn_uuid = TXUtils.generate_uuid() if uuid is None else uuid
        sql, params = TXSQLBuilder.insert(
            table="exchange_data_source_connection_data",
            data={
                "exchange_data_source_connection_data_uuid": conn_uuid,
                "exchange_data_source_uuid": exchange_data_source_uuid,
                "user_uuid": user_uuid,
                "connection_data": connection_data,
            },
        )
        try:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            self._conn.commit()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to insert exchange data source connection data: {exc}") from exc
        return conn_uuid

    def update_exchange_data_source_connection_data(
        self,
        uuid: str,
        exchange_data_source_uuid: str | None = None,
        user_uuid: str | None = None,
        connection_data: str | None = None,
    ) -> None:
        """Update an existing connection data entry by UUID."""
        self._ensure_connection()
        data: Dict[str, Any] = {}
        if exchange_data_source_uuid is not None:
            data["exchange_data_source_uuid"] = exchange_data_source_uuid
        if user_uuid is not None:
            data["user_uuid"] = user_uuid
        if connection_data is not None:
            TXUtils.validate_json(connection_data)
            data["connection_data"] = connection_data
        sql, params = TXSQLBuilder.update(
            table="exchange_data_source_connection_data",
            data=data,
            where=TXCondition(TXStorageQueryOps.EQUALS, "exchange_data_source_connection_data_uuid", uuid),
        )
        try:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            self._conn.commit()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to update exchange data source connection data: {exc}") from exc

    def delete_exchange_data_source_connection_data(self, uuid: str) -> None:
        """Delete a connection data entry by UUID (no soft-delete column)."""
        self._ensure_connection()
        sql, params = TXSQLBuilder.delete(
            table="exchange_data_source_connection_data",
            where=TXCondition(TXStorageQueryOps.EQUALS, "exchange_data_source_connection_data_uuid", uuid),
        )
        try:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            self._conn.commit()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to delete exchange data source connection data: {exc}") from exc


    # --- FINANCIAL HUB CRUD ---
    def get_financial_hubs(
        self,
        query: TXQueryNode | None = None,
        sort: list[TXSortCriterion] | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[TXFinancialHubBase]:
        """
        Retrieve financial hubs matching the given query, sort, offset, and limit.
        Returns a list of TXFinancialHubBase objects.
        """
        self._ensure_connection()
        sql, params = TXSQLBuilder.select(
            table="financial_hub",
            columns=[
                "financial_hub_uuid",
                "name",
                "allowed_operations",
                "notes",
            ],
            where=TXCondition(TXStorageQueryOps.EQUALS, "deleted", 0) if query is None else TXLogicalQuery(TXStorageQueryOps.AND, query, TXCondition(TXStorageQueryOps.EQUALS, "deleted", 0)),
            order_by=sort,
            limit=limit,
            offset=offset,
        )
        try:
            cursor = self._conn.cursor(dictionary=True)
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to fetch financial hubs: {exc}") from exc
        hubs: list[TXFinancialHubBase] = []
        for row in rows:
            ops: set[TXAssetType] = set()
            if row["allowed_operations"]:
                for op in row["allowed_operations"].split(','):
                    ops.add(TXAssetType(op))
            hub = TXFinancialHubBase(
                name=row["name"],
                allowed_operations=ops,
                uuid=row["financial_hub_uuid"],
            )
            hub.notes = row.get("notes")
            hubs.append(hub)
        return hubs

    def insert_financial_hub(
        self,
        name: str,
        allowed_operations: set[TXAssetType],
        notes: str | None = None,
        uuid: str | None = None,
    ) -> str:
        """Insert a new financial hub and return its UUID."""
        self._ensure_connection()
        hub_uuid = TXUtils.generate_uuid() if uuid is None else uuid
        ops_str = ','.join([op.value for op in allowed_operations])
        data = {
            "financial_hub_uuid": hub_uuid,
            "name": name,
            "allowed_operations": ops_str,
            "notes": notes,
        }
        sql, params = TXSQLBuilder.insert(
            table="financial_hub",
            data=data,
        )
        try:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            self._conn.commit()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to insert financial hub: {exc}") from exc
        return hub_uuid

    def update_financial_hub(
        self,
        uuid: str,
        name: str | None = None,
        allowed_operations: set[TXAssetType] | None = None,
        notes: str | None = None,
    ) -> None:
        """Update an existing financial hub by UUID."""
        self._ensure_connection()
        data: Dict[str, Any] = {}
        if name is not None:
            data["name"] = name
        if allowed_operations is not None:
            data["allowed_operations"] = ','.join([op.value for op in allowed_operations])
        if notes is not None:
            data["notes"] = notes
        sql, params = TXSQLBuilder.update(
            table="financial_hub",
            data=data,
            where=TXCondition(TXStorageQueryOps.EQUALS, "financial_hub_uuid", uuid),
        )
        try:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            self._conn.commit()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to update financial hub: {exc}") from exc

    def delete_financial_hub(self, uuid: str) -> None:
        """Soft-delete a financial hub by setting deleted = 1."""
        self._ensure_connection()
        sql, params = TXSQLBuilder.update(
            table="financial_hub",
            data={"deleted": 1},
            where=TXCondition(TXStorageQueryOps.EQUALS, "financial_hub_uuid", uuid),
        )
        try:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            self._conn.commit()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to delete financial hub: {exc}") from exc

    # --- FINANCIAL HUB CONNECTION DATA CRUD ---
    def get_financial_hub_connection_data(
        self,
        query: TXQueryNode | None = None,
        sort: list[TXSortCriterion] | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[TXFinancialHubConnectionDataBase]:
        """
        Retrieve financial hub connection data with optional filtering, ordering, and pagination.
        Returns a list of TXFinancialHubConnectionDataBase objects.
        """
        self._ensure_connection()
        sql, params = TXSQLBuilder.select(
            table="financial_hub_connection_data",
            columns=[
                "financial_hub_connection_data_uuid",
                "financial_hub_uuid",
                "user_uuid",
                "connection_data",
            ],
            where=query,
            order_by=sort,
            limit=limit,
            offset=offset,
        )
        try:
            cursor = self._conn.cursor(dictionary=True)
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to fetch financial hub connection data: {exc}") from exc
        results: list[TXFinancialHubConnectionDataBase] = []
        for row in rows:
            user = self.get_users(
                TXCondition(TXStorageQueryOps.EQUALS, "user_uuid", row["user_uuid"])
            )[0]
            hub = self.get_financial_hubs(
                TXCondition(TXStorageQueryOps.EQUALS, "financial_hub_uuid", row["financial_hub_uuid"])
            )[0]
            conn = TXFinancialHubConnectionDataBase(
                user=user,
                financial_hub=hub,
                connection_data=row["connection_data"],
                uuid=row["financial_hub_connection_data_uuid"],
            )
            results.append(conn)
        return results

    def insert_financial_hub_connection_data(
        self,
        financial_hub_uuid: str,
        user_uuid: str,
        connection_data: str,
        uuid: str | None = None,
    ) -> str:
        """Insert a new financial hub connection data row and return its UUID."""
        self._ensure_connection()
        TXUtils.validate_json(connection_data)
        conn_uuid = TXUtils.generate_uuid() if uuid is None else uuid
        data = {
            "financial_hub_connection_data_uuid": conn_uuid,
            "financial_hub_uuid": financial_hub_uuid,
            "user_uuid": user_uuid,
            "connection_data": connection_data,
        }
        sql, params = TXSQLBuilder.insert(
            table="financial_hub_connection_data",
            data=data,
        )
        try:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            self._conn.commit()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to insert financial hub connection data: {exc}") from exc
        return conn_uuid

    def update_financial_hub_connection_data(
        self,
        uuid: str,
        financial_hub_uuid: str | None = None,
        user_uuid: str | None = None,
        connection_data: str | None = None,
    ) -> None:
        """Update an existing financial hub connection data row by UUID."""
        self._ensure_connection()
        data: Dict[str, Any] = {}
        if financial_hub_uuid is not None:
            data["financial_hub_uuid"] = financial_hub_uuid
        if user_uuid is not None:
            data["user_uuid"] = user_uuid
        if connection_data is not None:
            TXUtils.validate_json(connection_data)
            data["connection_data"] = connection_data
        sql, params = TXSQLBuilder.update(
            table="financial_hub_connection_data",
            data=data,
            where=TXCondition(TXStorageQueryOps.EQUALS, "financial_hub_connection_data_uuid", uuid),
        )
        try:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            self._conn.commit()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to update financial hub connection data: {exc}") from exc

    def delete_financial_hub_connection_data(self, uuid: str) -> None:
        """Delete a financial hub connection data row by UUID."""
        self._ensure_connection()
        sql, params = TXSQLBuilder.delete(
            table="financial_hub_connection_data",
            where=TXCondition(TXStorageQueryOps.EQUALS, "financial_hub_connection_data_uuid", uuid),
        )
        try:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            self._conn.commit()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to delete financial hub connection data: {exc}") from exc

    # --- WALLET CRUD ---
    def get_wallets(
        self,
        query: TXQueryNode | None = None,
        sort: list[TXSortCriterion] | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[TXWalletBase]:
        """
        Retrieve wallets matching the given query, sort, offset, and limit.
        Returns a list of TXWalletBase objects.
        """
        self._ensure_connection()
        base_where = TXCondition(TXStorageQueryOps.EQUALS, "deleted", 0)
        where = base_where if query is None else TXLogicalQuery(TXStorageQueryOps.AND, query, base_where)
        sql, params = TXSQLBuilder.select(
            table="wallet",
            columns=[
                "wallet_uuid",
                "user_uuid",
                "financial_hub_uuid",
                "currency_uuid",
                "name",
                "details_data",
                "content_type",
                "UNIX_TIMESTAMP(initial_value_datetime) AS initial_ts",
                "total_value",
                "UNIX_TIMESTAMP(total_value_datetime) AS total_ts",
                "connection_data",
            ],
            where=where,
            order_by=sort,
            limit=limit,
            offset=offset,
        )
        try:
            cursor = self._conn.cursor(dictionary=True)
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to fetch wallets: {exc}") from exc
        wallets: list[TXWalletBase] = []
        for row in rows:
            user = self.get_users(TXCondition(TXStorageQueryOps.EQUALS, "user_uuid", row["user_uuid"]))[0]
            hub = self.get_financial_hubs(TXCondition(TXStorageQueryOps.EQUALS, "financial_hub_uuid", row["financial_hub_uuid"]))[0]
            currency = None
            if row.get("currency_uuid"):
                currency = self.get_currencies(TXCondition(TXStorageQueryOps.EQUALS, "currency_uuid", row["currency_uuid"]))[0]
            wallet = TXWalletBase(
                user=user,
                financial_hub=hub,
                currency=currency,
                name=row["name"],
                content_type=TXAssetType(row["content_type"]),
                uuid=row["wallet_uuid"],
            )
            # Optional fields
            if row.get("details_data") is not None:
                wallet.details_data = row["details_data"]
            if row.get("initial_ts") is not None:
                wallet.initial_value_datetime = int(row["initial_ts"])            
            if row.get("total_value") is not None:
                wallet.total_value = float(row["total_value"])
            if row.get("total_ts") is not None:
                wallet.total_value_datetime = int(row["total_ts"])            
            if row.get("connection_data") is not None:
                wallet.connection_data = row["connection_data"]
            wallets.append(wallet)
        return wallets

    def insert_wallet(
        self,
        user_uuid: str,
        financial_hub_uuid: str,
        name: str,
        content_type: TXAssetType,
        currency_uuid: str | None = None,
        details_data: str | None = None,
        initial_value: float | None = None,
        initial_value_datetime: int | None = None,
        total_value: float | None = None,
        total_value_datetime: int | None = None,
        connection_data: str | None = None,
        uuid: str | None = None,
    ) -> str:
        """Insert a new wallet and return its UUID."""
        self._ensure_connection()
        if details_data is not None:
            TXUtils.validate_json(details_data)
        if connection_data is not None:
            TXUtils.validate_json(connection_data)
        wallet_uuid = TXUtils.generate_uuid() if uuid is None else uuid
        data: Dict[str, Any] = {
            "wallet_uuid": wallet_uuid,
            "user_uuid": user_uuid,
            "financial_hub_uuid": financial_hub_uuid,
            "currency_uuid": currency_uuid,
            "name": name,
            "details_data": details_data,
            "content_type": content_type.value,
            "total_value": total_value,
            "connection_data": connection_data,
        }
        if initial_value_datetime is not None:
            data["initial_value_datetime"] = dt.fromtimestamp(initial_value_datetime).strftime('%Y-%m-%d %H:%M:%S')
        if total_value_datetime is not None:
            data["total_value_datetime"] = dt.fromtimestamp(total_value_datetime).strftime('%Y-%m-%d %H:%M:%S')
        sql, params = TXSQLBuilder.insert(
            table="wallet",
            data=data,
        )
        try:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            self._conn.commit()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to insert wallet: {exc}") from exc
        return wallet_uuid

    def update_wallet(
        self,
        uuid: str,
        user_uuid: str | None = None,
        financial_hub_uuid: str | None = None,
        name: str | None = None,
        content_type: TXAssetType | None = None,
        currency_uuid: str | None = None,
        details_data: str | None = None,
        initial_value: float | None = None,
        initial_value_datetime: int | None = None,
        total_value: float | None = None,
        total_value_datetime: int | None = None,
        connection_data: str | None = None,
    ) -> None:
        """Update an existing wallet by UUID."""
        self._ensure_connection()
        data: Dict[str, Any] = {}
        if user_uuid is not None:
            data["user_uuid"] = user_uuid
        if financial_hub_uuid is not None:
            data["financial_hub_uuid"] = financial_hub_uuid
        if name is not None:
            data["name"] = name
        if content_type is not None:
            data["content_type"] = content_type.value
        if currency_uuid is not None:
            data["currency_uuid"] = currency_uuid
        if details_data is not None:
            TXUtils.validate_json(details_data)
            data["details_data"] = details_data

        if initial_value_datetime is not None:
            data["initial_value_datetime"] = dt.fromtimestamp(initial_value_datetime).strftime('%Y-%m-%d %H:%M:%S')
        if total_value is not None:
            data["total_value"] = total_value
        if total_value_datetime is not None:
            data["total_value_datetime"] = dt.fromtimestamp(total_value_datetime).strftime('%Y-%m-%d %H:%M:%S')
        if connection_data is not None:
            TXUtils.validate_json(connection_data)
            data["connection_data"] = connection_data
        sql, params = TXSQLBuilder.update(
            table="wallet",
            data=data,
            where=TXCondition(TXStorageQueryOps.EQUALS, "wallet_uuid", uuid),
        )
        try:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            self._conn.commit()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to update wallet: {exc}") from exc

    def delete_wallet(self, uuid: str) -> None:
        """Soft-delete a wallet by setting deleted = 1."""
        self._ensure_connection()
        sql, params = TXSQLBuilder.update(
            table="wallet",
            data={"deleted": 1},
            where=TXCondition(TXStorageQueryOps.EQUALS, "wallet_uuid", uuid),
        )
        try:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            self._conn.commit()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to delete wallet: {exc}") from exc

    # --- TRANSACTION CRUD ---
    def get_transactions(
        self,
        query: TXQueryNode | None = None,
        sort: list[TXSortCriterion] | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[TXTransactionBase]:
        """
        Retrieve transactions matching the given query, sort, offset, and limit.
        Returns a list of TXTransactionBase objects.
        """
        self._ensure_connection()
        base_where = TXCondition(TXStorageQueryOps.EQUALS, "deleted", 0)
        where = base_where if query is None else TXLogicalQuery(TXStorageQueryOps.AND, query, base_where)
        sql, params = TXSQLBuilder.select(
            table="transaction",
            columns=[
                "transaction_uuid",
                "origin_transaction_uuid",
                "source_wallet_uuid",
                "target_wallet_uuid",
                "bot_uuid",
                "UNIX_TIMESTAMP(start_datetime) AS start_ts",
                "UNIX_TIMESTAMP(end_datetime) AS end_ts",
                "operational_mode",
                "source_value",
                "target_value",
                "status",
                "annotations",
                "`order`",
            ],
            where=where,
            order_by=sort,
            limit=limit,
            offset=offset,
        )
        try:
            cursor = self._conn.cursor(dictionary=True)
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to fetch transactions: {exc}") from exc
        
        transactions: list[TXTransactionBase] = []
        for row in rows:
            transaction = TXTransactionBase(uuid=row["transaction_uuid"])
            
            # Set origin transaction if available
            if row.get("origin_transaction_uuid"):
                origin_transactions = self.get_transactions(
                    TXCondition(TXStorageQueryOps.EQUALS, "transaction_uuid", row["origin_transaction_uuid"])
                )
                if len(origin_transactions) == 1:
                    transaction.origin_transaction = origin_transactions[0]
            
            # Set source wallet if available
            if row.get("source_wallet_uuid"):
                source_wallets = self.get_wallets(
                    TXCondition(TXStorageQueryOps.EQUALS, "wallet_uuid", row["source_wallet_uuid"])
                )
                if len(source_wallets) == 1:
                    transaction.source_wallet = source_wallets[0]
            
            # Set target wallet if available
            if row.get("target_wallet_uuid"):
                target_wallets = self.get_wallets(
                    TXCondition(TXStorageQueryOps.EQUALS, "wallet_uuid", row["target_wallet_uuid"])
                )
                if len(target_wallets) == 1:
                    transaction.target_wallet = target_wallets[0]
            
            # Set bot if available
            if row.get("bot_uuid"):
                bots = self.get_bots(
                    TXCondition(TXStorageQueryOps.EQUALS, "bot_uuid", row["bot_uuid"])
                )
                if len(bots) == 1:
                    transaction.bot = bots[0]
            
            # Set timestamps
            if row.get("start_ts") is not None:
                transaction.start_datetime = int(row["start_ts"])
            if row.get("end_ts") is not None:
                transaction.end_datetime = int(row["end_ts"])
            
            # Set operational mode
            if row.get("operational_mode"):
                transaction.operational_mode = TXTransOperationalMode(row["operational_mode"])
            
            # Set values
            if row.get("source_value") is not None:
                transaction.source_value = float(row["source_value"])
            if row.get("target_value") is not None:
                transaction.target_value = float(row["target_value"])
            
            # Set status
            if row.get("status"):
                transaction.status = TXTransStatus(row["status"])
            
            # Set optional fields
            if row.get("annotations") is not None:
                transaction.annotations = row["annotations"]
            if row.get("order") is not None:
                transaction.order = int(row["order"])
            
            transactions.append(transaction)
        
        return transactions

    def insert_transaction(
        self,
        origin_transaction_uuid: str | None = None,
        source_wallet_uuid: str | None = None,
        target_wallet_uuid: str | None = None,
        bot_uuid: str | None = None,
        start_datetime: int | None = None,
        end_datetime: int | None = None,
        operational_mode: TXTransOperationalMode | None = None,
        source_value: float | None = None,
        target_value: float | None = None,
        status: TXTransStatus | None = None,
        annotations: str | None = None,
        order: int = 0,
        uuid: str | None = None,
    ) -> str:
        """Insert a new transaction and return its UUID."""
        self._ensure_connection()
        
        transaction_uuid = TXUtils.generate_uuid() if uuid is None else uuid
        data: Dict[str, Any] = {
            "transaction_uuid": transaction_uuid,
            "origin_transaction_uuid": origin_transaction_uuid,
            "source_wallet_uuid": source_wallet_uuid,
            "target_wallet_uuid": target_wallet_uuid,
            "bot_uuid": bot_uuid,
            "source_value": source_value,
            "target_value": target_value,
            "annotations": annotations,
            "order": order,
        }
        
        if start_datetime is not None:
            data["start_datetime"] = dt.fromtimestamp(start_datetime).strftime('%Y-%m-%d %H:%M:%S')
        if end_datetime is not None:
            data["end_datetime"] = dt.fromtimestamp(end_datetime).strftime('%Y-%m-%d %H:%M:%S')
        if operational_mode is not None:
            data["operational_mode"] = operational_mode.value
        if status is not None:
            data["status"] = status.value
        
        sql, params = TXSQLBuilder.insert(
            table="transaction",
            data=data,
        )
        try:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            self._conn.commit()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to insert transaction: {exc}") from exc
        
        return transaction_uuid

    def update_transaction(
        self,
        uuid: str,
        origin_transaction_uuid: str | None = None,
        source_wallet_uuid: str | None = None,
        target_wallet_uuid: str | None = None,
        bot_uuid: str | None = None,
        start_datetime: int | None = None,
        end_datetime: int | None = None,
        operational_mode: TXTransOperationalMode | None = None,
        source_value: float | None = None,
        target_value: float | None = None,
        status: TXTransStatus | None = None,
        annotations: str | None = None,
        order: int | None = None,
    ) -> None:
        """Update an existing transaction by UUID."""
        self._ensure_connection()
        
        data: Dict[str, Any] = {}
        if origin_transaction_uuid is not None:
            data["origin_transaction_uuid"] = origin_transaction_uuid
        if source_wallet_uuid is not None:
            data["source_wallet_uuid"] = source_wallet_uuid
        if target_wallet_uuid is not None:
            data["target_wallet_uuid"] = target_wallet_uuid
        if bot_uuid is not None:
            data["bot_uuid"] = bot_uuid
        if start_datetime is not None:
            data["start_datetime"] = dt.fromtimestamp(start_datetime).strftime('%Y-%m-%d %H:%M:%S')
        if end_datetime is not None:
            data["end_datetime"] = dt.fromtimestamp(end_datetime).strftime('%Y-%m-%d %H:%M:%S')
        if operational_mode is not None:
            data["operational_mode"] = operational_mode.value
        if source_value is not None:
            data["source_value"] = source_value
        if target_value is not None:
            data["target_value"] = target_value
        if status is not None:
            data["status"] = status.value
        if annotations is not None:
            data["annotations"] = annotations
        if order is not None:
            data["order"] = order
        
        sql, params = TXSQLBuilder.update(
            table="transaction",
            data=data,
            where=TXCondition(TXStorageQueryOps.EQUALS, "transaction_uuid", uuid),
        )
        try:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            self._conn.commit()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to update transaction: {exc}") from exc

    def delete_transaction(self, uuid: str) -> None:
        """Soft-delete a transaction by setting deleted = 1."""
        self._ensure_connection()
        sql, params = TXSQLBuilder.delete(
            table="transaction",
            where=TXCondition(TXStorageQueryOps.EQUALS, "transaction_uuid", uuid),
        )
        try:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            self._conn.commit()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to delete transaction: {exc}") from exc
