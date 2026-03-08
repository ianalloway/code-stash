# Code Stash

A CLI code snippet manager with local Ollama-powered search.

## Install

```bash
pip install -e .
```

## Usage

```bash
# Add a snippet
code-stash add "my useful function" --lang python --tags "utils,api"

# List snippets
code-stash list
code-stash list --lang python
code-stash list --tag utils

# Search (uses Ollama if available, falls back to text search)
code-stash search "authentication handler"

# Get snippet by ID
code-stash get 1

# Delete
code-stash delete 1

# Export/Import
code-stash export backup.json
code-stash import backup.json
```

## Config

Config lives in `~/.code-stash/config.yaml`:

```yaml
ollama_url: "http://localhost:11434"
ollama_model: "llama3.3"
db_path: "~/.code-stash/snippets.db"
```
