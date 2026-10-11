"""Offline, copy-only migration. Stop backend/worker first; keep source backup."""
import argparse
import json
import sqlite3
import time
from pathlib import Path
from Backend.AI.app.account_api import SCHEMA
from Backend.AI.app.services.app_database import connect_postgres, postgres_enabled, schema_contract


def migrate(source):
    if not postgres_enabled():
        raise ValueError('Set APP_DATABASE_URL before migration.')
    if not source.is_file():
        raise ValueError('SQLite source does not exist.')
    # URI read-only mode prevents modifying or creating the source.
    connection = sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    contract = schema_contract(SCHEMA)
    counts = {}
    try:
        with connect_postgres(SCHEMA) as target:
            target.connection.execute('SELECT pg_advisory_xact_lock(824186235)')
            if any(target.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in contract):
                raise ValueError('Destination must be empty. Migration never merges accounts or replaces existing data.')
            available = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for table, (columns, _) in contract.items():
                if table not in available or table == 'monitor_jobs':
                    continue
                rows = connection.execute(f'SELECT {",".join(columns)} FROM {table}').fetchall()
                placeholders = ','.join('?' for _ in columns)
                for row in rows:
                    target.execute(f'INSERT INTO {table} ({",".join(columns)}) VALUES({placeholders})', tuple(row))
                counts[table] = len(rows)
            for row in target.execute('SELECT id,user_id,org_id,payload FROM workspace_packages').fetchall():
                package = json.loads(row['payload'])['package']
                if package.get('state') in {'pending','running','unknown'}:
                    target.execute('INSERT INTO monitor_jobs VALUES(?,?,?,?)', (row['id'], row['user_id'], row['org_id'], time.time()))
            # Preserve the generated activity sequence after importing explicit IDs.
            target.connection.execute("SELECT setval(pg_get_serial_sequence('activity','id'), COALESCE(MAX(id),1), MAX(id) IS NOT NULL) FROM activity")
    finally:
        connection.close()
    return counts


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=Path('.app-data/accounts.sqlite3'))
    args = parser.parse_args()
    counts = migrate(args.source)
    print('Migration committed. Source unchanged. Copied row counts:', counts)
