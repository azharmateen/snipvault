"""Snippet templates with variable substitution."""

import re
from typing import Optional


# Built-in templates
BUILTIN_TEMPLATES = {
    "dockerfile": {
        "title": "Dockerfile - ${SERVICE_NAME}",
        "language": "dockerfile",
        "tags": ["docker", "container"],
        "content": """FROM python:${PYTHON_VERSION:-3.12}-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE ${PORT:-8000}

CMD ["python", "-m", "uvicorn", "${SERVICE_NAME}.main:app", "--host", "0.0.0.0", "--port", "${PORT:-8000}"]
""",
    },
    "docker-compose": {
        "title": "docker-compose.yml - ${PROJECT_NAME}",
        "language": "yaml",
        "tags": ["docker", "compose"],
        "content": """version: '3.8'

services:
  ${SERVICE_NAME}:
    build: .
    ports:
      - "${PORT:-8000}:${PORT:-8000}"
    environment:
      DATABASE_URL: ${DB_URL:-postgresql://postgres:postgres@db:5432/${SERVICE_NAME}}
    depends_on:
      - db

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${SERVICE_NAME}
      POSTGRES_PASSWORD: postgres
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
""",
    },
    "fastapi": {
        "title": "FastAPI app - ${SERVICE_NAME}",
        "language": "python",
        "tags": ["python", "fastapi", "api"],
        "content": """from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="${SERVICE_NAME}", version="0.1.0")


class HealthResponse(BaseModel):
    status: str
    service: str


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", service="${SERVICE_NAME}")


@app.get("/")
async def root():
    return {"message": "Welcome to ${SERVICE_NAME}"}
""",
    },
    "github-action": {
        "title": "GitHub Action - ${WORKFLOW_NAME}",
        "language": "yaml",
        "tags": ["ci", "github", "actions"],
        "content": """name: ${WORKFLOW_NAME}

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  ${JOB_NAME:-build}:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '${PYTHON_VERSION:-3.12}'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt

      - name: Run tests
        run: |
          pytest -v
""",
    },
    "nginx-reverse-proxy": {
        "title": "Nginx reverse proxy - ${SERVICE_NAME}",
        "language": "nginx",
        "tags": ["nginx", "reverse-proxy"],
        "content": """server {
    listen 80;
    server_name ${DOMAIN};

    location / {
        proxy_pass http://127.0.0.1:${PORT:-8000};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
""",
    },
    "systemd-service": {
        "title": "Systemd service - ${SERVICE_NAME}",
        "language": "ini",
        "tags": ["systemd", "linux", "service"],
        "content": """[Unit]
Description=${SERVICE_NAME}
After=network.target

[Service]
Type=simple
User=${USER:-www-data}
WorkingDirectory=${WORK_DIR:-/opt/${SERVICE_NAME}}
ExecStart=${EXEC_CMD:-/usr/bin/python3 -m ${SERVICE_NAME}}
Restart=always
RestartSec=5
Environment=PORT=${PORT:-8000}

[Install]
WantedBy=multi-user.target
""",
    },
}


# Pattern: ${VAR_NAME} or ${VAR_NAME:-default_value}
_VAR_PATTERN = re.compile(r"\$\{(\w+)(?::-([^}]*))?\}")


def render_template(template_content: str, variables: dict[str, str]) -> str:
    """Render a template by substituting ${VAR} and ${VAR:-default} patterns.

    Args:
        template_content: String with ${VAR} placeholders
        variables: Dict of variable name -> value

    Returns:
        Rendered string with all variables substituted
    """

    def _replace(match: re.Match) -> str:
        var_name = match.group(1)
        default = match.group(2)
        value = variables.get(var_name)
        if value is not None:
            return value
        if default is not None:
            return default
        return match.group(0)  # Leave unresolved vars as-is

    return _VAR_PATTERN.sub(_replace, template_content)


def list_templates() -> list[dict]:
    """List all built-in templates with their metadata."""
    result = []
    for name, tmpl in BUILTIN_TEMPLATES.items():
        variables = extract_variables(tmpl["content"])
        # Also check title for variables
        variables.update(extract_variables(tmpl["title"]))
        result.append(
            {
                "name": name,
                "title": tmpl["title"],
                "language": tmpl["language"],
                "tags": tmpl["tags"],
                "variables": sorted(variables),
            }
        )
    return result


def extract_variables(content: str) -> set[str]:
    """Extract variable names from template content."""
    return {m.group(1) for m in _VAR_PATTERN.finditer(content)}


def get_template(name: str) -> Optional[dict]:
    """Get a template by name."""
    return BUILTIN_TEMPLATES.get(name)


def render_full_template(
    name: str, variables: dict[str, str]
) -> Optional[dict]:
    """Render a full template (title + content) with variables.

    Returns dict with rendered title, content, language, tags or None if not found.
    """
    tmpl = get_template(name)
    if not tmpl:
        return None
    return {
        "title": render_template(tmpl["title"], variables),
        "content": render_template(tmpl["content"], variables),
        "language": tmpl["language"],
        "tags": tmpl["tags"],
    }
