import subprocess
import psutil
import logging
import sys
import os
from typing import Optional, List, Any
from thw_nodekit.config import get_config

logger = logging.getLogger("thw_nodekit.toolkit.affinity")

# ANSI Color Codes
COLOR_BOLD_GREEN = "\033[1;32m"
COLOR_BRIGHT_CYAN = "\033[1;36m"
COLOR_YELLOW = "\033[1;33m"
COLOR_RED = "\033[1;31m"
COLOR_RESET = "\033[0m"

def _find_agave_validator_pid() -> Optional[int]:
    """Finds the PID of the running agave-validator process."""
    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            if proc.info['cmdline'] and \
               proc.info['cmdline'][0].endswith('agave-validator') and \
               '--identity' in proc.info['cmdline']:
                logger.debug(f"Found agave-validator process with PID: {proc.info['pid']}")
                return proc.info['pid']
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return None

def _find_solpoh_tick_prod_tid(main_pid: int) -> Optional[int]:
    """Finds the Thread ID (TID/SPID) of the 'solPohTickProd' thread for a given main PID."""
    try:
        cmd = ["ps", "-T", "-p", str(main_pid), "-o", "spid,comm"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding='utf-8')
        lines = result.stdout.strip().split('\n')
        
        for line in lines[1:]:  # Skip header
            parts = line.strip().split(None, 1)  # Split only on the first whitespace
            if len(parts) == 2:
                tid_str, comm_str = parts
                if 'solPohTickProd' in comm_str:
                    try:
                        tid = int(tid_str)
                        logger.debug(f"Found solPohTickProd thread with TID: {tid} for PID: {main_pid}")
                        return tid
                    except ValueError:
                        logger.warning(f"Could not parse TID from 'ps' output line: {line}")
                        continue
    except FileNotFoundError:
        logger.error("`ps` command not found. Please ensure it's installed and in PATH.")
        return None
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running `ps` command: {e}. Output: {e.stderr}")
        return None
    return None

def manage_affinity(core_override: Optional[int] = None) -> None:
    """Manages the CPU affinity for the solana 'solPohTickProd' thread."""
    config = get_config()
    logger.info("Attempting to manage CPU affinity for solPohTickProd thread.")

    solana_pid = _find_agave_validator_pid()
    if not solana_pid:
        logger.error("affinity: agave_validator_404. Ensure agave-validator with --identity is running.")
        sys.exit(1)
    logger.info(f"Found agave-validator PID: {solana_pid}")

    thread_tid = _find_solpoh_tick_prod_tid(solana_pid)
    if not thread_tid:
        logger.error(f"affinity: solPohTickProd_404. Could not find solPohTickProd thread for PID {solana_pid}.")
        sys.exit(1)
    logger.info(f"Found solPohTickProd thread TID: {thread_tid}")

    target_core_val: Any
    if core_override is not None:
        target_core_val = core_override
        logger.info(f"Using user-specified core: {target_core_val}")
    else:
        target_core_val = config.get("toolkit.poh_core")
        if target_core_val is None:
            logger.error("Error: 'toolkit.poh_core' not found in configuration and --core option not used.")
            sys.exit(1)
        logger.info(f"Using core from config: {target_core_val}")
    
    try:
        target_core = int(target_core_val)
        if target_core < 0:
            raise ValueError("Core number must be non-negative.")
    except ValueError:
        logger.error(f"Invalid core value: '{target_core_val}'. Must be a non-negative integer.")
        sys.exit(1)

    try:
        target_thread_proc = psutil.Process(thread_tid)
        current_affinity = target_thread_proc.cpu_affinity()
        logger.info(f"Current affinity for TID {thread_tid} (solPohTickProd): {current_affinity}")

        if len(current_affinity) == 1 and current_affinity[0] == target_core:
            logger.info(f"affinity: solPohTickProd_already_set to core {target_core}.")
            print(f"{COLOR_YELLOW}Thread solPohTickProd (TID: {thread_tid}) is already set to core {target_core}.{COLOR_RESET}")
            sys.exit(0)
        else:
            separator = "-" * 120
            print(f"{COLOR_BRIGHT_CYAN}{separator}{COLOR_RESET}")
            print(f"{COLOR_BOLD_GREEN}THW-NodeKit {COLOR_BRIGHT_CYAN}| PoH Thread CPU Affinity Utility{COLOR_RESET}")
            print(f"{COLOR_BRIGHT_CYAN}{separator}{COLOR_RESET}")

            details = {
                "Agave Validator PID": str(solana_pid),
                "PoH Thread TID": str(thread_tid),
                "Current Affinity": str(current_affinity),
                "Target Core": str(target_core)
            }
            max_label_len = max(len(k) for k in details.keys())
            padding = max_label_len + 4

            for label, value in details.items():
                print(f"{COLOR_BRIGHT_CYAN}{label + ':':<{padding}}{COLOR_RESET}{value}")
            
            print(f"{COLOR_BRIGHT_CYAN}{separator}{COLOR_RESET}")

            if os.geteuid() != 0:
                logger.warning("Process not running as root. Setting CPU affinity might fail if the user does not have the necessary permissions.")
                print(f"{COLOR_YELLOW}Warning: This command may require root (sudo) privileges to change CPU affinity.{COLOR_RESET}")
                print() # Add a blank line for spacing before the prompt

            try:
                confirm = input(f"{COLOR_BOLD_GREEN}Proceed to set affinity to core {target_core}? (y/n): {COLOR_RESET}").strip().lower()
                
                if confirm == 'y':
                    target_thread_proc.cpu_affinity([target_core])
                    new_affinity = target_thread_proc.cpu_affinity()  # Re-check affinity
                    if len(new_affinity) == 1 and new_affinity[0] == target_core:
                        logger.info(f"affinity: set_done. Successfully set affinity for TID {thread_tid} to [{target_core}].")
                        logger.info(f"Verified new affinity: {new_affinity}")
                        print(f"{COLOR_BOLD_GREEN}Successfully set affinity for TID {thread_tid} to {new_affinity}.{COLOR_RESET}")
                    else:
                        logger.error(f"affinity: set_failed. Attempted to set core {target_core}, but current is {new_affinity}.")
                        print(f"{COLOR_RED}Error: Failed to set affinity. Current affinity is {new_affinity}.{COLOR_RESET}")
                        sys.exit(1)
                else:
                    logger.info("User cancelled affinity change.")
                    print(f"{COLOR_YELLOW}Affinity change cancelled by user.{COLOR_RESET}")
                    sys.exit(0)
            except EOFError:
                logger.warning("EOFError reading input (non-interactive environment?). Aborting affinity change for safety.")
                print(f"{COLOR_YELLOW}Affinity change aborted due to non-interactive environment.{COLOR_RESET}")
                sys.exit(1) # Exit with an error code

    except psutil.NoSuchProcess:
        logger.error(f"affinity: Thread with TID {thread_tid} no longer found. It might have terminated.")
        print(f"{COLOR_RED}Error: Thread with TID {thread_tid} no longer found. It might have terminated.{COLOR_RESET}")
        sys.exit(1)
    except psutil.AccessDenied:
        logger.error(f"affinity: Access Denied. Run with sudo or as root to change CPU affinity.")
        print(f"{COLOR_RED}Error: Access Denied. Please run with sudo or as root to change CPU affinity.{COLOR_RESET}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"An unexpected error occurred while managing affinity for TID {thread_tid}")  # exception includes stack trace
        print(f"{COLOR_RED}An unexpected error occurred: {e}{COLOR_RESET}")
        sys.exit(1)
