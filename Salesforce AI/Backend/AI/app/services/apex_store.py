"""Durable Apex package and operation records; SQLite serializes state changes."""
import json
import sqlite3
from pathlib import Path

class ApexStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS bundles (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')

    def connect(self):
        return sqlite3.connect(self.path, timeout=30)

    def put(self, bundle):
        with self.connect() as db:
            db.execute('INSERT INTO bundles VALUES (?,?)', (bundle['id'], json.dumps(bundle)))

    def get(self, bundle_id):
        with self.connect() as db:
            row = db.execute('SELECT payload FROM bundles WHERE id=?', (bundle_id,)).fetchone()
        if row is None:
            raise KeyError(bundle_id)
        return json.loads(row[0])

    @staticmethod
    def component_keys(bundle):
        return {(item['metadataType'],item['fullName'].casefold()) for item in bundle.get('components',[])}

    def claim(self, bundle_id, operation):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT payload FROM bundles WHERE id=?', (bundle_id,)).fetchone()
            if row is None:
                raise KeyError(bundle_id)
            bundle = json.loads(row[0])
            if bundle.get('state') in {'running', 'pending', 'unknown', 'deployed'}:
                raise ValueError('Operation blocked by saved state. Check the deployment report; do not submit again.')
            for (payload,) in db.execute('SELECT payload FROM bundles WHERE id<>?', (bundle_id,)):
                other = json.loads(payload)
                if (other.get('targetOrg') == bundle.get('targetOrg')
                        and self.component_keys(other).intersection(self.component_keys(bundle))
                        and other.get('state') in {'running', 'pending', 'unknown', 'deployed'}):
                    raise ValueError('Another saved operation owns this component name in the target org.')
            bundle.update(state='running', operation=operation)
            db.execute('UPDATE bundles SET payload=? WHERE id=?', (json.dumps(bundle), bundle_id))
        return bundle

    def finish(self, bundle_id, **updates):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT payload FROM bundles WHERE id=?', (bundle_id,)).fetchone()
            if row is None:
                raise KeyError(bundle_id)
            bundle = json.loads(row[0])
            bundle.update(updates)
            db.execute('UPDATE bundles SET payload=? WHERE id=?', (json.dumps(bundle), bundle_id))
        return bundle
