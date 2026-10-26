from __future__ import annotations

import argparse
import sys

from .transfer import export_scope, resolve_db_path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog='hydramind-export',
        description="Export one scope's memory graph as JSONL.",
    )
    parser.add_argument('--scope', required=True, help='scope to export')
    parser.add_argument('--db', help='path to the HydraMind SQLite database')
    parser.add_argument('out', nargs='?', default='-', help='output file (default: stdout)')
    args = parser.parse_args(argv)

    out = sys.stdout if args.out == '-' else open(args.out, 'w', encoding='utf-8')
    try:
        export_scope(resolve_db_path(args.db), args.scope, out)
    finally:
        if out is not sys.stdout:
            out.close()


if __name__ == '__main__':
    main()
