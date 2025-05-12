"""Git operations for Buildkit."""

import logging
import os
from pathlib import Path
from .commands import run_command_check, CommandError
from typing import Optional

logger = logging.getLogger(__name__)

def clone_repo(repo_url: str, target_dir: str, branch: Optional[str] = None, recurse_submodules: bool = False) -> None:
    """Clones a Git repository.

    Args:
        repo_url: The URL of the repository to clone.
        target_dir: The directory to clone into.
        branch: The specific branch or tag to clone. If None, clones the default branch.
        recurse_submodules: If True, initializes and updates submodules recursively.
    """
    command = ["git", "clone"]
    if branch:
        command.extend(["--branch", branch])
    if recurse_submodules:
        command.append("--recurse-submodules")
    command.extend([repo_url, target_dir])

    logger.info(f"Cloning {repo_url} into {target_dir}... Branch: {branch or 'default'}, Submodules: {recurse_submodules}")
    logger.info("(Output will stream below...)")
    try:
        # Use streaming for potentially long clone process
        run_command_check(command, stream_output=True)
        logger.info(f"Successfully cloned {repo_url} to {target_dir}")
    except CommandError as e:
        logger.error(f"Failed to clone repository: {e}")
        raise # Re-raise the exception

def checkout_tag(repo_path: str, tag: str) -> None:
    """Checks out a specific tag in a Git repository.

    Args:
        repo_path: The path to the local repository.
        tag: The tag to checkout (e.g., 'v1.0.0').
    """
    # The script uses `git checkout tags/<tag>`, ensure we match that if needed.
    # Standard git checkout usually just needs the tag name.
    # Let's use the format from the script for compatibility.
    tag_ref = f"tags/{tag}"
    command = ["git", "checkout", tag_ref]
    logger.info(f"Checking out tag {tag_ref} in {repo_path}...")
    try:
        # Use run_command_check which runs in the specified directory (cwd)
        run_command_check(command, cwd=repo_path)
        logger.info(f"Successfully checked out tag {tag_ref} in {repo_path}")
    except CommandError as e:
        logger.error(f"Failed to checkout tag {tag_ref}: {e}")
        raise

def update_submodules(repo_path: str) -> None:
    """Initializes and updates submodules recursively.

    Args:
        repo_path: The path to the local repository.
    """
    command = ["git", "submodule", "update", "--init", "--recursive"]
    logger.info(f"Updating submodules in {repo_path}...")
    try:
        run_command_check(command, cwd=repo_path)
        logger.info(f"Successfully updated submodules in {repo_path}")
    except CommandError as e:
        logger.error(f"Failed to update submodules: {e}")
        raise

def get_commit_hash(repo_path: str) -> str:
    """Gets the current commit hash (HEAD) of the repository.

    Args:
        repo_path: The path to the local repository.

    Returns:
        The commit hash as a string.
    """
    command = ["git", "rev-parse", "HEAD"]
    logger.info(f"Getting commit hash for HEAD in {repo_path}...")
    try:
        stdout, _ = run_command_check(command, cwd=repo_path)
        commit_hash = stdout.strip()
        logger.info(f"Found commit hash: {commit_hash}")
        return commit_hash
    except CommandError as e:
        logger.error(f"Failed to get commit hash: {e}")
        raise

# --- Keep other functions if they exist and are needed, otherwise remove --- 
# Example: Check if a directory is a git repo (potentially useful)

def is_git_repo(path: str) -> bool:
    """Checks if a directory is a Git repository."""
    return Path(path, ".git").is_dir()

# Example: Get current branch (might not be needed for this task)

def get_current_branch(repo_path: str) -> Optional[str]:
    """Gets the current branch name."""
    command = ["git", "rev-parse", "--abbrev-ref", "HEAD"]
    try:
        stdout, _ = run_command_check(command, cwd=repo_path)
        branch = stdout.strip()
        return branch if branch != "HEAD" else None # Handle detached HEAD state
    except CommandError:
        return None