import logging
import os
import sys
from pathlib import Path
import subprocess
from typing import Optional

from thw_nodekit.config import get_config, Config

logger = logging.getLogger(__name__)

# ANSI Color Codes
COLOR_BOLD_GREEN = "\033[1;32m"
COLOR_BRIGHT_CYAN = "\033[1;36m"
COLOR_YELLOW = "\033[1;33m"
COLOR_RED = "\033[1;31m"
COLOR_RESET = "\033[0m"

def _create_symlink_internal(target_path_str: str, link_path_str: str) -> bool:
    """
    Creates a symlink, ensuring target exists and handling pre-existing links.
    Mimics 'ln --force --symbolic'. --no-dereference is implicitly handled by
    unlinking first if link_path exists.
    """
    target_path = Path(target_path_str).resolve() # Resolve to ensure it's absolute and exists
    link_path = Path(link_path_str)

    logger.info(f"Attempting to create symlink: {link_path} -> {target_path}")

    if not target_path.exists():
        logger.error(f"ERROR: Symlink target does not exist: {target_path}")
        return False
    if not target_path.is_dir(): # Assuming target should always be a directory based on usage
        logger.error(f"ERROR: Symlink target is not a directory: {target_path}")
        return False

    try:
        # Ensure parent directory of the link exists
        link_path.parent.mkdir(parents=True, exist_ok=True)

        # Mimic "ln --force": remove existing link_path if it exists
        if link_path.exists() or link_path.is_symlink(): # Check is_symlink for broken symlinks
            logger.info(f"Removing existing file/symlink at {link_path}")
            if link_path.is_dir() and not link_path.is_symlink(): # Don't remove a real directory
                logger.error(
                    f"ERROR: Path {link_path} is an existing directory, not a symlink. "
                    f"Please remove it manually if you intend to replace it with a symlink."
                )
                return False
            link_path.unlink(missing_ok=True) # missing_ok in case it's a broken symlink removed by another process

        # Create the symlink. target_is_directory=True is good practice.
        link_path.symlink_to(target_path, target_is_directory=True)

        logger.info(f"Successfully created symlink: {link_path} -> {target_path}")
        return True
    except OSError as e:
        logger.error(f"Failed to create symlink: {e}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred during symlink creation: {e}")
        return False

def _verify_versions(client: str, expected_tag: str, symlink_path_str: str):
    """
    Verifies the versions after symlink creation by calling executables.
    This assumes the executables (solana, fdctl) are accessible via PATH
    after the symlink is in place, or that their parent dir is the symlink target.
    """
    logger.info(f"STATUS: Checking if version(s) set by Active Release ({symlink_path_str}) match TAG: {expected_tag}")
    
    # The original script calls `solana --version` etc. directly, implying PATH setup.
    # We will replicate this behavior.
    commands_to_check = []
    if client != "firedancer": # For Agave/Jito, expect 'solana --version' to match tag
        commands_to_check.append({"cmd": ["solana", "--version"], "expect_tag": True})
    else: # For Firedancer
        commands_to_check.append({"cmd": ["solana", "--version"], "expect_tag": False}) # solana --version might be generic
        commands_to_check.append({"cmd": ["fdctl", "version"], "expect_tag": True})   # fdctl version should match tag

    all_checks_passed = True

    for item in commands_to_check:
        cmd = item["cmd"]
        expect_tag_in_output = item["expect_tag"]
        cmd_str = " ".join(cmd)
        logger.info(f"Running: {cmd_str}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=10)
            output = result.stdout.strip() if result.stdout else ""
            stderr_output = result.stderr.strip() if result.stderr else ""

            if result.returncode == 0:
                logger.info(f"Output: {output}")
                if expect_tag_in_output:
                    # Strip leading 'v'
                    tag_without_v = expected_tag.lstrip('v') 
                    # Extract the base version part (e.g., "2.1.21" from "2.1.21-mod" or "2.1.21-jito")
                    base_version_to_check = tag_without_v.split('-')[0]

                    if base_version_to_check not in output:
                        logger.warning(
                            f"WARNING: Expected base version '{base_version_to_check}' (derived from input tag '{expected_tag}') "
                            f"not found in '{cmd_str}' output: \"{output}\"."
                        )
                        all_checks_passed = False
            else:
                logger.error(f"Failed to run '{cmd_str}'. Return code: {result.returncode}")
                if stderr_output:
                    logger.error(f"Stderr: {stderr_output}")
                all_checks_passed = False
        except FileNotFoundError:
            logger.error(f"Error: Command '{cmd[0]}' not found. Ensure it is in your PATH.")
            all_checks_passed = False
            # If a crucial command is missing, no point continuing checks for it.
            if cmd[0] == "fdctl" and client == "firedancer": return False 
            if cmd[0] == "solana" and client != "firedancer": return False
        except subprocess.TimeoutExpired:
            logger.error(f"Error: Command '{cmd_str}' timed out.")
            all_checks_passed = False
        except Exception as e:
            logger.error(f"An unexpected error occurred while running '{cmd_str}': {e}")
            all_checks_passed = False
            
    if all_checks_passed:
        logger.info(f"Version check(s) indicate consistency with tag {expected_tag}.")
    else:
        logger.warning(f"Version check(s) indicate a potential mismatch or issue with tag {expected_tag}. Please review output.")
    return all_checks_passed


def manage_symlink(client: str, tag: str, config_path: Optional[str] = None) -> bool:
    """
    Manages the creation of a symlink for a given Solana client and tag.
    """
    if not client:
        logger.error(f"ERROR: Client cannot be empty.")
        return False
    if not tag:
        logger.error(f"ERROR: TAG cannot be empty. Please provide a valid release tag.")
        return False

    config = get_config(custom_path=config_path)

    symlink_path_str = config.get("paths.symlink_path")
    if not symlink_path_str:
        logger.error(f"ERROR: Configuration missing: paths.symlink_path")
        return False

    base_install_dir_str = config.get("paths.install_dir")
    if not base_install_dir_str:
        logger.error(f"ERROR: Configuration missing: paths.install_dir")
        return False

    # Construct symlink target path
    install_dir_for_client_tag = Path(base_install_dir_str) / client / tag
    symlink_target_actual_path: Path

    if client.lower() == "firedancer":
        firedancer_subpath = config.get("paths.firedancer.symlink_subpath")
        if not firedancer_subpath:
            logger.error(
                f"ERROR: Configuration missing for Firedancer: paths.firedancer.symlink_subpath"
            )
            return False
        symlink_target_actual_path = install_dir_for_client_tag / firedancer_subpath
    else:
        symlink_target_actual_path = install_dir_for_client_tag
    
    # Check existence before resolving to provide a clearer error if base path is wrong
    if not symlink_target_actual_path.exists():
         logger.error(f"ERROR: Symlink target directory does not exist: {symlink_target_actual_path}")
         logger.error("Please ensure the client and tag are correct and the release has been installed properly.")
         return False
    
    symlink_target_str_resolved = str(symlink_target_actual_path.resolve())


    # User confirmation section
    separator = "-" * 120
    print(f"{COLOR_BRIGHT_CYAN}{separator}{COLOR_RESET}")
    print(f"{COLOR_BOLD_GREEN}THW-NodeKit {COLOR_BRIGHT_CYAN}| Symlink Update{COLOR_RESET}")
    print(f"{COLOR_BRIGHT_CYAN}{separator}{COLOR_RESET}")
    
    details = {
        "Client": client, # Changed from "Project" to "Client" for consistency with other parts of nodekit
        "Release Tag": tag,
        "Install Directory": str(install_dir_for_client_tag.resolve()),
        "Symlink Target": symlink_target_str_resolved,
        "Symlink Path": symlink_path_str # This is the active_release path
    }
    
    max_label_len = max(len(k) for k in details.keys())
    padding = max_label_len + 4

    for label, value in details.items():
        print(f"{COLOR_BRIGHT_CYAN}{label + ':':<{padding}}{COLOR_RESET}{value}")
    
    print(f"{COLOR_BRIGHT_CYAN}{separator}{COLOR_RESET}") # Use full separator
    
    try:
        confirm = input(f"{COLOR_BOLD_GREEN}Proceed with update? (y/n): {COLOR_RESET}")
        if confirm.lower() != 'y':
            logger.warning("Symlink update aborted by user.")
            # Exiting successfully as it's a user choice, not an error.
            return True 
    except EOFError: # Handle non-interactive environments
        logger.warning("EOFError reading input (non-interactive environment?). Aborting symlink update for safety.")
        return False # Abort if no confirmation can be obtained.

    # Perform symlink update
    print(f"STATUS: Creating symlink to '{symlink_path_str}'")
    
    if not _create_symlink_internal(symlink_target_str_resolved, symlink_path_str):
        logger.error(f"Symlink creation failed.")
        return False # Symlink creation itself failed

    # Run version check after symlink update
    _verify_versions(client, tag, symlink_path_str)
    
    print(f"{COLOR_BOLD_GREEN}STATUS: Done.{COLOR_RESET}")
    return True
