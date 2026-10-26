import sqlite3

from hydramind.transfer import export_scope, import_file

SCHEMA = '''
CREATE TABLE scopes(name TEXT PRIMARY KEY);
CREATE TABLE memories(
    id TEXT PRIMARY KEY,
    scope TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE edges(
    id TEXT PRIMARY KEY,
    scope TEXT NOT NULL,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE trust_events(
    id TEXT PRIMARY KEY,
    scope TEXT NOT NULL,
    memory_id TEXT NOT NULL,
    before_trust REAL NOT NULL,
    after_trust REAL NOT NULL,
    created_at TEXT NOT NULL
);
'''


def _db(path):
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn


def test_export_import_round_trip_is_idempotent(tmp_path):
    source = tmp_path / 'source.db'
    conn = _db(source)
    conn.executescript('''
    INSERT INTO scopes VALUES ('acme');
    INSERT INTO memories VALUES ('m1', 'acme', 'hello', '2024-01-01T00:00:00Z');
    INSERT INTO memories VALUES ('m2', 'acme', 'world', '2024-01-02T00:00:00Z');
    INSERT INTO edges VALUES ('e1', 'acme', 'm1', 'm2', 'CONTRADICTS', '2024-01-03T00:00:00Z');
    INSERT INTO trust_events VALUES ('t1', 'acme', 'm1', 0.5, 0.4, '2024-01-04T00:00:00Z');
    ''')
    conn.commit()
    conn.close()

    exported = tmp_path / 'acme.jsonl'
    with exported.open('w', encoding='utf-8') as handle:
        export_scope(source, 'acme', handle)

    target = tmp_path / 'target.db'
    _db(target).close()

    import_file(target, exported, 'copy')
    import_file(target, exported, 'copy')

    conn = sqlite3.connect(target)
    assert conn.execute('SELECT COUNT(*) FROM memories').fetchone()[0] == 2
    assert conn.execute('SELECT COUNT(*) FROM edges').fetchone()[0] == 1
    assert conn.execute('SELECT COUNT(*) FROM trust_events').fetchone()[0] == 1
    assert conn.execute(
        'SELECT COUNT(*) FROM memories WHERE scope = ?', ('copy',)
    ).fetchone()[0] == 2
    source_id, target_id = conn.execute('SELECT source_id, target_id FROM edges').fetchone()
    assert source_id != target_id
    assert conn.execute(
        'SELECT before_trust, after_trust FROM trust_events'
    ).fetchone() == (0.5, 0.4)
    conn.close()
