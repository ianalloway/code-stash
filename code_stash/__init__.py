"""Code Stash - CLI code snippet manager."""
import argparse
import os
import sys
import sqlite3
import json
import requests
from pathlib import Path
from typing import Optional, List
import numpy as np

DB_PATH = Path.home() / ".code-stash" / "snippets.db"
CONFIG_PATH = Path.home() / ".code-stash" / "config.yaml"

DEFAULT_CONFIG = {
    "ollama_url": "http://localhost:11434",
    "ollama_model": "llama3.3",
    "embedding_model": "nomic-embed-text",
}

def load_config() -> dict:
    """Load config from YAML or return defaults."""
    import yaml
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return {**DEFAULT_CONFIG, **yaml.safe_load(f) or {}}
    return DEFAULT_CONFIG.copy()

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
            embedding BLOB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn

def get_embedding(text: str, config: dict) -> Optional[List[float]]:
    """Get embedding from Ollama."""
    try:
        resp = requests.post(
            f"{config['ollama_url']}/api/embeddings",
            json={"model": config.get("embedding_model", "nomic-embed-text"), "prompt": text},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("embedding")
    except Exception as e:
        print(f"Ollama error: {e}")
        return None

def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

def add_snippet(title: str, code: str, language: Optional[str] = None,
                tags: Optional[List[str]] = None, generate_embedding: bool = True) -> int:
    """Insert a snippet and return its new ID."""
    conn = init_db()
    tags_str = ",".join(tags) if tags else ""
    embedding = None

    if generate_embedding:
        config = load_config()
        text = f"{title}\n{code}"
        embedding = get_embedding(text, config)
        if embedding:
            import pickle
            embedding = pickle.dumps(embedding)

    cur = conn.execute(
        "INSERT INTO snippets (title, code, language, tags, embedding) VALUES (?, ?, ?, ?, ?)",
        (title, code, language, tags_str, embedding),
    )
    conn.commit()
    snippet_id = cur.lastrowid  # reliable: lastrowid on the INSERT cursor
    print(f"Added snippet: {title} (ID: {snippet_id})")
    if embedding:
        print("  → Embedding generated for semantic search")
    return snippet_id

def list_snippets(language: Optional[str] = None, tag: Optional[str] = None):
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

def get_snippet(snippet_id: int):
    conn = init_db()
    row = conn.execute("SELECT * FROM snippets WHERE id = ?", (snippet_id,)).fetchone()
    if not row:
        print("Snippet not found.")
        return
    print(f"Title: {row['title']}")
    print(f"Language: {row['language'] or 'N/A'}")
    print(f"Tags: {row['tags'] or 'N/A'}")
    print(f"\n--- Code ---\n{row['code']}")

def copy_snippet(snippet_id: int):
    """Copy a snippet's code to the system clipboard."""
    conn = init_db()
    row = conn.execute("SELECT title, code FROM snippets WHERE id = ?", (snippet_id,)).fetchone()
    if not row:
        print(f"Snippet {snippet_id} not found.")
        return

    code = row["code"]
    copied = False

    # Try pbcopy (macOS) → xclip → xsel → pyperclip in that order
    for cmd in (["pbcopy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]):
        try:
            import subprocess
            proc = subprocess.run(cmd, input=code.encode(), check=True,
                                  capture_output=True)
            copied = True
            break
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue

    if not copied:
        try:
            import pyperclip  # type: ignore
            pyperclip.copy(code)
            copied = True
        except ImportError:
            pass

    if copied:
        lines = code.count("\n") + 1
        print(f"Copied '{row['title']}' ({lines} line{'s' if lines != 1 else ''}) to clipboard.")
    else:
        # Last resort: just print the code so the user can copy manually
        print(f"Could not find a clipboard utility. Here is the code for '{row['title']}':\n")
        print(code)

def delete_snippet(snippet_id: int):
    conn = init_db()
    conn.execute("DELETE FROM snippets WHERE id = ?", (snippet_id,))
    conn.commit()
    print(f"Deleted snippet {snippet_id}")

def search_snippets(query: str, limit: int = 5):
    """Semantic search using Ollama embeddings."""
    config = load_config()
    conn = init_db()

    # Get query embedding
    print(f"Searching for: {query}")
    query_embedding = get_embedding(query, config)

    if not query_embedding:
        print("Falling back to text search...")
        # Simple text fallback
        rows = conn.execute(
            "SELECT * FROM snippets WHERE title LIKE ? OR code LIKE ? ORDER BY created_at DESC LIMIT ?",
            (f"%{query}%", f"%{query}%", limit)
        ).fetchall()
        for row in rows:
            print(f"[{row['id']}] {row['title']} (text match)")
        return

    # Search with embeddings
    import pickle
    rows = conn.execute("SELECT id, title, code, language, tags, embedding FROM snippets WHERE embedding IS NOT NULL").fetchall()

    if not rows:
        print("No snippets with embeddings. Add snippets first, or use `code-stash list` for text search.")
        return

    results = []
    for row in rows:
        if row['embedding']:
            emb = pickle.loads(row['embedding'])
            sim = cosine_similarity(query_embedding, emb)
            results.append((sim, row))

    # Sort by similarity
    results.sort(key=lambda x: x[0], reverse=True)

    print(f"\nTop {limit} results:\n")
    for score, row in results[:limit]:
        print(f"[{row['id']}] {row['title']} | similarity: {score:.3f}")
        print(f"    {row['code'][:100]}...")
        print()

def regenerate_embeddings():
    """Regenerate embeddings for all snippets."""
    config = load_config()
    conn = init_db()
    rows = conn.execute("SELECT id, title, code FROM snippets").fetchall()

    import pickle
    for row in rows:
        text = f"{row['title']}\n{row['code']}"
        emb = get_embedding(text, config)
        if emb:
            conn.execute("UPDATE snippets SET embedding = ? WHERE id = ?", (pickle.dumps(emb), row['id']))
            print(f"Indexed: {row['title']}")

    conn.commit()
    print("Done rebuilding embeddings.")

def export_snippets(filepath: str):
    conn = init_db()
    rows = conn.execute("SELECT * FROM snippets").fetchall()
    data = [dict(row) for row in rows]
    # Strip binary embedding blobs — they're not portable as JSON
    for item in data:
        item.pop("embedding", None)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    print(f"Exported {len(data)} snippets to {filepath}")

def import_snippets(filepath: str):
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

    # add
    add_parser = sub.add_parser("add", help="Add a snippet")
    add_parser.add_argument("title")
    add_parser.add_argument("--lang", "-l", help="Language")
    add_parser.add_argument("--tags", "-t", help="Tags (comma-separated)")
    add_parser.add_argument("--no-embed", action="store_true", help="Skip embedding generation")

    # list  — now supports --lang / --tag filters
    list_parser = sub.add_parser("list", help="List snippets")
    list_parser.add_argument("--lang", "-l", help="Filter by language")
    list_parser.add_argument("--tag", help="Filter by tag")

    # get
    sub.add_parser("get", help="Get snippet by ID").add_argument("id", type=int)

    # copy  — new command
    copy_parser = sub.add_parser("copy", help="Copy snippet code to clipboard")
    copy_parser.add_argument("id", type=int, help="Snippet ID to copy")

    # delete
    sub.add_parser("delete", help="Delete snippet").add_argument("id", type=int)

    # search
    search_parser = sub.add_parser("search", help="Semantic search with Ollama")
    search_parser.add_argument("query", nargs="?")
    search_parser.add_argument("--limit", "-n", type=int, default=5)

    sub.add_parser("reindex", help="Regenerate all embeddings")

    # export
    sub.add_parser("export", help="Export snippets to JSON").add_argument("filepath")

    # import
    sub.add_parser("import", help="Import snippets from JSON").add_argument("filepath")

    args = parser.parse_args()

    if args.command == "add":
        tags = args.tags.split(",") if args.tags else None
        # Read code from stdin first, then insert — avoids the stale
        # last_insert_rowid() race condition in the original implementation.
        print("Enter code (Ctrl+D / Ctrl+Z to finish):")
        try:
            code = sys.stdin.read()
        except KeyboardInterrupt:
            print("\nAborted.")
            return
        add_snippet(
            args.title,
            code,
            args.lang,
            tags,
            generate_embedding=not args.no_embed,
        )

    elif args.command == "list":
        list_snippets(language=getattr(args, "lang", None), tag=getattr(args, "tag", None))
    elif args.command == "get":
        get_snippet(args.id)
    elif args.command == "copy":
        copy_snippet(args.id)
    elif args.command == "delete":
        delete_snippet(args.id)
    elif args.command == "search":
        if not args.query:
            print("Usage: code-stash search \"your search query\"")
            return
        search_snippets(args.query, args.limit)
    elif args.command == "reindex":
        regenerate_embeddings()
    elif args.command == "export":
        export_snippets(args.filepath)
    elif args.command == "import":
        import_snippets(args.filepath)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
