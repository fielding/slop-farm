"""CLI interface for slop-farm — persistent agent task management."""

import argparse
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from rich.console import Console
from rich.table import Table

console = Console()

STATE_FILE = Path(os.environ.get("SLOP_STATE", str(Path.home() / ".slop-farm" / "tasks.json")))

def load_state() -> dict:
    """Load task state from JSON file."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    return {"tasks": [], "version": 1}

def save_state(state: dict) -> None:
    """Persist task state to JSON file."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))

def cmd_status():
    """Show farm status reading from real state."""
    state = load_state()
    tasks = state.get("tasks", [])
    pending = [t for t in tasks if t["status"] == "pending"]
    done = [t for t in tasks if t["status"] == "done"]

    table = Table(title="🌱 slop-farm Status")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Tasks pending", str(len(pending)))
    table.add_row("Tasks done", str(len(done)))
    table.add_row("State file", str(STATE_FILE))
    console.print(table)

    if pending:
        console.print("\n[bold]Pending tasks:[/bold]")
        for t in pending[:10]:
            console.print(f"  [yellow]●[/yellow] {t['id'][:8]} — {t['description'][:60]} ({t['created_at'][:10]})")

def cmd_plant(task_desc: str):
    """Plant a new task — persists to state."""
    state = load_state()
    task = {
        "id": str(uuid.uuid4()),
        "description": task_desc,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    state["tasks"].append(task)
    save_state(state)
    console.print(f"[green]🌱 Planted:[/green] {task['id'][:8]} — {task_desc}")

def cmd_harvest():
    """Harvest completed tasks — reads from state."""
    state = load_state()
    done = [t for t in state["tasks"] if t["status"] == "done"]
    pending = [t for t in state["tasks"] if t["status"] == "pending"]

    if not pending and not done:
        console.print("[dim]No tasks in the farm yet. Plant one with: slop plant <task>[/dim]")
        return

    if not done:
        console.print(f"[yellow]🌾 {len(pending)} tasks pending, none ready to harvest.[/yellow]")
        return

    console.print(f"[green]🌾 Harvesting {len(done)} completed task(s):[/green]")
    for t in done:
        console.print(f"  ✓ {t['id'][:8]} — {t['description'][:60]}")
        t["status"] = "archived"

    # Clean archived from active list after harvest
    state["tasks"] = [t for t in state["tasks"] if t["status"] != "archived"]
    save_state(state)

def cmd_done(task_id: str):
    """Mark a task as done."""
    state = load_state()
    for t in state["tasks"]:
        if t["id"].startswith(task_id):
            t["status"] = "done"
            save_state(state)
            console.print(f"[green]✓ Task {task_id} marked as done[/green]")
            return
    console.print(f"[red]Task {task_id} not found[/red]")

def cmd_list():
    """List all tasks."""
    state = load_state()
    tasks = state.get("tasks", [])
    if not tasks:
        console.print("[dim]No tasks yet.[/dim]")
        return
    table = Table(title="📋 Tasks")
    table.add_column("ID", style="dim")
    table.add_column("Status")
    table.add_column("Description")
    table.add_column("Created")
    for t in tasks:
        icon = "⏳" if t["status"] == "pending" else "✓"
        color = "yellow" if t["status"] == "pending" else "green"
        table.add_row(t["id"][:8], f"[{color}]{icon} {t['status']}[/{color}]", 
                      t["description"][:50], t["created_at"][:10])
    console.print(table)

def main():
    parser = argparse.ArgumentParser(description="slop-farm — agent-governed task farming")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="Show farm status")
    
    plant = sub.add_parser("plant", help="Plant a new task")
    plant.add_argument("task", help="Task description")
    
    sub.add_parser("harvest", help="Harvest completed tasks")
    sub.add_parser("list", help="List all tasks")

    done = sub.add_parser("done", help="Mark task as done")
    done.add_argument("task_id", help="Task ID (first 8 chars enough)")

    args = parser.parse_args()
    
    if args.command == "status":
        cmd_status()
    elif args.command == "plant":
        cmd_plant(args.task)
    elif args.command == "harvest":
        cmd_harvest()
    elif args.command == "list":
        cmd_list()
    elif args.command == "done":
        cmd_done(args.task_id)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
