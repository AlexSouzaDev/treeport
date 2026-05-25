"""
Logging and terminal output for treeport runs.

Supports:
  - File logging (default, auto-generated path)
  - Stdout with Rich panels/spinners
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import print as rprint


class RunLogger:
    """Unified logger for a single treeport run."""

    def __init__(
        self,
        *,
        log_to_stdout: bool = False,
        log_file: Path | None = None,
        run_name: str | None = None,
    ) -> None:
        self.run_name = run_name or "treeport"
        self.log_to_stdout = log_to_stdout
        self.log_file = log_file
        self._console = Console(stderr=False)
        self._file_handle = None

        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            self._file_handle = log_file.open("w", encoding="utf-8")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        ts = datetime.now().isoformat(timespec="seconds")
        self._write_header(f"[{self.run_name}] Starting run at {ts}")

    def iteration_start(self, iteration: int, max_iterations: int) -> None:
        self._write(
            f"[{self.run_name}] Iteration {iteration}/{max_iterations} starting…",
            style="bold cyan",
        )

    def iteration_end(
        self, iteration: int, signal_detected: bool, stdout: str
    ) -> None:
        status = "✓ completion signal detected" if signal_detected else "→ continuing"
        self._write(
            f"[{self.run_name}] Iteration {iteration} done — {status}",
            style="bold green" if signal_detected else "yellow",
        )
        if self._file_handle:
            self._file_handle.write(f"\n--- ITERATION {iteration} OUTPUT ---\n")
            self._file_handle.write(stdout)
            self._file_handle.flush()

    def agent_output(self, text: str) -> None:
        if self.log_to_stdout:
            self._console.print(text, end="")
        if self._file_handle:
            self._file_handle.write(text)
            self._file_handle.flush()

    def commits_found(self, commits: list[dict[str, str]]) -> None:
        if not commits:
            self._write(f"[{self.run_name}] No new commits.", style="dim")
            return
        shas = ", ".join(c["sha"][:8] for c in commits)
        self._write(
            f"[{self.run_name}] {len(commits)} commit(s): {shas}",
            style="bold green",
        )

    def finish(self, branch: str, log_file_path: Path | None) -> None:
        msg = f"[{self.run_name}] Run complete → branch: {branch}"
        if log_file_path:
            msg += f" | log: {log_file_path}"
        self._write(msg, style="bold magenta")
        self._close()

    def error(self, message: str) -> None:
        self._write(f"[{self.run_name}] ERROR: {message}", style="bold red")
        self._close()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _write(self, message: str, style: str = "") -> None:
        if self.log_to_stdout:
            self._console.print(message, style=style)
        if self._file_handle:
            self._file_handle.write(message + "\n")
            self._file_handle.flush()

    def _write_header(self, message: str) -> None:
        if self.log_to_stdout:
            self._console.print(
                Panel(Text(message, style="bold white"), style="blue")
            )
        if self._file_handle:
            self._file_handle.write(f"{'='*60}\n{message}\n{'='*60}\n")
            self._file_handle.flush()

    def _close(self) -> None:
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None


def make_logger(
    log_type: str,
    log_file_path: str | Path | None,
    run_name: str | None,
    repo_root: Path,
) -> tuple[RunLogger, Path | None]:
    """Factory: returns (logger, resolved_log_file_path)."""
    if log_type == "stdout":
        return RunLogger(log_to_stdout=True, run_name=run_name), None

    # File logging
    if log_file_path:
        resolved = Path(log_file_path)
    else:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        slug = run_name or "run"
        resolved = repo_root / ".treeport" / "logs" / f"{slug}-{ts}.log"

    logger = RunLogger(log_file=resolved, run_name=run_name)
    return logger, resolved
