# snipvault

**Encrypted, searchable code snippet manager with templates and team sync.**

Your code snippets deserve bank-grade encryption. `snipvault` stores every snippet with AES-256-GCM encryption, indexes them with SQLite FTS5 full-text search, and lets you share encrypted bundles with teammates -- all from the terminal.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

---

## Why snipvault?

- **Encrypted at rest** -- AES-256-GCM with PBKDF2 key derivation. Your snippets never touch disk unencrypted.
- **Instant search** -- SQLite FTS5 full-text search with fuzzy matching, language/tag/date filters.
- **Templates** -- Built-in templates for Dockerfiles, CI configs, FastAPI apps, and more. Define variables like `${SERVICE_NAME}` and render on the fly.
- **Clipboard integration** -- Copy snippets straight to clipboard or pipe raw content.
- **Team sharing** -- Export encrypted bundles, share the file + passphrase, teammates import in one command.
- **Zero dependencies on cloud services** -- Everything lives in a local SQLite vault.

## Quick Start

```bash
pip install snipvault

# Set your vault passphrase (or use -p flag each time)
export SNIPVAULT_PASS="my-secret-passphrase"

# Add a snippet
snipvault add -t "Python retry decorator" -l python -T "python,retry,decorator" -f retry.py

# Add from stdin
echo 'SELECT * FROM users WHERE active = true;' | snipvault add -t "Active users query" -l sql

# Search
snipvault search "retry decorator"
snipvault search "docker" --language yaml --tags ci

# Get snippet with clipboard copy
snipvault get 1 --copy

# Pipe raw content
snipvault get 1 --raw | pbcopy

# Use templates
snipvault templates  # list available templates
snipvault add --template dockerfile -v SERVICE_NAME=myapi -v PORT=3000 -t "My API Dockerfile"

# Share with teammates
snipvault share -o team-snippets.snipbundle --ids 1,2,3
snipvault import team-snippets.snipbundle --format bundle
```

## Features

### Encrypted Storage
Every snippet's content is encrypted with AES-256-GCM before writing to SQLite. Key derivation uses PBKDF2 with 480,000 iterations. Metadata (title, tags, language) is stored in plaintext for searchability.

### Full-Text Search
```bash
snipvault search "kubernetes deployment"
snipvault search "auth" --language python --tags fastapi
snipvault search "config" --from 2025-01-01 --to 2025-06-30
snipvault search "dcokr" --fuzzy  # typo-tolerant
```

### Built-in Templates
```bash
snipvault templates  # See all templates and their variables

# Render a template and save to vault
snipvault add --template fastapi \
  -v SERVICE_NAME=user-service \
  -v PORT=8080 \
  -t "User Service"
```

Available templates: `dockerfile`, `docker-compose`, `fastapi`, `github-action`, `nginx-reverse-proxy`, `systemd-service`.

### Team Sharing
```bash
# Sender: export selected snippets as encrypted bundle
snipvault share -o devops-snippets.snipbundle --ids 5,12,18

# Recipient: import the bundle
snipvault import devops-snippets.snipbundle --format bundle --bundle-pass "shared-secret"
```

### Export / Import
```bash
# JSON export (decrypted, for backup)
snipvault export -o backup.json

# JSON import
snipvault import backup.json
```

## Configuration

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `SNIPVAULT_PASS` | Vault passphrase | (prompted) |
| `SNIPVAULT_DIR` | Vault directory | `~/.snipvault` |

## Architecture

```
~/.snipvault/
  vault.db          # SQLite with FTS5, WAL mode
    snippets        # id, title, encrypted_content, language, tags, timestamps
    snippets_fts    # FTS5 virtual table for search
    metadata        # key-value store for vault settings
```

## License

MIT
