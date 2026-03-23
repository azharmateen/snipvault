"""Click CLI for snipvault: add, get, search, list, export, import, share."""

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax
from rich.panel import Panel

from .vault import Vault
from .search import search_snippets, fuzzy_search
from .templates import list_templates, render_full_template, extract_variables
from .clipboard import copy_to_clipboard, paste_to_stdout, format_snippet_for_copy
from .sharing import export_bundle, import_bundle, list_bundle_info

console = Console()

PASS_ENV = "SNIPVAULT_PASS"


def _get_passphrase(passphrase: str | None) -> str:
    """Get passphrase from option, env, or prompt."""
    import os

    if passphrase:
        return passphrase
    env_pass = os.environ.get(PASS_ENV)
    if env_pass:
        return env_pass
    return click.prompt("Vault passphrase", hide_input=True)


def _open_vault(passphrase: str | None) -> Vault:
    return Vault(_get_passphrase(passphrase))


@click.group()
@click.version_option(package_name="snipvault")
def cli():
    """snipvault - Encrypted, searchable code snippet manager."""
    pass


@cli.command()
@click.option("--title", "-t", required=True, help="Snippet title")
@click.option("--language", "-l", default="", help="Programming language")
@click.option("--tags", "-T", default="", help="Comma-separated tags")
@click.option("--file", "-f", "filepath", type=click.Path(exists=True), help="Read content from file")
@click.option("--template", "tmpl_name", help="Use a built-in template")
@click.option("--var", "-v", "variables", multiple=True, help="Template variable: KEY=VALUE")
@click.option("--passphrase", "-p", envvar=PASS_ENV, help="Vault passphrase")
def add(title, language, tags, filepath, tmpl_name, variables, passphrase):
    """Add a new snippet to the vault."""
    vault = _open_vault(passphrase)
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    if tmpl_name:
        # Template mode
        var_dict = {}
        for v in variables:
            if "=" in v:
                k, val = v.split("=", 1)
                var_dict[k] = val
        rendered = render_full_template(tmpl_name, var_dict)
        if not rendered:
            console.print(f"[red]Template '{tmpl_name}' not found.[/red]")
            console.print("Available templates: " + ", ".join(t["name"] for t in list_templates()))
            vault.close()
            sys.exit(1)
        content = rendered["content"]
        title = title or rendered["title"]
        language = language or rendered["language"]
        tag_list = tag_list or rendered["tags"]
    elif filepath:
        content = Path(filepath).read_text(encoding="utf-8")
    elif not sys.stdin.isatty():
        content = sys.stdin.read()
    else:
        content = click.edit("# Enter your snippet content here\n")
        if not content:
            console.print("[yellow]No content provided. Aborted.[/yellow]")
            vault.close()
            return

    snippet_id = vault.add(title, content, language, tag_list)
    vault.close()
    console.print(f"[green]Snippet added with ID: {snippet_id}[/green]")


@cli.command()
@click.argument("snippet_id", type=int)
@click.option("--copy", "-c", "do_copy", is_flag=True, help="Copy to clipboard")
@click.option("--raw", "-r", is_flag=True, help="Output raw content only (for piping)")
@click.option("--passphrase", "-p", envvar=PASS_ENV, help="Vault passphrase")
def get(snippet_id, do_copy, raw, passphrase):
    """Get a snippet by ID."""
    vault = _open_vault(passphrase)
    snippet = vault.get(snippet_id)
    vault.close()

    if not snippet:
        console.print(f"[red]Snippet #{snippet_id} not found.[/red]")
        sys.exit(1)

    if raw:
        paste_to_stdout(snippet["content"])
        return

    if do_copy:
        text = format_snippet_for_copy(snippet)
        if copy_to_clipboard(text):
            console.print("[green]Copied to clipboard![/green]")
        else:
            console.print("[yellow]Clipboard not available. Printing instead:[/yellow]")

    _display_snippet(snippet)


@cli.command()
@click.argument("query")
@click.option("--language", "-l", help="Filter by language")
@click.option("--tags", "-T", help="Filter by tags (comma-separated)")
@click.option("--from", "date_from", help="Date from (ISO format)")
@click.option("--to", "date_to", help="Date to (ISO format)")
@click.option("--fuzzy", is_flag=True, help="Use fuzzy matching")
@click.option("--limit", "-n", default=20, help="Max results")
@click.option("--passphrase", "-p", envvar=PASS_ENV, help="Vault passphrase")
def search(query, language, tags, date_from, date_to, fuzzy, limit, passphrase):
    """Search snippets by keyword."""
    vault = _open_vault(passphrase)
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None

    if fuzzy:
        results = fuzzy_search(vault, query, limit=limit)
    else:
        results = search_snippets(
            vault, query,
            language=language,
            tags=tag_list,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )
    vault.close()

    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return

    table = Table(title=f"Search results for '{query}'")
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("Title", style="bold")
    table.add_column("Language", style="green")
    table.add_column("Tags", style="magenta")

    for s in results:
        table.add_row(
            str(s["id"]),
            s["title"],
            s.get("language", ""),
            ", ".join(s.get("tags", [])),
        )
    console.print(table)


@cli.command("list")
@click.option("--language", "-l", help="Filter by language")
@click.option("--tag", "-T", help="Filter by tag")
@click.option("--limit", "-n", default=50, help="Max results")
@click.option("--passphrase", "-p", envvar=PASS_ENV, help="Vault passphrase")
def list_cmd(language, tag, limit, passphrase):
    """List all snippets."""
    vault = _open_vault(passphrase)
    snippets = vault.list_all(language=language, tag=tag, limit=limit)
    vault.close()

    if not snippets:
        console.print("[yellow]No snippets in vault.[/yellow]")
        return

    table = Table(title=f"Snippets ({len(snippets)})")
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("Title", style="bold")
    table.add_column("Language", style="green")
    table.add_column("Tags", style="magenta")
    table.add_column("Updated", style="dim")

    for s in snippets:
        table.add_row(
            str(s["id"]),
            s["title"],
            s["language"],
            ", ".join(s["tags"]),
            s["updated_at"][:10],
        )
    console.print(table)


@cli.command("delete")
@click.argument("snippet_id", type=int)
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.option("--passphrase", "-p", envvar=PASS_ENV, help="Vault passphrase")
def delete_cmd(snippet_id, force, passphrase):
    """Delete a snippet by ID."""
    vault = _open_vault(passphrase)

    if not force:
        snippet = vault.get(snippet_id)
        if snippet:
            console.print(f"About to delete: [bold]{snippet['title']}[/bold]")
            if not click.confirm("Are you sure?"):
                vault.close()
                return

    if vault.delete(snippet_id):
        console.print(f"[green]Snippet #{snippet_id} deleted.[/green]")
    else:
        console.print(f"[red]Snippet #{snippet_id} not found.[/red]")
    vault.close()


@cli.command("export")
@click.option("--output", "-o", default="snippets.json", help="Output file path")
@click.option("--format", "fmt", type=click.Choice(["json", "bundle"]), default="json")
@click.option("--bundle-pass", help="Passphrase for encrypted bundle")
@click.option("--ids", help="Comma-separated snippet IDs to export")
@click.option("--passphrase", "-p", envvar=PASS_ENV, help="Vault passphrase")
def export_cmd(output, fmt, bundle_pass, ids, passphrase):
    """Export snippets to JSON or encrypted bundle."""
    vault = _open_vault(passphrase)
    id_list = [int(i.strip()) for i in ids.split(",") if i.strip()] if ids else None

    if fmt == "bundle":
        bp = bundle_pass or click.prompt("Bundle passphrase", hide_input=True)
        result = export_bundle(vault, output, bp, snippet_ids=id_list)
        console.print(f"[green]Exported {result['count']} snippets to {result['path']}[/green]")
    else:
        if id_list:
            snippets = [vault.get(i) for i in id_list if vault.get(i)]
        else:
            snippets = vault.export_all()
        with open(output, "w", encoding="utf-8") as f:
            json.dump(snippets, f, indent=2, ensure_ascii=False)
        console.print(f"[green]Exported {len(snippets)} snippets to {output}[/green]")

    vault.close()


@cli.command("import")
@click.argument("filepath", type=click.Path(exists=True))
@click.option("--format", "fmt", type=click.Choice(["json", "bundle"]), default="json")
@click.option("--bundle-pass", help="Passphrase for encrypted bundle")
@click.option("--passphrase", "-p", envvar=PASS_ENV, help="Vault passphrase")
def import_cmd(filepath, fmt, bundle_pass, passphrase):
    """Import snippets from JSON or encrypted bundle."""
    vault = _open_vault(passphrase)

    if fmt == "bundle":
        bp = bundle_pass or click.prompt("Bundle passphrase", hide_input=True)
        result = import_bundle(vault, filepath, bp)
        console.print(f"[green]Imported {result['count']} snippets from bundle[/green]")
    else:
        with open(filepath, "r", encoding="utf-8") as f:
            snippets = json.load(f)
        count = vault.import_snippets(snippets)
        console.print(f"[green]Imported {count} snippets from {filepath}[/green]")

    vault.close()


@cli.command()
@click.option("--output", "-o", required=True, help="Output bundle path")
@click.option("--ids", help="Comma-separated snippet IDs to share")
@click.option("--passphrase", "-p", envvar=PASS_ENV, help="Vault passphrase")
def share(output, ids, passphrase):
    """Create an encrypted bundle to share with teammates."""
    vault = _open_vault(passphrase)
    bundle_pass = click.prompt("Set bundle passphrase (share this with recipient)", hide_input=True, confirmation_prompt=True)
    id_list = [int(i.strip()) for i in ids.split(",") if i.strip()] if ids else None

    result = export_bundle(vault, output, bundle_pass, snippet_ids=id_list)
    vault.close()

    console.print(f"[green]Shared {result['count']} snippets -> {result['path']}[/green]")
    console.print("[dim]Send this file and the passphrase to your teammate.[/dim]")
    console.print(f"[dim]They can import with: snipvault import {output} --format bundle[/dim]")


@cli.command("templates")
def templates_cmd():
    """List available snippet templates."""
    templates = list_templates()
    table = Table(title="Available Templates")
    table.add_column("Name", style="cyan")
    table.add_column("Language", style="green")
    table.add_column("Variables", style="yellow")
    table.add_column("Tags", style="magenta")

    for t in templates:
        table.add_row(
            t["name"],
            t["language"],
            ", ".join(t["variables"]),
            ", ".join(t["tags"]),
        )
    console.print(table)
    console.print("\n[dim]Use: snipvault add --template <name> -v KEY=VALUE[/dim]")


def _display_snippet(snippet: dict) -> None:
    """Pretty-print a snippet."""
    lang = snippet.get("language", "") or "text"
    tags = ", ".join(snippet.get("tags", []))
    header = f"[cyan]#{snippet['id']}[/cyan] [bold]{snippet['title']}[/bold]"
    if tags:
        header += f"  [magenta][{tags}][/magenta]"

    console.print(header)
    console.print(f"[dim]Language: {lang} | Created: {snippet['created_at'][:10]} | Updated: {snippet['updated_at'][:10]}[/dim]")
    console.print()
    syntax = Syntax(snippet["content"], lang, theme="monokai", line_numbers=True)
    console.print(syntax)


if __name__ == "__main__":
    cli()
