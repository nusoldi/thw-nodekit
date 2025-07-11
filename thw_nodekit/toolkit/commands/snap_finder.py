import os
import glob
import requests
import time
import shutil
import math
import json
import sys
import logging
import subprocess
from pathlib import Path
from requests import ReadTimeout, ConnectTimeout, HTTPError, Timeout, ConnectionError
from tqdm import tqdm
from multiprocessing.dummy import Pool as ThreadPool
import statistics
from thw_nodekit.config import get_config

# ANSI Color Codes
C_GREEN = "\033[1;32m"
C_CYAN = "\033[1;36m"
C_YELLOW = "\033[1;33m"
C_BOLD_RED = "\033[1;31m"
C_NC = "\033[0m"

# --- Module-level variables (will be configured by find_snapshot_and_download) ---
# Configuration (set by find_snapshot_and_download based on its args and defaults)
RPC = ""
SPECIFIC_SLOT_CONFIG = 0
SPECIFIC_VERSION_CONFIG = None
WILDCARD_VERSION_CONFIG = None
MAX_SNAPSHOT_AGE_IN_SLOTS_CONFIG = 1300
WITH_PRIVATE_RPC_CONFIG = False 
THREADS_COUNT_CONFIG = 1000
MIN_DOWNLOAD_SPEED_MB_CONFIG = 60
MAX_DOWNLOAD_SPEED_MB_CONFIG = None
SPEED_MEASURE_TIME_SEC_CONFIG = 7
MAX_LATENCY_CONFIG = 100
SNAPSHOT_PATH_CONFIG = "."
SORT_ORDER_CONFIG = 'latency'

# Runtime State (managed by find_snapshot_and_download and helpers)
current_slot = 0
DISCARDED_BY_ARCHIVE_TYPE = 0
DISCARDED_BY_LATENCY = 0
DISCARDED_BY_SLOT = 0
DISCARDED_BY_VERSION = 0
DISCARDED_BY_UNKNW_ERR = 0
DISCARDED_BY_TIMEOUT = 0
FULL_LOCAL_SNAPSHOTS = [] 
FULL_LOCAL_SNAP_SLOT = 0 
unsuitable_servers = set()
json_data = {}
pbar = None 
wget_path = None

DEFAULT_HEADERS = {"Content-Type": "application/json"}
logger = logging.getLogger("thw_nodekit.toolkit.snap_finder")


def convert_size(size_bytes):
   if size_bytes == 0:
    return "0B"
   size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
   i = int(math.floor(math.log(size_bytes, 1024)))
   p = math.pow(1024, i)
   s = round(size_bytes / p, 2)
   return "%s %s" % (s, size_name[i])


def measure_speed(url: str, measure_time: int) -> float:
    logger.debug('measure_speed()')
    url = f'http://{url}/snapshot.tar.bz2' # Uses module global SNAPSHOT_PATH_CONFIG indirectly
    try:
        r = requests.get(url, stream=True, timeout=measure_time+2)
        r.raise_for_status()
    except requests.RequestException as e:
        logger.debug(f"Failed to connect or stream from {url} for speed test: {e}")
        return 0.0 # Cannot measure speed

    start_time = time.monotonic_ns()
    last_time = start_time
    loaded = 0
    speeds = []
    try:
        for chunk in r.iter_content(chunk_size=81920):
            curtime = time.monotonic_ns()

            worktime = (curtime - start_time) / 1000000000
            if worktime >= measure_time:
                break

            delta = (curtime - last_time) / 1000000000
            loaded += len(chunk)
            if delta > 1: # Calculate speed roughly every second
                estimated_bytes_per_second = loaded * (1 / delta)
                speeds.append(estimated_bytes_per_second)
                last_time = curtime
                loaded = 0
        if not speeds:
            return 0.0
        return statistics.median(speeds)
    except Exception as e:
        logger.debug(f"Error during speed measurement content iteration for {url}: {e}")
        return 0.0
    finally:
        r.close()


def do_request(url_: str, method_: str = 'GET', data_: str = '', timeout_: int = 3,
               headers_: dict = None):
    global DISCARDED_BY_UNKNW_ERR
    global DISCARDED_BY_TIMEOUT
    
    if headers_ is None:
        headers_ = DEFAULT_HEADERS

    try:
        if method_.lower() == 'get':
            r = requests.get(url_, headers=headers_, timeout=(timeout_, timeout_))
        elif method_.lower() == 'post':
            r = requests.post(url_, headers=headers_, data=data_, timeout=(timeout_, timeout_))
        elif method_.lower() == 'head':
            r = requests.head(url_, headers=headers_, timeout=(timeout_, timeout_))
        else:
            logger.error(f"Unsupported HTTP method: {method_}")
            return f'error in do_request(): Unsupported HTTP method: {method_}'
        return r

    except (ReadTimeout, ConnectTimeout, HTTPError, Timeout, ConnectionError) as reqErr:
        DISCARDED_BY_TIMEOUT += 1
        return f'error in do_request(): {reqErr}'
    except Exception as unknwErr:
        DISCARDED_BY_UNKNW_ERR += 1
        # Original code had 'reqErr' here, correcting to 'unknwErr'
        return f'error in do_request(): {unknwErr}'


def get_current_slot():
    logger.debug("get_current_slot()")
    # Uses module global RPC
    d = '{"jsonrpc":"2.0","id":1, "method":"getSlot"}'
    try:
        r = do_request(url_=RPC, method_='post', data_=d, timeout_=25)
        if isinstance(r, str) or 'result' not in str(r.text): # Check if do_request returned error string
            logger.error(f'Can\'t get current slot. Response: {r.text if not isinstance(r, str) else r}')
            if not isinstance(r, str): logger.debug(r.status_code)
            return None
        return r.json()["result"]
    except Exception as e: # Catch potential .json() errors or other issues
        logger.error(f'Exception in get_current_slot(): {e}')
        return None


def get_all_rpc_ips():
    global DISCARDED_BY_VERSION
    logger.debug("get_all_rpc_ips()")
    # Uses module globals RPC, WILDCARD_VERSION_CONFIG, SPECIFIC_VERSION_CONFIG, WITH_PRIVATE_RPC_CONFIG
    d = '{"jsonrpc":"2.0", "id":1, "method":"getClusterNodes"}'
    r = do_request(url_=RPC, method_='post', data_=d, timeout_=25)

    if isinstance(r, str) or 'result' not in str(r.text):
        logger.error(f'Can\'t get RPC ip addresses. Response: {r.text if not isinstance(r, str) else r}')
        return [] # Return empty list on failure

    rpc_ips = []
    try:
        for node in r.json()["result"]:
            node_version = node.get("version")
            if (WILDCARD_VERSION_CONFIG is not None and node_version and WILDCARD_VERSION_CONFIG not in node_version) or \
               (SPECIFIC_VERSION_CONFIG is not None and node_version and node_version != SPECIFIC_VERSION_CONFIG):
                DISCARDED_BY_VERSION += 1
                continue
            
            node_rpc = node.get("rpc")
            if node_rpc:
                rpc_ips.append(node_rpc)
            elif WITH_PRIVATE_RPC_CONFIG:
                gossip_ip_port = node.get("gossip")
                if gossip_ip_port:
                    gossip_ip = gossip_ip_port.split(":")[0]
                    rpc_ips.append(f'{gossip_ip}:8899')
    except Exception as e:
        logger.error(f"Error processing cluster nodes in get_all_rpc_ips: {e}")
        return []


    rpc_ips = list(set(rpc_ips))
    logger.debug(f'RPC_IPS LEN {len(rpc_ips)}')
    # IP_BLACKLIST functionality removed
    return rpc_ips


def get_snapshot_slot(rpc_address: str):
    global pbar, DISCARDED_BY_ARCHIVE_TYPE, DISCARDED_BY_LATENCY, DISCARDED_BY_SLOT, json_data
    # Uses module globals MAX_LATENCY_CONFIG, current_slot, MAX_SNAPSHOT_AGE_IN_SLOTS_CONFIG, FULL_LOCAL_SNAP_SLOT

    if pbar: pbar.update(1)
    url = f'http://{rpc_address}/snapshot.tar.bz2'
    inc_url = f'http://{rpc_address}/incremental-snapshot.tar.bz2'
    
    try:
        r_inc = do_request(url_=inc_url, method_='head', timeout_=1)
        if not isinstance(r_inc, str): # Check if request was successful
            if 'location' in r_inc.headers and r_inc.elapsed.total_seconds() * 1000 > MAX_LATENCY_CONFIG:
                DISCARDED_BY_LATENCY += 1
                return None

            if 'location' in r_inc.headers:
                snap_location_inc = r_inc.headers["location"]
                if snap_location_inc.endswith('.tar'): # Filter uncompressed
                    DISCARDED_BY_ARCHIVE_TYPE += 1
                    return None
                
                parts = snap_location_inc.split("-")
                if len(parts) > 3: # Basic check for expected format
                    try:
                        incremental_base_slot = int(parts[2])
                        tip_snap_slot = int(parts[3])
                        slots_diff_tip = current_slot - tip_snap_slot

                        if slots_diff_tip < -100: # Too far in future
                            DISCARDED_BY_SLOT += 1
                            return None
                        if slots_diff_tip > MAX_SNAPSHOT_AGE_IN_SLOTS_CONFIG:
                            DISCARDED_BY_SLOT += 1
                            return None

                        if FULL_LOCAL_SNAP_SLOT == incremental_base_slot:
                            json_data["rpc_nodes"].append({
                                "snapshot_address": rpc_address,
                                "slots_diff": slots_diff_tip, # Relative to tip of incremental
                                "latency": r_inc.elapsed.total_seconds() * 1000,
                                "files_to_download": [snap_location_inc]
                            })
                            return None # Found suitable incremental

                        # Incremental found, but not matching local full, check for corresponding full
                        r_full_for_inc = do_request(url_=url, method_='head', timeout_=1)
                        if not isinstance(r_full_for_inc, str) and 'location' in r_full_for_inc.headers:
                            json_data["rpc_nodes"].append({
                                "snapshot_address": rpc_address,
                                "slots_diff": slots_diff_tip, # Still using incremental's tip slot diff
                                "latency": r_inc.elapsed.total_seconds() * 1000, # Latency of incremental check
                                "files_to_download": [snap_location_inc, r_full_for_inc.headers['location']],
                            })
                            return None
                    except (ValueError, IndexError) as e:
                        logger.debug(f"Error parsing incremental snapshot name {snap_location_inc}: {e}")
                        # Fall through to full snapshot check
                else:
                    logger.debug(f"Incremental snapshot name format unexpected: {snap_location_inc}")


        # Check for full snapshot if no suitable incremental path taken
        r_full = do_request(url_=url, method_='head', timeout_=1)
        if not isinstance(r_full, str) and 'location' in r_full.headers:
            snap_location_full = r_full.headers["location"]
            if snap_location_full.endswith('.tar'):
                DISCARDED_BY_ARCHIVE_TYPE += 1
                return None
            
            parts = snap_location_full.split("-")
            if len(parts) > 2: # snapshot-SLOT-HASH...
                try:
                    full_snap_slot_val = int(parts[1])
                    slots_diff_full = current_slot - full_snap_slot_val
                    if slots_diff_full <= MAX_SNAPSHOT_AGE_IN_SLOTS_CONFIG and r_full.elapsed.total_seconds() * 1000 <= MAX_LATENCY_CONFIG:
                        json_data["rpc_nodes"].append({
                            "snapshot_address": rpc_address,
                            "slots_diff": slots_diff_full,
                            "latency": r_full.elapsed.total_seconds() * 1000,
                            "files_to_download": [snap_location_full]
                        })
                        return None
                    else: # Did not meet age or latency for full
                        if slots_diff_full > MAX_SNAPSHOT_AGE_IN_SLOTS_CONFIG : DISCARDED_BY_SLOT += 1
                        if r_full.elapsed.total_seconds() * 1000 > MAX_LATENCY_CONFIG : DISCARDED_BY_LATENCY +=1

                except (ValueError, IndexError) as e:
                    logger.debug(f"Error parsing full snapshot name {snap_location_full}: {e}")
        return None # No suitable snapshot found or error

    except Exception: # Catch-all for unexpected issues in this function
        # DISCARDED_BY_UNKNW_ERR implicitly handled by do_request for network errors
        return None


def download(url_to_download: str):
    # Uses module globals SNAPSHOT_PATH_CONFIG, MAX_DOWNLOAD_SPEED_MB_CONFIG, wget_path
    fname = url_to_download[url_to_download.rfind('/'):].replace("/", "")
    temp_fname = f'{SNAPSHOT_PATH_CONFIG}/tmp-{fname}'
    final_fname = f'{SNAPSHOT_PATH_CONFIG}/{fname}'
    
    cmd = [wget_path, '--progress=dot:giga', '--trust-server-names', url_to_download, f'-O{temp_fname}']
    if MAX_DOWNLOAD_SPEED_MB_CONFIG is not None:
        cmd.insert(1, f'--limit-rate={MAX_DOWNLOAD_SPEED_MB_CONFIG}M')

    try:
        logger.info(f"Downloading {url_to_download} (via wget)")
        # Allow wget to print directly to terminal by removing stdout/stderr PIPE
        process = subprocess.run(cmd, universal_newlines=True, check=False)
        
        if process.returncode == 0:
            logger.info(f"wget successfully downloaded to {temp_fname}")
            logger.info(f'Renaming downloaded file {temp_fname} to {final_fname}')
            os.rename(temp_fname, final_fname)
            return True, final_fname # Return success and the final filename
        else:
            logger.error(f"wget failed for {url_to_download}. Return code: {process.returncode}")
            # Output is now directly on terminal, no need to log process.stdout/stderr
            if os.path.exists(temp_fname): # Clean up partial download
                os.remove(temp_fname)
            return False, None # Return failure and no filename
            
    except Exception as e:
        logger.error(f'Exception in download() func for {url_to_download}. Make sure wget is installed and path is correct.\n{e}')
        if os.path.exists(temp_fname):
            os.remove(temp_fname)
        return False, None # Return failure and no filename


def main_worker():
    global pbar, FULL_LOCAL_SNAPSHOTS, FULL_LOCAL_SNAP_SLOT, unsuitable_servers, json_data
    # Uses module globals: RPC, SNAPSHOT_PATH_CONFIG, THREADS_COUNT_CONFIG, current_slot,
    # MAX_SNAPSHOT_AGE_IN_SLOTS_CONFIG, MIN_DOWNLOAD_SPEED_MB_CONFIG, MAX_DOWNLOAD_SPEED_MB_CONFIG,
    # SPEED_MEASURE_TIME_SEC_CONFIG, MAX_LATENCY_CONFIG, SORT_ORDER_CONFIG,
    # SPECIFIC_VERSION_CONFIG, WILDCARD_VERSION_CONFIG, WITH_PRIVATE_RPC_CONFIG
    
    try:
        rpc_nodes = list(set(get_all_rpc_ips())) # Uses various _CONFIG globals
        if not rpc_nodes:
            logger.warning("No RPC nodes found or failed to retrieve them. Check RPC endpoint and network.")
            return 1 # Failure

        if pbar: pbar.close() # Close previous pbar if any
        pbar = tqdm(total=len(rpc_nodes), desc="Scanning RPCs")
        logger.info(f'RPC servers in total: {len(rpc_nodes)} | Current slot number: {current_slot}\n')

        FULL_LOCAL_SNAPSHOTS = glob.glob(f'{SNAPSHOT_PATH_CONFIG}/snapshot-*tar*')
        if len(FULL_LOCAL_SNAPSHOTS) > 0:
            FULL_LOCAL_SNAPSHOTS.sort(key=os.path.getmtime, reverse=True) # Sort by modification time
            try:
                # Assuming snapshot-SLOT-HASH... format
                FULL_LOCAL_SNAP_SLOT = int(Path(FULL_LOCAL_SNAPSHOTS[0]).name.split("-")[1])
                logger.info(f'Found local full snapshot {FULL_LOCAL_SNAPSHOTS[0]} | Slot: {FULL_LOCAL_SNAP_SLOT}')
            except (IndexError, ValueError) as e:
                logger.warning(f"Could not parse slot from local snapshot {FULL_LOCAL_SNAPSHOTS[0]}: {e}. Will not use for incremental matching.")
                FULL_LOCAL_SNAP_SLOT = 0 # Reset if parsing failed
        else:
            logger.info(f'No local full snapshots found in {SNAPSHOT_PATH_CONFIG}. Searching for full snapshots.')
            FULL_LOCAL_SNAP_SLOT = 0

        logger.info(f'Searching for snapshot info on {len(rpc_nodes)} RPCs...')
        if THREADS_COUNT_CONFIG > 0 :
            pool = ThreadPool(THREADS_COUNT_CONFIG)
            pool.map(get_snapshot_slot, rpc_nodes) # get_snapshot_slot appends to global json_data
            pool.close()
            pool.join()
        else: # Sequential for debugging or if threads_count is 0/1
             for node in rpc_nodes: get_snapshot_slot(node)

        if pbar: pbar.close()

        logger.info(f'Found suitable RPCs: {len(json_data.get("rpc_nodes", []))}')
        logger.info(f'Discarded counts: ArchiveType={DISCARDED_BY_ARCHIVE_TYPE}, Latency={DISCARDED_BY_LATENCY}, Slot={DISCARDED_BY_SLOT}, Version={DISCARDED_BY_VERSION}, Timeout={DISCARDED_BY_TIMEOUT}, UnknownError={DISCARDED_BY_UNKNW_ERR}')

        if not json_data.get("rpc_nodes"):
            logger.warning(f'No snapshot nodes found matching criteria (Max Age: {MAX_SNAPSHOT_AGE_IN_SLOTS_CONFIG} slots).')
            return 1 # Failure

        rpc_nodes_sorted = sorted(json_data["rpc_nodes"], key=lambda k: k.get(SORT_ORDER_CONFIG, float('inf')))
        
        # Update json_data structure (as original script did)
        json_data.update({
            "last_update_at": time.time(),
            "last_update_slot": current_slot,
            "total_rpc_nodes_scanned": len(rpc_nodes), # Renamed for clarity
            "rpc_nodes_with_potential_snapshot": len(json_data["rpc_nodes"]), # Renamed
            "rpc_nodes": rpc_nodes_sorted # Overwrite with sorted list
        })

        try:
            with open(f'{SNAPSHOT_PATH_CONFIG}/snapshot_info.json', "w") as result_f: # Renamed file
                json.dump(json_data, result_f, indent=2)
            logger.info(f'Snapshot metadata saved to {SNAPSHOT_PATH_CONFIG}/snapshot_info.json')
        except IOError as e:
            logger.warning(f"Could not write snapshot_info.json: {e}")


        num_of_rpc_to_check_speed = 15 
        logger.info(f"Attempting to measure speed and download from up to {num_of_rpc_to_check_speed} top candidates...")

        for i, rpc_node_info in enumerate(rpc_nodes_sorted[:num_of_rpc_to_check_speed], start=1):
            # Blacklist functionality for specific snapshot files/hashes removed.
            
            snapshot_address = rpc_node_info["snapshot_address"]
            logger.info(f'{i}/{len(rpc_nodes_sorted)} Checking speed for {snapshot_address} (Latency: {rpc_node_info.get("latency", "N/A"):.2f}ms, Slot Diff: {rpc_node_info.get("slots_diff", "N/A")})')
            
            if snapshot_address in unsuitable_servers:
                logger.info(f'Skipping {snapshot_address}, already marked unsuitable.')
                continue

            down_speed_bytes = measure_speed(url=snapshot_address, measure_time=SPEED_MEASURE_TIME_SEC_CONFIG)
            if down_speed_bytes == 0.0:
                 logger.warning(f"Speed measurement failed or result is zero for {snapshot_address}.")
                 unsuitable_servers.add(snapshot_address)
                 continue

            down_speed_mb_ps_str = convert_size(down_speed_bytes) + "/s" # Bytes per second
            
            # Original speed check was MIN_DOWNLOAD_SPEED_MB * 1e6 (MB to Bytes)
            if down_speed_bytes < MIN_DOWNLOAD_SPEED_MB_CONFIG * 1024 * 1024: # MB to Bytes
                logger.info(f'Too slow: {snapshot_address} ({down_speed_mb_ps_str}). Minimum required: {MIN_DOWNLOAD_SPEED_MB_CONFIG} MB/s.')
                unsuitable_servers.add(snapshot_address)
                continue
            
            logger.info(f'Sufficient speed: {snapshot_address} ({down_speed_mb_ps_str}). Proceeding with download.')
            
            all_downloads_successful = True
            for file_path_suffix in reversed(rpc_node_info.get("files_to_download", [])):
                # Avoid re-downloading full snapshot if a matching local one exists and this is a full snapshot path
                is_full_snapshot_path = False
                current_file_slot = 0
                try:
                    # snapshot-SLOT-HASH... or /snapshot-SLOT-HASH...
                    filename_for_check = Path(file_path_suffix).name
                    if filename_for_check.startswith("snapshot-"):
                        is_full_snapshot_path = True
                        current_file_slot = int(filename_for_check.split("-")[1])
                        if current_file_slot == FULL_LOCAL_SNAP_SLOT:
                            logger.info(f"Skipping download of {file_path_suffix}, equivalent local full snapshot slot {FULL_LOCAL_SNAP_SLOT} exists.")
                            continue
                except (IndexError, ValueError) as e:
                    logger.debug(f"Could not parse slot from file path {file_path_suffix} for skipping check: {e}")
                
                # Construct full URL.
                download_url_to_use = f'http://{snapshot_address}{file_path_suffix if file_path_suffix.startswith("/") else "/" + file_path_suffix}'

                # If it's an incremental, get the latest link via a fresh HEAD request
                if "incremental-snapshot" in Path(file_path_suffix).name.lower():
                    logger.info(f"Refreshing incremental snapshot link for {snapshot_address}...")
                    fresh_inc_head_url = f'http://{snapshot_address}/incremental-snapshot.tar.bz2'
                    r_fresh_inc = do_request(url_=fresh_inc_head_url, method_='head', timeout_=2)
                    if not isinstance(r_fresh_inc, str) and 'location' in r_fresh_inc.headers:
                        fresh_location = r_fresh_inc.headers["location"]
                        # Ensure the base slot of the fresh incremental still matches FULL_LOCAL_SNAP_SLOT if it's set
                        # (This is important if FULL_LOCAL_SNAP_SLOT was just updated by a full snapshot download)
                        can_use_fresh_location = True
                        if FULL_LOCAL_SNAP_SLOT > 0:
                            try:
                                fresh_inc_base_slot = int(Path(fresh_location).name.split("-")[2])
                                if fresh_inc_base_slot != FULL_LOCAL_SNAP_SLOT:
                                    logger.warning(f"Fresh incremental {fresh_location} from {snapshot_address} has base slot {fresh_inc_base_slot}, but expected {FULL_LOCAL_SNAP_SLOT}. Sticking to original plan.")
                                    can_use_fresh_location = False
                            except (IndexError, ValueError):
                                logger.warning(f"Could not parse base slot from fresh incremental {fresh_location}. Sticking to original plan.")
                                can_use_fresh_location = False
                        
                        if can_use_fresh_location:
                            logger.info(f"Using fresh incremental link: {fresh_location}")
                            download_url_to_use = f'http://{snapshot_address}{fresh_location if fresh_location.startswith("/") else "/" + fresh_location}'
                        else:
                            logger.info(f"Proceeding with originally identified incremental link: {file_path_suffix}")
                    else:
                        logger.warning(f"Could not get fresh incremental link from {snapshot_address}. Using originally identified link.")
                
                logger.info(f'Downloading {download_url_to_use} to {SNAPSHOT_PATH_CONFIG}')
                download_success, downloaded_fname = download(url_to_download=download_url_to_use)
                if not download_success:
                    all_downloads_successful = False
                    logger.error(f"Failed to download {download_url_to_use}. Aborting downloads for this RPC node.")
                    break # Stop downloading files for this RPC if one fails
                
                # If a full snapshot was just successfully downloaded, update FULL_LOCAL_SNAP_SLOT
                if is_full_snapshot_path and downloaded_fname: # Check if it was a full snapshot and we have a name
                    try:
                        # downloaded_fname is the final name, e.g., SNAPSHOT_PATH_CONFIG/snapshot-SLOT-HASH.tar.zst
                        newly_downloaded_full_slot = int(Path(downloaded_fname).name.split("-")[1])
                        if FULL_LOCAL_SNAP_SLOT != newly_downloaded_full_slot:
                             FULL_LOCAL_SNAP_SLOT = newly_downloaded_full_slot
                             logger.info(f"Successfully downloaded full snapshot. Updated FULL_LOCAL_SNAP_SLOT to: {FULL_LOCAL_SNAP_SLOT}")
                        else:
                             logger.info(f"Successfully re-confirmed/downloaded full snapshot for slot: {FULL_LOCAL_SNAP_SLOT}")
                    except (IndexError, ValueError) as e:
                        logger.warning(f"Could not parse slot from newly downloaded full snapshot {downloaded_fname} to update FULL_LOCAL_SNAP_SLOT: {e}")
            
            if all_downloads_successful and rpc_node_info.get("files_to_download"): # Check if there were files to download
                logger.info(f"All snapshot files downloaded successfully from {snapshot_address}.")
                return 0 # SUCCESS - Exit main_worker after first successful RPC processing
            elif not rpc_node_info.get("files_to_download"):
                 logger.warning(f"No files listed for download from {snapshot_address}, though it passed speed check.")


        logger.error(f'No suitable snapshot server found meeting all criteria (speed, etc.) from the top candidates within this attempt.')
        return 1 # Failure, no server met all criteria or download failed

    except KeyboardInterrupt:
        logger.info('KeyboardInterrupt received, exiting main_worker.')
        # For library, re-raise or handle differently, but for now, let it propagate if not caught by find_snapshot_and_download
        raise 
    except Exception as e:
        logger.error(f'Unexpected error in main_worker: {e}', exc_info=True)
        return 1 # General failure


def run_snap_finder(cluster_arg: str, verbose: bool = False):
    global RPC, SPECIFIC_SLOT_CONFIG, SPECIFIC_VERSION_CONFIG, WILDCARD_VERSION_CONFIG
    global MAX_SNAPSHOT_AGE_IN_SLOTS_CONFIG, WITH_PRIVATE_RPC_CONFIG 
    global THREADS_COUNT_CONFIG, MIN_DOWNLOAD_SPEED_MB_CONFIG, MAX_DOWNLOAD_SPEED_MB_CONFIG
    global SPEED_MEASURE_TIME_SEC_CONFIG, MAX_LATENCY_CONFIG, SNAPSHOT_PATH_CONFIG, SORT_ORDER_CONFIG
    global wget_path, current_slot 

    config = get_config()

    if cluster_arg == "um":
        RPC = "https://api.mainnet-beta.solana.com"
        SNAPSHOT_PATH_CONFIG = config.get("toolkit.snapshot_dir_um")
        if not SNAPSHOT_PATH_CONFIG:
            logger.error("Mainnet snapshot directory 'toolkit.snapshot_dir_um' not found in configuration.")
            return False
    elif cluster_arg == "ut":
        RPC = "https://api.testnet.solana.com"
        SNAPSHOT_PATH_CONFIG = config.get("toolkit.snapshot_dir_ut")
        if not SNAPSHOT_PATH_CONFIG:
            logger.error("Testnet snapshot directory 'toolkit.snapshot_dir_ut' not found in configuration.")
            return False
    else:
        logger.error(f"Invalid cluster argument: {cluster_arg}. Use 'um' for mainnet or 'ut' for testnet.")
        return False
    
    SNAPSHOT_PATH_CONFIG = SNAPSHOT_PATH_CONFIG if not SNAPSHOT_PATH_CONFIG.endswith('/') else SNAPSHOT_PATH_CONFIG[:-1]
    
    THREADS_COUNT_CONFIG = 1000
    SPECIFIC_SLOT_CONFIG = 0 
    SPECIFIC_VERSION_CONFIG = None
    WILDCARD_VERSION_CONFIG = None
    MAX_SNAPSHOT_AGE_IN_SLOTS_CONFIG = 1300
    _initial_with_private_rpc = False 
    WITH_PRIVATE_RPC_CONFIG = _initial_with_private_rpc
    MIN_DOWNLOAD_SPEED_MB_CONFIG = 60
    MAX_DOWNLOAD_SPEED_MB_CONFIG = None
    SPEED_MEASURE_TIME_SEC_CONFIG = 7
    MAX_LATENCY_CONFIG = 100
    SORT_ORDER_CONFIG = 'latency'
    
    _NUM_OF_MAX_ATTEMPTS = 5
    _SLEEP_BEFORE_RETRY = 7

    # Logging Setup
    log_level = logging.DEBUG if verbose else logging.INFO
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True
    )
    logging.getLogger('urllib3').setLevel(logging.WARNING)

    # --- User Confirmation --- 
    separator = "-" * 120
    print(f"{C_CYAN}{separator}{C_NC}")
    print(f"{C_GREEN}THW-NodeKit {C_CYAN}| Snapshot Download (Snapshot Finder){C_NC}")
    print(f"{C_CYAN}{separator}{C_NC}")

    cluster_map = {"um": "Mainnet", "ut": "Testnet"} # Map for display names
    display_cluster_name = cluster_map.get(cluster_arg.lower(), cluster_arg.upper())

    details = {
        "Cluster": display_cluster_name, # Use display name
        "RPC Endpoint": RPC,
        "Download Directory": SNAPSHOT_PATH_CONFIG,
    }
    max_label_len = max(len(k) for k in details.keys())
    padding = max_label_len + 4

    for label, value in details.items():
        print(f"{C_CYAN}{label + ':':<{padding}}{C_NC}{value}")
    
    print(f"{C_CYAN}{separator}{C_NC}")

    try:
        confirm = input(f"{C_GREEN}Proceed with snapshot search and download? (y/n): {C_NC}").strip().lower()
        if confirm != 'y':
            logger.warning("Snapshot finder operation cancelled by user.")
            print(f"{C_YELLOW}Snapshot finder operation cancelled by user.{C_NC}")
            return False # User cancelled
    except EOFError:
        logger.warning("EOFError reading input (non-interactive environment?). Aborting snapshot finder.")
        print(f"{C_YELLOW}Snapshot finder operation aborted due to non-interactive environment.{C_NC}")
        return False # Treat as cancellation
    # --- End User Confirmation ---

    # Moved these log messages to after confirmation, if proceeding
    logger.info(f"Proceeding with Snap Finder for cluster: {cluster_arg.upper()}, Target RPC: {RPC}, Path: {SNAPSHOT_PATH_CONFIG}")
    logger.debug(f"Verbose logging enabled. Using up to {_NUM_OF_MAX_ATTEMPTS} attempts, {_SLEEP_BEFORE_RETRY}s sleep between attempts.")
    logger.debug(f"Scan Params: Threads={THREADS_COUNT_CONFIG}, MaxAgeSlots={MAX_SNAPSHOT_AGE_IN_SLOTS_CONFIG}, MinSpeedMBps={MIN_DOWNLOAD_SPEED_MB_CONFIG}, MaxLatencyMs={MAX_LATENCY_CONFIG}")

    try:
        Path(SNAPSHOT_PATH_CONFIG).mkdir(parents=True, exist_ok=True)
        with open(f'{SNAPSHOT_PATH_CONFIG}/.write_perm_test', 'w') as f_: # Hidden file
            f_.write("test")
        os.remove(f'{SNAPSHOT_PATH_CONFIG}/.write_perm_test')
    except IOError as e:
        logger.error(f"Write permission test failed for '{SNAPSHOT_PATH_CONFIG}': {e}")
        return False

    wget_path_check = shutil.which("wget")
    if wget_path_check is None:
        logger.error("wget utility not found in system PATH. It is required for downloading snapshots.")
        return False
    wget_path = wget_path_check 

    num_attempts_made = 0
    while num_attempts_made < _NUM_OF_MAX_ATTEMPTS:
        num_attempts_made += 1
        logger.info(f"Snapshot search: Attempt {num_attempts_made}/{_NUM_OF_MAX_ATTEMPTS}")

        # Reset per-attempt module-level state variables
        global DISCARDED_BY_ARCHIVE_TYPE, DISCARDED_BY_LATENCY, DISCARDED_BY_SLOT, DISCARDED_BY_VERSION
        global DISCARDED_BY_UNKNW_ERR, DISCARDED_BY_TIMEOUT, FULL_LOCAL_SNAPSHOTS, FULL_LOCAL_SNAP_SLOT
        global unsuitable_servers, json_data, pbar

        DISCARDED_BY_ARCHIVE_TYPE = 0; DISCARDED_BY_LATENCY = 0; DISCARDED_BY_SLOT = 0
        DISCARDED_BY_VERSION = 0; DISCARDED_BY_UNKNW_ERR = 0; DISCARDED_BY_TIMEOUT = 0
        FULL_LOCAL_SNAPSHOTS = []; FULL_LOCAL_SNAP_SLOT = 0
        unsuitable_servers = set()
        json_data = {"rpc_nodes": []} 
        if pbar: pbar.close(); pbar = None


        if SPECIFIC_SLOT_CONFIG != 0:
            current_slot = SPECIFIC_SLOT_CONFIG
        else:
            slot_val = get_current_slot() 
            if slot_val is None:
                logger.warning("Failed to get current slot for this attempt.")
                if num_attempts_made >= _NUM_OF_MAX_ATTEMPTS: break 
                logger.info(f"Sleeping for {_SLEEP_BEFORE_RETRY}s before next attempt to get slot.")
                time.sleep(_SLEEP_BEFORE_RETRY)
                continue 
            current_slot = slot_val

        try:
            worker_result = main_worker() 
        except KeyboardInterrupt:
            logger.info("Operation cancelled by user (KeyboardInterrupt).")
            return False


        if worker_result == 0: 
            logger.info("Snapshot operation completed successfully.")
            print(f"{C_GREEN}Snapshot operation completed successfully.{C_NC}")
            return True
        
        logger.warning(f"Snapshot operation failed on attempt {num_attempts_made}.")
        if not WITH_PRIVATE_RPC_CONFIG and not _initial_with_private_rpc: 
            logger.info("Enabling private RPC search for subsequent attempts.")
            WITH_PRIVATE_RPC_CONFIG = True

        if num_attempts_made >= _NUM_OF_MAX_ATTEMPTS: break

        logger.info(f"Sleeping for {_SLEEP_BEFORE_RETRY}s before next attempt.")
        time.sleep(_SLEEP_BEFORE_RETRY)

    logger.error(f"Failed to find and download a suitable snapshot after {_NUM_OF_MAX_ATTEMPTS} attempts.")
    print(f"{C_BOLD_RED}Failed to find and download a suitable snapshot after {_NUM_OF_MAX_ATTEMPTS} attempts.{C_NC}")
    return False
