from __future__ import annotations

import argparse
import sys

from .transfer import import_file, resolve_db_path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog='hydramind-import',
        description='Import a JSONL memory graph export.',
    )
    parser.add_argument('file', nargs='?', default='-', help='input file (default: stdin)')
    parser.add_argument('--scope', help='target scope (default: scope from the export)')
    parser.add_argument('--db', help='path to the HydraMind SQLite database')
    args = parser.parse_args(argv)

    if args.file == '-':
        import_file(resolve_db_path(args.db), sys.stdin, args.scope)
    else:
        import_file(resolve_db_path(args.db), args.file, args.scope)


if __name__ == '__main__':
    main()
