import subprocess
import sys
import os
import logging
from thw_nodekit.config import get_config

# ANSI Color Codes
C_GREEN = "\033[1;32m"
C_CYAN = "\033[1;36m"
C_YELLOW = "\033[1;33m"
C_BOLD_RED = "\033[1;31m"
C_NC = "\033[0m"

logger = logging.getLogger(__name__)

def download_snapshot(cluster: str, snap_type: str):
    """
    Downloads Solana snapshots using aria2c.
    """
    config = get_config()
    cluster_map = {"um": "Mainnet", "ut": "Testnet"}
    cluster_name = cluster_map.get(cluster, "Unknown")

    if cluster == "um":
        base_url = "https://snapshots.avorio.network/mainnet-beta"
        snaps_dir = config.get("toolkit.snapshot_dir_um")
    elif cluster == "ut":
        base_url = "https://snapshots.avorio.network/testnet"
        snaps_dir = config.get("toolkit.snapshot_dir_ut")
    else:
        logger.error(f"Invalid cluster '{cluster}'. Valid options: 'um' (mainnet), 'ut' (testnet)")
        print(f"{C_BOLD_RED}Error: Invalid cluster '{cluster}'. Valid options: 'um' (mainnet), 'ut' (testnet){C_NC}")
        return False

    if not snaps_dir:
        logger.error(f"Snapshot directory for cluster '{cluster}' not configured. Please set 'toolkit.snapshot_dir_{cluster}'.")
        print(f"{C_BOLD_RED}Error: Snapshot directory for cluster '{cluster}' not configured. Please set 'toolkit.snapshot_dir_{cluster}'.{C_NC}")
        return False

    full_snapshot_url = f"{base_url}/snapshot.tar.bz2"
    incr_snapshot_url = f"{base_url}/incremental-snapshot.tar.bz2"

    snap_urls = []
    snap_type_display = snap_type.capitalize()
    if snap_type == "full":
        snap_urls.append(full_snapshot_url)
    elif snap_type == "incr":
        snap_urls.append(incr_snapshot_url)
        snap_type_display = "Incremental"
    elif snap_type == "both":
        snap_urls.extend([incr_snapshot_url, full_snapshot_url])
    else:
        logger.error(f"Invalid snapshot type '{snap_type}'. Valid options: 'full', 'incr', 'both'.")
        print(f"{C_BOLD_RED}Error: Invalid snapshot type '{snap_type}'. Valid options: 'full', 'incr', 'both'.{C_NC}")
        return False

    if not snap_urls:
        logger.error("No snapshot URLs determined. This should not happen if type is valid.")
        print(f"{C_BOLD_RED}Error: No snapshot URLs determined.{C_NC}")
        return False

    # --- User Confirmation --- 
    separator = "-" * 120
    print(f"{C_CYAN}{separator}{C_NC}")
    print(f"{C_GREEN}THW-NodeKit {C_CYAN}| Snapshot Download (Avorio Network){C_NC}")
    print(f"{C_CYAN}{separator}{C_NC}")

    details = {
        "Cluster": cluster_name,
        "Snapshot Type": snap_type_display,
        "Download Directory": snaps_dir,
        "Source URL(s)": "\n".join(snap_urls)
    }
    max_label_len = max(len(k) for k in details.keys())
    padding = max_label_len + 4

    for label, value in details.items():
        if label == "Source URL(s)":
            urls = value.splitlines()
            if urls:
                print(f"{C_CYAN}{label + ':':<{padding}}{C_NC}{urls[0]}")
                for i in range(1, len(urls)):
                    print(f"{'':<{padding}}{urls[i]}")
            else:
                print(f"{C_CYAN}{label + ':':<{padding}}{C_NC}")
        elif "\n" in value:
            print(f"{C_CYAN}{label + ':':<{padding}}{C_NC}{value.splitlines()[0]}")
            for line in value.splitlines()[1:]:
                print(f"{'':<{padding}}{line}")
        else:
            print(f"{C_CYAN}{label + ':':<{padding}}{C_NC}{value}")
    
    print(f"{C_CYAN}{separator}{C_NC}")

    try:
        confirm = input(f"{C_GREEN}Proceed with download? (y/n): {C_NC}").strip().lower()
        if confirm != 'y':
            logger.warning("Snapshot download cancelled by user.")
            print(f"{C_YELLOW}Snapshot download cancelled by user.{C_NC}")
            return True
    except EOFError:
        logger.warning("EOFError reading input (non-interactive environment?). Aborting download for safety.")
        print(f"{C_YELLOW}Snapshot download aborted due to non-interactive environment.{C_NC}")
        return True

    # --- End User Confirmation ---

    logger.info(f"Starting download to: {snaps_dir} from URLs: {snap_urls}")
    
    try:
        os.makedirs(snaps_dir, exist_ok=True)
        
        command = [
            "aria2c",
            "-x16",
            "-s16",
            "--force-sequential=true",
            f"--dir={snaps_dir}",
        ]
        command.extend(snap_urls)
        
        logger.info(f"Executing command: {' '.join(command)}")
        process = subprocess.Popen(command, stdout=sys.stdout, stderr=sys.stderr)
        process.wait()

        if process.returncode == 0:
            logger.info("Download completed successfully via aria2c.")
            print(f"\n{C_GREEN}Download completed successfully.{C_NC}")
            return True
        else:
            logger.error(f"Error during download with aria2c. Return code: {process.returncode}")
            print(f"\n{C_BOLD_RED}Error during download with aria2c. Return code: {process.returncode}{C_NC}")
            return False
    except FileNotFoundError:
        logger.error("aria2c command not found.")
        print(f"{C_BOLD_RED}Error: aria2c command not found.{C_NC}")
        return False
    except Exception as e:
        logger.exception(f"An unexpected error occurred during snap_avorio download process: {e}")
        print(f"{C_BOLD_RED}An unexpected error occurred: {e}{C_NC}")
        return False
