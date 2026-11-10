import argparse
import json
import sys
from typing import Any
from .db import HydraDB

def export_scope(scope: str, db: HydraDB) -> None:
    data = db.get_full_graph(scope)
    for entry in data:
        print(json.dumps(entry))

def import_scope(scope: str, file_path: str, db: HydraDB) -> None:
    with open(file_path, 'r') as f:
        for line in f:
            if line.strip():
                entry = json.loads(line)
                db.merge_memory(scope, entry)

def main() -> None:
    parser = argparse.ArgumentParser(description="HydraMind CLI")
    subparsers = parser.add_subparsers(dest="command")
    
    export = subparsers.add_parser("export")
    export.add_argument("--scope", required=True)
    
    imp = subparsers.add_parser("import")
    imp.add_argument("--scope", required=True)
    imp.add_argument("file", help="Path to JSONL file")
    
    args = parser.parse_args()
    db = HydraDB()
    
    if args.command == "export":
        export_scope(args.scope, db)
    elif args.command == "import":
        import_scope(args.scope, args.file, db)

if __name__ == "__main__":
    main()