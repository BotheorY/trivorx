from trivorxlib.core import TXUserRole
from trivorxlib.storages.base import *
from typing import Any, Dict, List, Tuple, Optional
import mysql.connector
from mysql.connector.connection_cext import CMySQLConnection
from mysql.connector import Error as MySQLError
import warnings
import pathlib

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
        encrypted_password: str | None = None
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
        token: str | None = None
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
            columns=[
                "user_uuid",
                "full_name",
                "login",
                "password",
                "token",
                "role",
            ],
            values=[
                uuid,
                full_name,
                login,
                encrypted_password,
                token,
                role.value,
            ],
        )
        try:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            self._conn.commit()
            cursor.close()
        except MySQLError as exc:
            raise RuntimeError(f"Failed to insert user: {exc}") from exc
        return uuid, token