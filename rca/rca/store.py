import json
import sqlite3
import threading
import uuid
from pathlib import Path

from .common import compact, epoch, now, redact


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.db:
            self.db.executescript('''
              PRAGMA journal_mode=WAL;
              CREATE TABLE IF NOT EXISTS incidents (
                id TEXT PRIMARY KEY, dedup TEXT UNIQUE, created TEXT, state TEXT,
                data TEXT, result TEXT, started TEXT);
              CREATE TABLE IF NOT EXISTS evidence (
                id TEXT PRIMARY KEY, incident TEXT, tool TEXT, args TEXT, data TEXT);
              CREATE TABLE IF NOT EXISTS windows (
                id TEXT PRIMARY KEY, node TEXT, uid TEXT, container TEXT, start REAL, end REAL, data TEXT);
              CREATE INDEX IF NOT EXISTS windows_lookup ON windows(uid,start);
              CREATE TABLE IF NOT EXISTS heartbeats (node TEXT PRIMARY KEY, data TEXT);
              CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, data TEXT);
            ''')
            self.db.execute("UPDATE incidents SET state='interrupted' WHERE state='running'")

    def add(self, incident, dedup):
        iid = str(uuid.uuid4())
        with self.lock, self.db:
            self.db.execute('INSERT OR IGNORE INTO incidents VALUES (?,?,?,?,?,?,?)',
                            (iid, dedup, now(), 'capturing', compact(redact(incident)), None, None))
            row = self.db.execute('SELECT id FROM incidents WHERE dedup=?', (dedup,)).fetchone()
            return row['id'], row['id'] == iid

    def get(self, iid):
        with self.lock:
            row = self.db.execute('SELECT * FROM incidents WHERE id=?', (iid,)).fetchone()
            if row is None:
                raise ValueError('unknown incident')
            out = dict(row)
            out['data'] = json.loads(out['data'])
            out['result'] = json.loads(out['result']) if out['result'] else None
            return out

    def list(self):
        with self.lock:
            return [dict(r) for r in self.db.execute(
                'SELECT id,created,state,started FROM incidents ORDER BY created DESC LIMIT 100')]

    def update(self, iid, state, result=None):
        with self.lock, self.db:
            self.db.execute('UPDATE incidents SET state=?,result=? WHERE id=?',
                            (state, compact(redact(result)) if result is not None else None, iid))

    def claim(self, iid, daily_limit):
        with self.lock, self.db:
            row = self.db.execute('SELECT state FROM incidents WHERE id=?', (iid,)).fetchone()
            if not row or row['state'] == 'running':
                return False
            day = now()[:10]
            # Count attempts, including failures and retries, not just unique incidents.
            key = 'attempts:' + day
            attempts = int(self.meta(key) or 0)
            if attempts >= daily_limit:
                raise ValueError('daily investigation limit reached')
            self.db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', (key, compact(attempts + 1)))
            self.db.execute("UPDATE incidents SET state='running',started=? WHERE id=?", (now(), iid))
            return True

    def evidence(self, iid, tool, args, data):
        eid = 'ev-' + uuid.uuid4().hex[:12]
        record = {'evidence_id': eid, 'tool': tool, 'retrieved_at': now(), **redact(data)}
        with self.lock, self.db:
            self.db.execute('INSERT INTO evidence VALUES (?,?,?,?,?)',
                            (eid, iid, tool, compact(args), compact(record)))
        return record

    def cached(self, iid, tool, args):
        with self.lock:
            row = self.db.execute('SELECT data FROM evidence WHERE incident=? AND tool=? AND args=? ORDER BY rowid DESC LIMIT 1',
                                  (iid, tool, compact(args))).fetchone()
            return json.loads(row[0]) if row else None

    def all_evidence(self, iid):
        with self.lock:
            return [json.loads(r[0]) for r in self.db.execute('SELECT data FROM evidence WHERE incident=?', (iid,))]

    def ingest(self, payload):
        if payload.get('node') not in ('worker-1', 'worker-3'):
            raise ValueError('unexpected collector node')
        if len(payload.get('windows', [])) > 200:
            raise ValueError('too many windows')
        with self.lock, self.db:
            self.db.execute('INSERT OR REPLACE INTO heartbeats VALUES (?,?)',
                            (payload['node'], compact({**payload.get('health', {}), 'received_at': now()})))
            for w in payload.get('windows', []):
                start, end = float(w['start']), float(w['end'])
                if not (0 < end - start <= 15) or len(compact(w)) > 5000:
                    raise ValueError('invalid window')
                key = compact([payload['node'], w['pod_uid'], w['container_id'], start])
                self.db.execute('INSERT OR REPLACE INTO windows VALUES (?,?,?,?,?,?,?)',
                                (key, payload['node'], w['pod_uid'], w['container_id'], start, end, compact(w)))
            self.db.execute('DELETE FROM windows WHERE end < ?', (epoch(now()) - 600,))

    def windows(self, uid, container_id, start, end):
        with self.lock:
            rows = self.db.execute('SELECT data FROM windows WHERE uid=? AND container=? AND end>? AND start<? ORDER BY start',
                                   (uid, container_id, start, end))
            return [json.loads(r[0]) for r in rows]

    def health(self):
        with self.lock:
            return {r['node']: json.loads(r['data']) for r in self.db.execute('SELECT * FROM heartbeats')}

    def meta(self, key, value=None):
        with self.lock, self.db:
            if value is not None:
                self.db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', (key, compact(value)))
            row = self.db.execute('SELECT data FROM meta WHERE key=?', (key,)).fetchone()
            return json.loads(row[0]) if row else None
