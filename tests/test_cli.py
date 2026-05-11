"""Tests for slop-farm CLI with real state assertions."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

CLI = [sys.executable, "-m", "slop_farm.cli"]


def run_slop(*args, env=None):
    return subprocess.run([*CLI, *args], capture_output=True, text=True, env=env)


def test_import():
    from slop_farm import __version__
    assert __version__ == "0.1.0"


def test_status_empty():
    result = run_slop("status")
    assert result.returncode == 0


def test_plant_creates_state_file():
    with tempfile.TemporaryDirectory() as tmp:
        state_file = Path(tmp) / "tasks.json"
        env = {**__import__("os").environ, "SLOP_STATE": str(state_file)}
        
        result = run_slop("plant", "test task", env=env)
        assert result.returncode == 0
        assert "test task" in result.stdout
        assert state_file.exists()
        
        data = json.loads(state_file.read_text())
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["description"] == "test task"
        assert data["tasks"][0]["status"] == "pending"
        assert "id" in data["tasks"][0]
        assert "created_at" in data["tasks"][0]


def test_status_shows_task():
    with tempfile.TemporaryDirectory() as tmp:
        state_file = Path(tmp) / "tasks.json"
        env = {**__import__("os").environ, "SLOP_STATE": str(state_file)}
        
        run_slop("plant", "my important task", env=env)
        result = run_slop("status", env=env)
        assert result.returncode == 0
        assert "my important task" in result.stdout
        assert "Tasks pending" in result.stdout


def test_done_marks_task():
    with tempfile.TemporaryDirectory() as tmp:
        state_file = Path(tmp) / "tasks.json"
        env = {**__import__("os").environ, "SLOP_STATE": str(state_file)}
        
        plant = run_slop("plant", "do this thing", env=env)
        data = json.loads(state_file.read_text())
        task_id = data["tasks"][0]["id"][:8]
        
        result = run_slop("done", task_id, env=env)
        assert result.returncode == 0
        
        data = json.loads(state_file.read_text())
        assert data["tasks"][0]["status"] == "done"


def test_harvest_archives_done_tasks():
    with tempfile.TemporaryDirectory() as tmp:
        state_file = Path(tmp) / "tasks.json"
        env = {**__import__("os").environ, "SLOP_STATE": str(state_file)}
        
        run_slop("plant", "task one", env=env)
        run_slop("plant", "task two", env=env)
        data = json.loads(state_file.read_text())
        tid = data["tasks"][0]["id"][:8]
        run_slop("done", tid, env=env)
        
        result = run_slop("harvest", env=env)
        assert result.returncode == 0
        
        data = json.loads(state_file.read_text())
        assert len(data["tasks"]) == 1  # done+archived removed, pending stays
        assert data["tasks"][0]["status"] == "pending"


def test_list_shows_tasks():
    with tempfile.TemporaryDirectory() as tmp:
        state_file = Path(tmp) / "tasks.json"
        env = {**__import__("os").environ, "SLOP_STATE": str(state_file)}
        
        run_slop("plant", "alpha", env=env)
        run_slop("plant", "beta", env=env)
        result = run_slop("list", env=env)
        assert result.returncode == 0
        assert "alpha" in result.stdout
        assert "beta" in result.stdout


def test_plant_with_special_chars():
    with tempfile.TemporaryDirectory() as tmp:
        state_file = Path(tmp) / "tasks.json"
        env = {**__import__("os").environ, "SLOP_STATE": str(state_file)}
        
        result = run_slop("plant", "task with 'quotes' and \"double\"", env=env)
        assert result.returncode == 0
        data = json.loads(state_file.read_text())
        assert "quotes" in data["tasks"][0]["description"]


def test_empty_harvest():
    with tempfile.TemporaryDirectory() as tmp:
        state_file = Path(tmp) / "tasks.json"
        env = {**__import__("os").environ, "SLOP_STATE": str(state_file)}
        
        result = run_slop("harvest", env=env)
        assert result.returncode == 0

