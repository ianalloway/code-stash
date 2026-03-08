"""Code Stash - CLI code snippet manager."""
import argparse
import os
import sys
import sqlite3
import json
from pathlib import Path

DB_PATH = Path.home() / ".code-stash" / "snippets.db"

def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS snippets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            code TEXT NOT NULL,
            language TEXT,
            tags TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn

def add_snippet(title, code, language=None, tags=None):
    conn = init_db()
    tags_str = ",".join(tags) if tags else ""
    conn.execute(
        "INSERT INTO snippets (title, code, language, tags) VALUES (?, ?, ?, ?)",
        (title, code, language, tags_str)
    )
    conn.commit()
    print(f"Added snippet: {title} (ID: {conn.execute('SELECT last_insert_rowid()').fetchone()[0]})")

def list_snippets(language=None, tag=None):
    conn = init_db()
    query = "SELECT * FROM snippets WHERE 1=1"
    params = []
    if language:
        query += " AND language = ?"
        params.append(language)
    if tag:
        query += " AND tags LIKE ?"
        params.append(f"%{tag}%")
    query += " ORDER BY created_at DESC"
    
    rows = conn.execute(query, params).fetchall()
    if not rows:
        print("No snippets found.")
        return
    for row in rows:
        print(f"[{row['id']}] {row['title']} | {row['language'] or '?'} | {row['tags'] or ''}")

def get_snippet(snippet_id):
    conn = init_db()
    row = conn.execute("SELECT * FROM snippets WHERE id = ?", (snippet_id,)).fetchone()
    if not row:
        print("Snippet not found.")
        return
    print(f"Title: {row['title']}")
    print(f"Language: {row['language'] or 'N/A'}")
    print(f"Tags: {row['tags'] or 'N/A'}")
    print(f"\n--- Code ---\n{row['code']}")

def delete_snippet(snippet_id):
    conn = init_db()
    conn.execute("DELETE FROM snippets WHERE id = ?", (snippet_id,))
    conn.commit()
    print(f"Deleted snippet {snippet_id}")

def export_snippets(filepath):
    conn = init_db()
    rows = conn.execute("SELECT * FROM snippets").fetchall()
    data = [dict(row) for row in rows]
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    print(f"Exported {len(data)} snippets to {filepath}")

def import_snippets(filepath):
    with open(filepath, 'r') as f:
        data = json.load(f)
    conn = init_db()
    for item in data:
        conn.execute(
            "INSERT INTO snippets (title, code, language, tags) VALUES (?, ?, ?, ?)",
            (item['title'], item['code'], item.get('language'), item.get('tags', ''))
        )
    conn.commit()
    print(f"Imported {len(data)} snippets from {filepath}")

def main():
    parser = argparse.ArgumentParser(prog="code-stash")
    sub = parser.add_subparsers(dest="command")
    
    sub.add_parser("add", help="Add a snippet").add_argument("title")
    sub.add_parser("list", help="List snippets")
    sub.add_parser("get", help="Get snippet by ID").add_argument("id", type=int)
    sub.add_parser("delete", help="Delete snippet").add_argument("id", type=int)
    sub.add_parser("export", help="Export snippets").add_argument("filepath")
    sub.add_parser("import", help="Import snippets").add_argument("filepath")
    
    args = parser.parse_args()
    
    if args.command == "add":
        import sys
        print("Enter code (Ctrl+D to finish):")
        code = sys.stdin.read()
        add_snippet(args.title, code)
    elif args.command == "list":
        list_snippets()
    elif args.command == "get":
        get_snippet(args.id)
    elif args.command == "delete":
        delete_snippet(args.id)
    elif args.command == "export":
        export_snippets(args.filepath)
    elif args.command == "import":
        import_snippets(args.filepath)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
