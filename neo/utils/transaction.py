"""Transaction system for atomic file operations."""

from __future__ import annotations

import difflib
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from neo.logger import get_logger

logger = get_logger(__name__)


@dataclass
class FileChange:
    """A single file change operation."""

    operation: str  # write, edit, delete, mkdir
    file_path: Path
    original_content: str | None = None
    new_content: str | None = None
    old_string: str | None = None  # For edit operation
    applied: bool = False
    backed_up: bool = False
    backup_path: Path | None = None

    def __post_init__(self) -> None:
        """Normalize paths."""
        self.file_path = Path(self.file_path)
        if self.backup_path:
            self.backup_path = Path(self.backup_path)


@dataclass
class TransactionResult:
    """Result of a transaction."""

    success: bool
    changes_applied: int = 0
    changes_reverted: int = 0
    error: str | None = None
    applied_changes: list[FileChange] = field(default_factory=list)
    failed_changes: list[tuple[FileChange, str]] = field(default_factory=list)


class FileTransaction:
    """Atomic transaction for file operations.

    Supports:
    - Multiple file operations in a single transaction
    - Automatic backup before changes
    - Rollback on failure
    - Preview changes before applying
    - Batch apply/revert
    """

    BACKUP_SUFFIX = ".neo.bak"
    TEMP_SUFFIX = ".neo.tmp"

    def __init__(self, project_path: Path):
        """Initialize transaction.

        Args:
            project_path: Root path of the project
        """
        self.project_path = Path(project_path)
        self.changes: list[FileChange] = []
        self.applied: bool = False
        self._temp_dir: Path | None = None

    def __enter__(self) -> FileTransaction:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Context manager exit - rollback on exception."""
        if exc_type and self.changes:
            logger.warning(f"Exception occurred, rolling back: {exc_val}")
            self.rollback()
        return False

    def write_file(self, file_path: str | Path, content: str) -> None:
        """Queue a file write operation.

        Args:
            file_path: Path to file
            content: Content to write
        """
        path = self.project_path / file_path
        original = None

        # Read original content if file exists
        if path.exists():
            try:
                original = path.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning(f"Could not read original file: {e}")

        change = FileChange(
            operation="write",
            file_path=path,
            original_content=original,
            new_content=content,
        )
        self.changes.append(change)

    def edit_file(
        self,
        file_path: str | Path,
        old_string: str,
        new_string: str,
    ) -> None:
        """Queue a file edit operation.

        Args:
            file_path: Path to file
            old_string: String to replace
            new_string: Replacement string
        """
        path = self.project_path / file_path

        # Read current content
        try:
            original = path.read_text(encoding="utf-8")
        except Exception as e:
            raise ValueError(f"Cannot read file {path}: {e}")

        if old_string not in original:
            raise ValueError(f"String not found in file: {old_string[:50]}...")

        new_content = original.replace(old_string, new_string, 1)

        change = FileChange(
            operation="edit",
            file_path=path,
            original_content=original,
            new_content=new_content,
            old_string=old_string,
        )
        self.changes.append(change)

    def delete_file(self, file_path: str | Path) -> None:
        """Queue a file delete operation.

        Args:
            file_path: Path to file
        """
        path = self.project_path / file_path

        # Read original content for backup
        original = None
        if path.exists():
            try:
                original = path.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning(f"Could not read file for backup: {e}")

        change = FileChange(
            operation="delete",
            file_path=path,
            original_content=original,
        )
        self.changes.append(change)

    def mkdir(self, dir_path: str | Path) -> None:
        """Queue a directory creation.

        Args:
            dir_path: Path to directory
        """
        path = self.project_path / dir_path
        change = FileChange(
            operation="mkdir",
            file_path=path,
        )
        self.changes.append(change)

    def preview_changes(self) -> str:
        """Generate a preview of all changes.

        Returns:
            Unified diff string
        """
        lines = ["## Transaction Preview\n", f"Total changes: {len(self.changes)}\n"]

        for i, change in enumerate(self.changes, 1):
            lines.append(f"\n### Change {i}: {change.operation}\n")
            lines.append(f"File: {change.file_path}\n")

            if change.operation in ("write", "edit"):
                # Generate diff
                if change.original_content is not None:
                    original_lines = change.original_content.splitlines(keepends=True)
                    if not original_lines[-1].endswith("\n"):
                        original_lines[-1] += "\n"
                else:
                    original_lines = []

                new_lines = change.new_content.splitlines(keepends=True) if change.new_content else []
                if new_lines and not new_lines[-1].endswith("\n"):
                    new_lines[-1] += "\n"

                diff = difflib.unified_diff(
                    original_lines,
                    new_lines,
                    fromfile=f"a/{change.file_path.name}",
                    tofile=f"b/{change.file_path.name}",
                )
                diff_text = "".join(diff)
                if diff_text:
                    lines.append("```diff\n")
                    lines.append(diff_text)
                    lines.append("```\n")
                else:
                    lines.append("(no changes)\n")

            elif change.operation == "delete":
                lines.append("```diff\n")
                lines.append(f"--- a/{change.file_path.name}\n")
                lines.append(f"+++ /dev/null\n")
                lines.append("@@ -1,0 +0,0 @@\n")
                lines.append("(file deleted)\n")
                lines.append("```\n")

            elif change.operation == "mkdir":
                lines.append(f"Create directory: {change.file_path}\n")

        return "".join(lines)

    def apply(self, dry_run: bool = False) -> TransactionResult:
        """Apply all changes in the transaction.

        Args:
            dry_run: If True, only validate without applying

        Returns:
            TransactionResult
        """
        if not self.changes:
            return TransactionResult(success=True, changes_applied=0)

        if self.applied:
            return TransactionResult(
                success=False,
                error="Transaction already applied",
            )

        applied: list[FileChange] = []
        failed: list[tuple[FileChange, str]] = []

        try:
            for change in self.changes:
                if dry_run:
                    # Just validate
                    if not self._validate_change(change):
                        failed.append((change, "Validation failed"))
                        continue
                else:
                    # Apply the change
                    success, error = self._apply_change(change)
                    if success:
                        applied.append(change)
                    else:
                        failed.append((change, error or "Unknown error"))
                        # Rollback on first failure
                        break

        except Exception as e:
            logger.exception("Error applying transaction")
            failed.append((self.changes[len(applied)], str(e)))

        # Handle failures
        if failed:
            # Rollback applied changes
            for change in reversed(applied):
                self._revert_change(change)

            return TransactionResult(
                success=False,
                error=f"Failed at change {len(applied) + 1}: {failed[0][1]}",
                failed_changes=failed,
            )

        self.applied = not dry_run

        return TransactionResult(
            success=True,
            changes_applied=len(applied),
            applied_changes=applied,
        )

    def _validate_change(self, change: FileChange) -> bool:
        """Validate a change without applying it.

        Args:
            change: Change to validate

        Returns:
            True if valid
        """
        if change.operation == "edit":
            if not change.file_path.exists():
                return False
            try:
                content = change.file_path.read_text(encoding="utf-8")
                if change.old_string not in content:
                    return False
            except Exception:
                return False
        return True

    def _apply_change(self, change: FileChange) -> tuple[bool, str | None]:
        """Apply a single change.

        Args:
            change: Change to apply

        Returns:
            (success, error_message)
        """
        try:
            if change.operation == "write":
                return self._apply_write(change)
            elif change.operation == "edit":
                return self._apply_edit(change)
            elif change.operation == "delete":
                return self._apply_delete(change)
            elif change.operation == "mkdir":
                return self._apply_mkdir(change)
            else:
                return False, f"Unknown operation: {change.operation}"
        except Exception as e:
            return False, str(e)

    def _apply_write(self, change: FileChange) -> tuple[bool, str | None]:
        """Apply a write operation."""
        # Create backup if file exists
        if change.file_path.exists():
            self._create_backup(change)

        # Ensure parent directory exists
        change.file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write atomically
        temp_path = change.file_path.with_suffix(self.TEMP_SUFFIX)
        try:
            temp_path.write_text(change.new_content or "", encoding="utf-8")
            temp_path.replace(change.file_path)
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise

        change.applied = True
        return True, None

    def _apply_edit(self, change: FileChange) -> tuple[bool, str | None]:
        """Apply an edit operation."""
        # Create backup
        self._create_backup(change)

        # Apply edit
        content = change.file_path.read_text(encoding="utf-8")
        if change.old_string not in content:
            return False, f"Old string not found in {change.file_path}"

        new_content = content.replace(change.old_string, change.new_content or "", 1)

        # Write atomically
        temp_path = change.file_path.with_suffix(self.TEMP_SUFFIX)
        try:
            temp_path.write_text(new_content, encoding="utf-8")
            temp_path.replace(change.file_path)
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise

        change.applied = True
        return True, None

    def _apply_delete(self, change: FileChange) -> tuple[bool, str | None]:
        """Apply a delete operation."""
        # Create backup
        self._create_backup(change)

        # Delete file
        change.file_path.unlink()

        change.applied = True
        return True, None

    def _apply_mkdir(self, change: FileChange) -> tuple[bool, str | None]:
        """Apply a mkdir operation."""
        change.file_path.mkdir(parents=True, exist_ok=True)
        change.applied = True
        return True, None

    def _create_backup(self, change: FileChange) -> None:
        """Create a backup of the original file."""
        if not change.file_path.exists():
            return

        backup_path = change.file_path.with_suffix(
            change.file_path.suffix + self.BACKUP_SUFFIX
        )

        try:
            shutil.copy2(change.file_path, backup_path)
            change.backup_path = backup_path
            change.backed_up = True
        except Exception as e:
            logger.warning(f"Failed to create backup: {e}")

    def _revert_change(self, change: FileChange) -> None:
        """Revert a single change."""
        try:
            if change.operation in ("write", "edit"):
                if change.backed_up and change.backup_path:
                    # Restore from backup
                    change.backup_path.replace(change.file_path)
                elif change.original_content is not None:
                    # Restore from memory
                    change.file_path.write_text(change.original_content, encoding="utf-8")
                else:
                    # Delete the file we created
                    if change.file_path.exists():
                        change.file_path.unlink()

            elif change.operation == "delete":
                if change.backed_up and change.backup_path:
                    # Restore from backup
                    change.backup_path.rename(change.file_path)

            elif change.operation == "mkdir":
                # Try to remove directory if empty
                try:
                    change.file_path.rmdir()
                except OSError:
                    pass  # Directory not empty or other error

            change.applied = False

        except Exception as e:
            logger.error(f"Failed to revert change: {e}")

    def rollback(self) -> TransactionResult:
        """Rollback all applied changes.

        Returns:
            TransactionResult
        """
        if not self.applied:
            return TransactionResult(
                success=False,
                error="Transaction not applied",
            )

        reverted = 0
        failed = []

        for change in reversed(self.changes):
            try:
                self._revert_change(change)
                reverted += 1
            except Exception as e:
                failed.append((change, str(e)))

        self.applied = False

        return TransactionResult(
            success=len(failed) == 0,
            changes_reverted=reverted,
            error="Some changes failed to revert" if failed else None,
            failed_changes=failed,
        )

    def cleanup_backups(self) -> None:
        """Clean up backup files."""
        for change in self.changes:
            if change.backup_path and change.backup_path.exists():
                try:
                    change.backup_path.unlink()
                except Exception as e:
                    logger.warning(f"Failed to remove backup: {e}")


class TransactionManager:
    """Manager for multiple transactions with undo/redo support."""

    def __init__(self, project_path: Path):
        """Initialize transaction manager.

        Args:
            project_path: Root path of the project
        """
        self.project_path = Path(project_path)
        self._undo_stack: list[FileTransaction] = []
        self._redo_stack: list[FileTransaction] = []
        self._max_history = 20

    def new_transaction(self) -> FileTransaction:
        """Create a new transaction.

        Returns:
            New FileTransaction
        """
        return FileTransaction(self.project_path)

    def execute(self, transaction: FileTransaction, dry_run: bool = False) -> TransactionResult:
        """Execute a transaction and add to history.

        Args:
            transaction: Transaction to execute
            dry_run: If True, only validate

        Returns:
            TransactionResult
        """
        result = transaction.apply(dry_run=dry_run)

        if result.success and not dry_run:
            self._undo_stack.append(transaction)
            self._redo_stack.clear()

            # Trim history if needed
            if len(self._undo_stack) > self._max_history:
                old = self._undo_stack.pop(0)
                old.cleanup_backups()

        return result

    def undo(self) -> TransactionResult | None:
        """Undo the last transaction.

        Returns:
            TransactionResult or None if nothing to undo
        """
        if not self._undo_stack:
            return None

        transaction = self._undo_stack.pop()
        result = transaction.rollback()

        if result.success:
            self._redo_stack.append(transaction)

        return result

    def redo(self) -> TransactionResult | None:
        """Redo the last undone transaction.

        Returns:
            TransactionResult or None if nothing to redo
        """
        if not self._redo_stack:
            return None

        transaction = self._redo_stack.pop()
        result = transaction.apply()

        if result.success:
            self._undo_stack.append(transaction)

        return result

    def can_undo(self) -> bool:
        """Check if undo is available."""
        return len(self._undo_stack) > 0

    def can_redo(self) -> bool:
        """Check if redo is available."""
        return len(self._redo_stack) > 0

    def get_undo_summary(self) -> list[str]:
        """Get summary of undoable transactions."""
        return [
            f"{i+1}. {len(t.changes)} changes"
            for i, t in enumerate(reversed(self._undo_stack))
        ]
