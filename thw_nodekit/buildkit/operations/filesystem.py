"""Filesystem operations for build processes."""

import logging
import os
import shutil
from pathlib import Path
from .commands import run_command_check, CommandError

logger = logging.getLogger(__name__)

def ensure_directory_exists(dir_path: str) -> None:
    """Ensures that a directory exists, creating it if necessary."""
    path = Path(dir_path)
    if not path.exists():
        logger.info(f"Creating directory: {dir_path}")
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create directory {dir_path}: {e}")
            raise
    elif not path.is_dir():
        logger.error(f"Path exists but is not a directory: {dir_path}")
        raise FileExistsError(f"Path exists but is not a directory: {dir_path}")

def remove_directory(dir_path: str) -> None:
    """Removes a directory and its contents recursively."""
    path = Path(dir_path)
    if path.exists() and path.is_dir():
        logger.warning(f"Removing directory: {dir_path}")
        try:
            shutil.rmtree(dir_path)
            logger.info(f"Successfully removed directory: {dir_path}")
        except OSError as e:
            logger.error(f"Failed to remove directory {dir_path}: {e}")
            raise
    elif path.exists():
        logger.error(f"Path exists but is not a directory, cannot remove: {dir_path}")
        raise NotADirectoryError(f"Path exists but is not a directory: {dir_path}")
    else:
        logger.info(f"Directory does not exist, skipping removal: {dir_path}")

def create_symlink(
    target: str,
    link_path: str,
    force: bool = True,
    no_dereference: bool = True,
    symbolic: bool = True
) -> None:
    """Creates a symlink using ln, mirroring script options.

    Args:
        target: The path the symlink should point to.
        link_path: The path where the symlink will be created.
        force: Corresponds to `ln --force`. Removes existing destination files.
        no_dereference: Corresponds to `ln --no-dereference`. Treat LINK_NAME as a normal file if it is a symbolic link to a directory.
        symbolic: Corresponds to `ln --symbolic`. Make symbolic links instead of hard links.
    """
    # Ensure the directory for the link exists
    link_parent_dir = Path(link_path).parent
    ensure_directory_exists(str(link_parent_dir))

    command = ["ln"]
    if force:
        command.append("--force")
    if no_dereference:
        command.append("--no-dereference")
    if symbolic:
        command.append("--symbolic")

    command.extend([target, link_path])

    logger.info(f"Creating symlink: {link_path} -> {target}")
    try:
        run_command_check(command)
        logger.info("Successfully created symlink.")
    except CommandError as e:
        logger.error(f"Failed to create symlink: {e}")
        raise

# --- Keep other potentially useful filesystem functions ---