"""Postgres adapter for the app's small, explicit SQL contract.

Legacy isolated Apex/LWC endpoints remain disabled for signed-in accounts.
SQLite is retained for local development and replay tests.
"""
import os
import re
import sqlite3
from threading import Lock

_ready = set()
_schema_lock = Lock()


def postgres_enabled():
    return bool(os.getenv('APP_DATABASE_URL', '').strip())


def raw_connection():
    import psycopg
    from psycopg.rows import dict_row
    return psycopg.connect(os.environ['APP_DATABASE_URL'], row_factory=dict_row,
                           connect_timeout=10)


class AppRow(dict):
    def __getitem__(self, key):
        return list(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


class Result:
    def __init__(self, cursor):
        self.cursor = cursor
        self.rowcount = cursor.rowcount

    def fetchone(self):
        row = self.cursor.fetchone()
        return AppRow(row) if row is not None else None

    def fetchall(self):
        return [AppRow(row) for row in self.cursor.fetchall()]


def schema_contract(schema):
    tables = {}
    for table, definition in re.findall(r'CREATE TABLE IF NOT EXISTS (\w+)\((.*?)\);', schema, re.S):
        columns = re.findall(r'(?:^|,)\s*(\w+)\s+(?:TEXT|REAL|INTEGER)\b', definition)
        composite = re.search(r'PRIMARY KEY\(([^)]+)\)', definition)
        keys = composite.group(1).split(',') if composite else re.findall(r'(\w+)\s+\w+\s+PRIMARY KEY', definition)
        tables[table] = (columns, [k.strip() for k in keys])
    return tables


def translate(sql, tables):
    # Only the known app upserts are accepted; no generic SQL interpretation.
    match = re.match(r'INSERT OR (REPLACE|IGNORE) INTO (\w+)\s+VALUES\((.*?)\)\s*$', sql, re.I)
    if match:
        mode, table, values = match.groups()
        if table not in tables:
            raise ValueError('Unsupported app database table')
        columns, keys = tables[table]
        if not keys or len(values.split(',')) != len(columns):
            raise ValueError('Unsupported app database upsert')
        sql = f'INSERT INTO {table} ({",".join(columns)}) VALUES({values}) ON CONFLICT ({",".join(keys)}) '
        updates = [f'{c}=EXCLUDED.{c}' for c in columns if c not in keys]
        sql += 'DO NOTHING' if mode.upper() == 'IGNORE' or not updates else 'DO UPDATE SET ' + ','.join(updates)
    # Existing increments must qualify the current row in Postgres.
    sql = sql.replace('SET count=count+1', 'SET count=attempts.count+1')
    sql = sql.replace('SET epoch=epoch+1', 'SET epoch=org_cache_epochs.epoch+1')
    # Percent literals must be escaped for psycopg's parameter syntax.
    sql = sql.replace('%', '%%')
    # Never substitute placeholders inside SQL string literals.
    pieces = re.split(r"('(?:''|[^'])*')", sql)
    return ''.join(piece if i % 2 else piece.replace('?', '%s') for i, piece in enumerate(pieces))


class Connection:
    def __init__(self, connection, schema):
        self.connection = connection
        self.tables = schema_contract(schema)

    def execute(self, sql, params=()):
        import psycopg
        try:
            return Result(self.connection.execute(translate(sql, self.tables), params))
        except psycopg.IntegrityError as exc:
            raise sqlite3.IntegrityError('App database constraint failed') from exc

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        try:
            self.connection.rollback() if kind else self.connection.commit()
        finally:
            self.connection.close()


def connect_postgres(schema):
    url = os.environ['APP_DATABASE_URL']
    with _schema_lock:
        if url not in _ready:
            with raw_connection() as connection:
                connection.execute('SELECT pg_advisory_xact_lock(824186235)')
                ddl = schema.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'BIGSERIAL PRIMARY KEY')
                ddl = re.sub(r'\bREAL\b', 'DOUBLE PRECISION', ddl)
                for statement in ddl.split(';'):
                    if statement.strip():
                        connection.execute(statement)
            _ready.add(url)
    return Connection(raw_connection(), schema)
