from __future__ import annotations

import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Iterable, TextIO

FORMAT_VERSION = 1
_NAMESPACE = uuid.UUID('6f6d2f4e-6a1b-4f0e-9d7a-2b3c4d5e6f70')


def resolve_db_path(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit)
    for env in ('HYDRAMIND_DB', 'HYDRAMIND_DB_PATH', 'HYDRAMIND_DATABASE'):
        value = os.environ.get(env)
        if value:
            return Path(value)
    try:
        from . import db as dbmod
    except Exception:
        dbmod = None
    if dbmod is not None:
        for attr in ('DB_PATH', 'DEFAULT_DB_PATH', 'DATABASE_PATH'):
            value = getattr(dbmod, attr, None)
            if callable(value):
                try:
                    value = value()
                except Exception:
                    value = None
            if value:
                return Path(value)
        for name in ('get_db_path', 'db_path', 'default_db_path'):
            fn = getattr(dbmod, name, None)
            if callable(fn):
                try:
                    value = fn()
                except Exception:
                    value = None
                if value:
                    return Path(value)
    return Path('hydramind.db')


def _connect(path: str | Path) -> sqlite3.Connection:
    p = Path(path)
    if str(p) != ':memory:':
        p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    return conn


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [row[0] for row in rows]


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f'PRAGMA table_info({_quote(table)})')]


def _select(
    conn: sqlite3.Connection,
    table: str,
    columns: list[str],
    where: str,
    params: Iterable[Any],
) -> list[dict[str, Any]]:
    sql = f"SELECT {', '.join(_quote(c) for c in columns)} FROM {_quote(table)}"
    if where:
        sql += f' WHERE {where}'
    cursor = conn.execute(sql, tuple(params))
    names = [d[0] for d in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def _select_in(
    conn: sqlite3.Connection,
    table: str,
    columns: list[str],
    id_columns: list[str],
    ids: set[str],
) -> list[dict[str, Any]]:
    if not ids:
        return []
    values = list(ids)
    rows: list[dict[str, Any]] = []
    for start in range(0, len(values), 500):
        chunk = values[start : start + 500]
        placeholders = ','.join('?' for _ in chunk)
        where = ' OR '.join(f'{_quote(c)} IN ({placeholders})' for c in id_columns)
        params = tuple(chunk * len(id_columns))
        rows.extend(_select(conn, table, columns, where, params))
    return rows


def _ids(rows: list[dict[str, Any]], columns: list[str]) -> set[str]:
    if 'id' not in columns:
        return set()
    return {str(row['id']) for row in rows if row.get('id') is not None}


def _scope_rows(
    conn: sqlite3.Connection, table: str, columns: list[str], scope: str
) -> list[dict[str, Any]]:
    if 'scope' in columns:
        return _select(conn, table, columns, f"{_quote('scope')} = ?", (scope,))
    if table in ('scopes', 'scope'):
        for column in ('name', 'id', 'scope_id'):
            if column in columns:
                return _select(conn, table, columns, f'{_quote(column)} = ?', (scope,))
    return []


def export_scope(db_path: str | Path, scope: str, out: TextIO) -> None:
    conn = _connect(db_path)
    try:
        tables = _tables(conn)
        exported: dict[str, list[dict[str, Any]]] = {}
        ids_by_table: dict[str, set[str]] = {}

        for table in tables:
            columns = _columns(conn, table)
            if not columns:
                continue
            rows = _scope_rows(conn, table, columns, scope)
            if rows:
                exported[table] = rows
                ids_by_table[table] = _ids(rows, columns)

        all_ids: set[str] = set()
        for ids in ids_by_table.values():
            all_ids.update(ids)

        for table in tables:
            if table in exported:
                continue
            columns = _columns(conn, table)
            if not columns:
                continue
            id_columns = [c for c in columns if c.endswith('_id')]
            if not id_columns:
                continue
            rows = _select_in(conn, table, columns, id_columns, all_ids)
            if rows:
                exported[table] = rows

        meta = {
            'type': 'meta',
            'version': FORMAT_VERSION,
            'scope': scope,
            'tables': sorted(exported),
        }
        out.write(json.dumps(meta, ensure_ascii=False) + '\n')
        for table in sorted(exported):
            for row in exported[table]:
                out.write(
                    json.dumps(
                        {'type': 'row', 'table': table, 'data': row},
                        ensure_ascii=False,
                        default=str,
                    )
                    + '\n'
                )
    finally:
        conn.close()


def _priority(table: str) -> int:
    return {
        'scopes': 0,
        'scope': 0,
        'memories': 1,
        'memory': 1,
        'edges': 2,
        'edge': 2,
    }.get(table, 3)


def _insert_ignore(conn: sqlite3.Connection, table: str, data: dict[str, Any]) -> None:
    columns = list(data)
    sql = (
        f'INSERT OR IGNORE INTO {_quote(table)} '
        f"({', '.join(_quote(c) for c in columns)}) "
        f"VALUES ({', '.join('?' for _ in columns)})"
    )
    conn.execute(sql, tuple(data[c] for c in columns))


def _insert_if_absent(conn: sqlite3.Connection, table: str, data: dict[str, Any]) -> None:
    columns = list(data)
    where = ' AND '.join(f'{_quote(c)} IS ?' for c in columns)
    exists = conn.execute(
        f'SELECT 1 FROM {_quote(table)} WHERE {where} LIMIT 1',
        tuple(data[c] for c in columns),
    ).fetchone()
    if not exists:
        _insert_ignore(conn, table, data)


def import_file(
    db_path: str | Path, file: str | Path | TextIO, target_scope: str | None = None
) -> None:
    close = False
    if isinstance(file, (str, Path)):
        handle = open(file, encoding='utf-8')
        close = True
    else:
        handle = file
    try:
        items = [json.loads(line) for line in handle if line.strip()]
    finally:
        if close:
            handle.close()

    meta = next((item for item in items if item.get('type') == 'meta'), None)
    if meta is None:
        raise ValueError('missing export metadata')
    source_scope = meta.get('scope')
    scope = target_scope or source_scope
    if not scope:
        raise ValueError('missing target scope')

    rows = [item for item in items if item.get('type') == 'row']
    rows.sort(key=lambda item: _priority(item['table']))

    conn = _connect(db_path)
    conn.execute('PRAGMA foreign_keys=OFF')
    try:
        id_map: dict[tuple[str, str], str] = {}
        for item in rows:
            table = item['table']
            data = item.get('data') or {}
            if 'id' not in data:
                continue
            old = str(data['id'])
            if table in ('scopes', 'scope') and 'name' not in data:
                new = scope
            elif scope == source_scope:
                new = old
            else:
                new = str(uuid.uuid5(_NAMESPACE, f'{scope}:{table}:{old}'))
            id_map[(table, old)] = new

        global_map: dict[str, str] = {}
        for (_, old), new in id_map.items():
            global_map.setdefault(old, new)

        for item in rows:
            table = item['table']
            data = dict(item.get('data') or {})
            columns = _columns(conn, table)
            if not columns:
                continue

            if table in ('scopes', 'scope'):
                if 'name' in columns:
                    data['name'] = scope
                elif 'id' in columns:
                    data['id'] = scope

            if 'id' in data and 'id' in columns:
                data['id'] = id_map.get((table, str(data['id'])), data['id'])

            for column in list(data):
                if column.endswith('_id') and column != 'id':
                    value = data[column]
                    if value is not None and str(value) in global_map:
                        data[column] = global_map[str(value)]

            if 'scope' in columns:
                data['scope'] = scope

            data = {key: value for key, value in data.items() if key in columns}
            if not data:
                continue

            if 'id' in data:
                _insert_ignore(conn, table, data)
            else:
                _insert_if_absent(conn, table, data)

        conn.commit()
    finally:
        conn.close()
