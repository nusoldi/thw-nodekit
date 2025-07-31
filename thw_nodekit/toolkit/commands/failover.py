#!/usr/bin/env python3

import os
import sys
import time
import platform
import subprocess
from datetime import datetime
import logging
from typing import Optional, Dict, Any

from thw_nodekit.config import get_config

# --- ANSI Color Codes ---
# Preserving the exact codes from the original script for visual consistency.
C_BLUE = "\033[94m"
C_GREEN = "\033[1;32m"
C_YELLOW = "\033[1;33m"
C_CYAN = "\033[1;36m"
C_RED = "\033[0;31m"
C_NC = "\033[0m" # No Color

logger = logging.getLogger(__name__)

# --- Logging and Output Functions ---

def log_msg(level, message):
    """Prints a formatted and colored log message."""
    colors = {
        "INFO": C_BLUE,
        "SUCCESS": C_GREEN,
        "WARN": C_YELLOW,
        "ERROR": C_RED,
    }
    color = colors.get(level, C_NC)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    # Use print directly to ensure ANSI codes are rendered without Rich mangling
    print(f"{color}[{timestamp}] {level}:{C_NC} {message}")


def print_header(title):
    """Prints a consistent, formatted header."""
    separator = "-" * 120
    print(f"{C_CYAN}{separator}{C_NC}")
    print(f"{C_GREEN}THW-NodeKit {C_CYAN}| Agave Identity Swap (Failover):{C_NC} {C_YELLOW}{title}{C_NC}")
    print(f"{C_CYAN}{separator}{C_NC}")


def format_duration(duration_s):
    """Formats a duration in seconds into a human-readable string."""
    ms = duration_s * 1000
    return f"{duration_s:.4f} seconds ({ms:.0f} ms)."

# --- Core Logic Functions ---

def load_configuration(from_host, to_host, cluster, config_path):
    """
    Loads configurations from the main config and builds the failover context.
    """
    try:
        full_config = get_config(custom_path=config_path)
    except FileNotFoundError:
        log_msg("ERROR", "Could not load configuration.")
        return None

    try:
        local_conf = full_config.get(f"{from_host}.{cluster}")
        remote_conf = full_config.get(f"{to_host}.{cluster}")
        if not local_conf or not remote_conf:
             raise KeyError
    except KeyError:
        log_msg("ERROR", f"Configuration error. Could not find host or cluster in config.")
        log_msg("ERROR", f"Please ensure an entry for '[{from_host}.{cluster}]' and '[{to_host}.{cluster}]' exists.")
        return None

    config = {
        "from_host": from_host,
        "to_host": to_host,
        "cluster": cluster,
        "local": local_conf,
        "remote": remote_conf,
    }
    return config


def run_shell_command(command: list, description: str, hide_output: bool = False, is_shell_cmd: bool = False, capture_stdout: bool = False) -> subprocess.CompletedProcess:
    """
    Runs a shell command and handles logging and errors.
    If is_shell_cmd is True, 'command' should be a string.
    """
    if description:
        log_msg("INFO", description)

    try:
        # If hiding output, both pipes go to DEVNULL.
        # If capturing stdout, stdout goes to PIPE, stderr streams.
        # Otherwise, both stream.
        stdout_pipe = subprocess.PIPE if hide_output or capture_stdout else None
        stderr_pipe = subprocess.PIPE if hide_output else None
        result = subprocess.run(command, shell=is_shell_cmd, check=True, text=True, stdout=stdout_pipe, stderr=stderr_pipe)
        return result
    except subprocess.CalledProcessError as e:
        cmd_str = command if is_shell_cmd else ' '.join(command)
        log_msg("ERROR", f"Failed to execute: {cmd_str}")
        if e.stderr:
            log_msg("ERROR", f"Stderr: {e.stderr.strip()}")
        log_msg("ERROR", "Aborting failover due to local command failure.")
        sys.exit(1)
    except Exception as e:
        log_msg("ERROR", f"An unexpected error occurred running command: {e}")
        sys.exit(1)


def run_pre_flight_checks(from_host, local_config, remote_config):
    """Performs a series of checks on local and remote systems before proceeding."""
    print_header("Pre-Flight Checks")
    errors = False

    ssh_opts = f"-i {local_config['ssh_key_path']} -o ConnectTimeout=5 -o 'ControlMaster=auto' -o 'ControlPath=/tmp/ssh-%r@%h:%p' -o 'ControlPersist=yes'"
    ssh_host_str = f"{remote_config['user']}@{remote_config['ip']}"
    ssh_cmd_prefix = f"ssh {ssh_opts} {ssh_host_str}"

    # 1. Hostname Verification
    log_msg("INFO", f"Checking: Script is running on the correct host ({C_BLUE}{from_host}{C_NC})...")
    current_hostname = platform.node()
    if current_hostname != from_host:
        log_msg("ERROR", f"This script is running on '{current_hostname}', but the failover is FROM '{C_BLUE}{from_host}{C_NC}'.")
        log_msg("ERROR", f"Please run this script on {C_BLUE}{from_host}{C_NC} to proceed. Aborting.")
        sys.exit(1)
    log_msg("SUCCESS", "OK: Script is running on the correct source host.")

    # 2. Local File/Binary Checks
    log_msg("INFO", f"--- Verifying local node ({C_BLUE}{from_host}{C_NC}) ---")
    local_checks = {
        f"Local ledger path ({local_config['ledger_path']})": (os.path.isdir, local_config['ledger_path']),
        f"Local unstaked keypair ({local_config['unstaked_keypair']})": (os.path.isfile, local_config['unstaked_keypair']),
        f"Local validator keypair ({local_config['validator_keypair']})": (os.path.isfile, local_config['validator_keypair']),
        f"SSH key ({local_config['ssh_key_path']})": (os.path.isfile, local_config['ssh_key_path']),
        "agave-validator executable": (os.access, os.path.join(local_config['solana_path'], "agave-validator"), os.X_OK),
        "solana-keygen executable": (os.access, os.path.join(local_config['solana_path'], "solana-keygen"), os.X_OK),
    }
    for desc, check in local_checks.items():
        log_msg("INFO", f"Checking: {desc}...")
        try:
            if check[0](*check[1:]):
                log_msg("SUCCESS", f"OK: {desc} check passed")
            else:
                raise FileNotFoundError
        except (FileNotFoundError, PermissionError):
            log_msg("ERROR", f"FAILED: {desc} check failed")
            errors = True

    # 3. Remote File/Binary Checks
    log_msg("INFO", f"--- Verifying remote node ({C_GREEN}{remote_config['hostname']}{C_NC}) ---")
    remote_checks = {
        f"Remote ledger path ({remote_config['ledger_path']})": f"[ -d '{remote_config['ledger_path']}' ]",
        f"Remote validator keypair ({remote_config['validator_keypair']})": f"[ -f '{remote_config['validator_keypair']}' ]",
        "Remote agave-validator executable": f"[ -x '{os.path.join(remote_config['solana_path'], 'agave-validator')}' ]",
        "Remote solana-keygen executable": f"[ -x '{os.path.join(remote_config['solana_path'], 'solana-keygen')}' ]",
    }
    for desc, cmd in remote_checks.items():
        log_msg("INFO", f"Checking: {desc}...")
        full_ssh_cmd = f"{ssh_cmd_prefix} \"{cmd}\""
        result = subprocess.run(full_ssh_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode == 0:
            log_msg("SUCCESS", f"OK: {desc} check passed")
        else:
            log_msg("ERROR", f"FAILED: {desc} check failed")
            errors = True

    if errors:
        log_msg("ERROR", "Pre-flight checks failed. Please review the errors above. Aborting.")
        sys.exit(1)

    # 4. Remote Tower Check
    log_msg("INFO", "Checking: Existing tower on remote node...")
    pubkey_cmd = f"{os.path.join(remote_config['solana_path'], 'solana-keygen')} pubkey {remote_config['validator_keypair']}"
    
    remote_pubkey_result = subprocess.run(f"{ssh_cmd_prefix} \"{pubkey_cmd}\"", shell=True, capture_output=True, text=True)
    if remote_pubkey_result.returncode != 0:
        log_msg("ERROR", f"Could not get remote validator pubkey: {remote_pubkey_result.stderr}")
        sys.exit(1)
        
    remote_validator_pubkey = remote_pubkey_result.stdout.strip()
    remote_tower_filename = f"tower-1_9-{remote_validator_pubkey}.bin"
    remote_tower_check_path = os.path.join(remote_config['ledger_path'], remote_tower_filename)
    
    tower_check_cmd = f"[ -f '{remote_tower_check_path}' ]"
    full_ssh_tower_check_cmd = f"{ssh_cmd_prefix} \"{tower_check_cmd}\""
    result = subprocess.run(full_ssh_tower_check_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if result.returncode == 0:
        log_msg("SUCCESS", "OK: Existing tower found on remote. Will use --require-tower.")
        remote_config['require_tower_flag'] = "--require-tower"
    else:
        log_msg("WARN", "No existing tower for main identity found on remote node. A new tower will be initialized.")
        remote_config['require_tower_flag'] = ""


def get_tower_paths(local_config, remote_config):
    """Determines the full local and remote paths for the tower file."""
    # We only need the local validator's pubkey to determine the tower filename.
    pubkey_cmd = [os.path.join(local_config['solana_path'], 'solana-keygen'), 'pubkey', local_config['validator_keypair']]
    try:
        # We need to run this locally to get the pubkey for the filename.
        local_validator_pubkey = run_shell_command(pubkey_cmd, "", hide_output=True).stdout.strip()
        tower_filename = f"tower-1_9-{local_validator_pubkey}.bin"
        
        local_tower_path = os.path.join(local_config['ledger_path'], tower_filename)
        remote_tower_path = os.path.join(remote_config['tower_path_dir'], tower_filename)

        # Add these paths to the config dictionaries for later use.
        local_config['tower_path'] = local_tower_path
        remote_config['tower_path'] = remote_tower_path
    except Exception as e:
        log_msg("ERROR", f"Could not determine tower path: {e}")
        sys.exit(1)


def display_confirmation_prompt(from_host, to_host, cluster, local_config, remote_config):
    """Displays the planned actions and asks for user confirmation."""
    print_header("Confirmation")
    print(f"FROM (Local/Active):   {C_BLUE}{from_host}{C_NC}")
    print(f"TO (Remote/Inactive):  {C_GREEN}{to_host}{C_NC}")
    print(f"CLUSTER:               {C_YELLOW}{cluster}{C_NC}")

    print(C_CYAN + "------------------------------------------------------------------------------------------------------------------------")
    print(f"{C_CYAN}Actions on LOCAL node {C_BLUE}({from_host}){C_NC}:")
    print(C_CYAN + "------------------------------------------------------------------------------------------------------------------------")
    print(f"{C_CYAN}(1). Change Identity to {C_BLUE}JUNK{C_NC}{C_CYAN}:{C_NC}")
    print(f"---> {local_config['solana_path']}agave-validator --ledger {local_config['ledger_path']} set-identity {local_config['unstaked_keypair']}")
    print(f"{C_CYAN}(2). Transfer Tower File:{C_NC}")
    print(f"---> cat {local_config.get('tower_path', '[local_tower_path]')} | ssh ... | dd of={remote_config.get('tower_path', '[remote_tower_path]')}")

    print(C_CYAN + "------------------------------------------------------------------------------------------------------------------------")
    print(f"{C_CYAN}Actions on REMOTE node {C_GREEN}({to_host}){C_NC}:")
    print(C_CYAN + "------------------------------------------------------------------------------------------------------------------------")
    print(f"{C_CYAN}(1). Change Identity to {C_GREEN}VALIDATOR{C_NC}{C_CYAN}:{C_NC}")
    print(f"---> {remote_config['solana_path']}agave-validator --ledger {remote_config['ledger_path']} set-identity {remote_config['require_tower_flag']} {remote_config['validator_keypair']}")
    print(C_CYAN + "------------------------------------------------------------------------------------------------------------------------")
    
    try:
        # Replicating confirmation from buildkit
        prompt_text = f"{C_GREEN}Proceed with this failover? (y/N): {C_NC}"
        confirm = input(prompt_text)
        if confirm.lower() != 'y':
            log_msg("WARN", "Failover aborted by user.")
            sys.exit(0) # Exit gracefully
    except (EOFError, KeyboardInterrupt):
        log_msg("WARN", "Failover aborted by user.")
        sys.exit(0)


def execute_failover(from_host, to_host, local_config, remote_config):
    """Executes the core failover logic."""
    print_header("Execution")
    timings = {}

    # --- Start Failover ---
    overall_start_time = time.monotonic()

    # 1. Wait for restart window
    cmd_list = [os.path.join(local_config['solana_path'], 'agave-validator'), '--ledger', local_config['ledger_path'], 'wait-for-restart-window', '--min-idle-time', '2', '--skip-new-snapshot-check']
    run_shell_command(cmd_list, "Waiting for restart window...")

    # Record start of critical failover window HERE, before any identity changes.
    failover_start_time = time.monotonic()

    # 2. Set local identity to junk
    local_id_start = time.monotonic()
    cmd_list = [os.path.join(local_config['solana_path'], 'agave-validator'), '--ledger', local_config['ledger_path'], 'set-identity', local_config['unstaked_keypair']]
    run_shell_command(cmd_list, f"Changing identity on local node ({C_BLUE}{from_host}{C_NC})...")
    timings['local_id_change'] = time.monotonic() - local_id_start

    # 4. OPTIMIZATION: Combine tower transfer and remote commands into a single, pipelined SSH execution.
    ssh_opts = f"-i {local_config['ssh_key_path']} -o 'ControlMaster=auto' -o 'ControlPath=/tmp/ssh-%r@%h:%p' -o 'ControlPersist=yes'"
    ssh_host_str = f"{remote_config['user']}@{remote_config['ip']}"

    pipelined_total_start = time.monotonic()

    remote_set_id_cmd = f"{os.path.join(remote_config['solana_path'], 'agave-validator')} --ledger {remote_config['ledger_path']} set-identity {remote_config['require_tower_flag']} {remote_config['validator_keypair']}"

    # Chain the commands. `dd` reads from stdin until EOF, then the shell executes the rest via `&&`.
    # `set -ex` ensures that the script will exit immediately if any command fails.
    chained_remote_cmds = f"dd of={remote_config['tower_path']} && set -ex; {remote_set_id_cmd};"

    transfer_and_exec_cmd = f"cat {local_config['tower_path']} | ssh {ssh_opts} {ssh_host_str} \"{chained_remote_cmds}\""

    # Execute the entire pipeline. We no longer capture stdout.
    run_shell_command(transfer_and_exec_cmd, f"Executing tower transfer and remote commands on {C_GREEN}{to_host}{C_NC}...", is_shell_cmd=True)
    timings['pipelined_total_duration'] = time.monotonic() - pipelined_total_start

    # Record end of critical failover window
    failover_end_time = time.monotonic()
    timings['critical_failover_window'] = failover_end_time - failover_start_time
    
    log_msg("SUCCESS", f"Failover actions complete. ({C_BLUE}{from_host}{C_NC} is now inactive, {C_GREEN}{to_host}{C_NC} is now active.)")
    # Return the timings dict and the overall start time for the final calculation
    return timings, overall_start_time


def run_verification(from_host, to_host, local_config, remote_config):
    """Performs post-failover checks to verify identity changes."""
    print_header("Verification")
    verification_start_time = time.monotonic()

    # Common SSH options for verification commands
    ssh_opts = f"-i {local_config['ssh_key_path']} -o 'ControlMaster=auto' -o 'ControlPath=/tmp/ssh-%r@%h:%p' -o 'ControlPersist=yes'"
    ssh_host_str = f"{remote_config['user']}@{remote_config['ip']}"

    # Local Verification
    log_msg("INFO", f"--- Verifying identity on LOCAL node ({C_BLUE}{from_host}{C_NC}) ---")
    
    local_grep_cmd1 = f"grep 'Identity set to' \"{local_config['agave_log']}\" | tail -n 1 || true"
    run_shell_command(local_grep_cmd1,f"Searching for last 'Identity set to' in {local_config['agave_log']}...", is_shell_cmd=True)
    
    local_grep_cmd2 = f"grep 'Identity changed' \"{local_config['agave_log']}\" | tail -n 1 || true"
    run_shell_command(local_grep_cmd2,f"Searching for last 'Identity changed' in {local_config['agave_log']}...", is_shell_cmd=True)
    
    local_verify_cmd_str = f"{os.path.join(local_config['solana_path'], 'agave-validator')} --ledger {local_config['ledger_path']} contact-info | grep 'Identity:'"
    run_shell_command(local_verify_cmd_str, "Querying local validator contact info...", is_shell_cmd=True)
    
    # Remote Verification
    log_msg("INFO", f"--- Verifying identity on REMOTE node ({C_GREEN}{to_host}{C_NC}) ---")
    
    remote_grep_cmd1 = f"ssh {ssh_opts} {ssh_host_str} \"grep 'Identity set to' '{remote_config['agave_log']}' | tail -n 1 || true\""
    run_shell_command(remote_grep_cmd1,f"Searching for last 'Identity set to' in {remote_config['agave_log']}...", is_shell_cmd=True)
    
    remote_grep_cmd2 = f"ssh {ssh_opts} {ssh_host_str} \"grep 'Identity changed' '{remote_config['agave_log']}' | tail -n 1 || true\""
    run_shell_command(remote_grep_cmd2,f"Searching for last 'Identity changed' in {remote_config['agave_log']}...", is_shell_cmd=True)
    
    remote_verify_cmd_str = f"{os.path.join(remote_config['solana_path'], 'agave-validator')} --ledger {remote_config['ledger_path']} contact-info | grep 'Identity:'"
    full_remote_verify_cmd = f"ssh {ssh_opts} {ssh_host_str} \"{remote_verify_cmd_str}\""
    run_shell_command(full_remote_verify_cmd, "Querying remote validator contact info...", is_shell_cmd=True)

    return time.monotonic() - verification_start_time


def print_summary(timings):
    """Prints a summary of the timing for each step of the failover."""
    print_header("Summary")
    log_msg("INFO", f"(1). Local Identity Change:                 {format_duration(timings.get('local_id_change', 0))}")
    log_msg("INFO", f"(2). Tower Transfer & Remote Commands:      {format_duration(timings.get('pipelined_total_duration', 0))}")
    log_msg("INFO", f"(3). Critical Failover Window (1-2):        {format_duration(timings.get('critical_failover_window', 0))}")
    log_msg("INFO", f"(4). Verification Phase:                    {format_duration(timings.get('verification', 0))}")
    log_msg("INFO", f"(5). Total Script Execution Time (1-5):     {format_duration(timings.get('total_duration', 0))}")
    log_msg("SUCCESS", "Identity Swap Complete")


def manage_failover(from_host: str, to_host: str, cluster: str, config_path: Optional[str] = None) -> bool:
    """
    Main entry point for orchestrating a validator failover.
    """
    log_msg("INFO", f"Starting configuration for {C_BLUE}{from_host}{C_NC} -> {C_GREEN}{to_host}{C_NC} failover on '{C_YELLOW}{cluster}{C_NC}' cluster.")
    config = load_configuration(from_host, to_host, cluster, config_path)
    if not config:
        return False

    master_conn_established = False
    try:
        # Establish the persistent SSH master connection for speed.
        ssh_host_str = f"{config['remote']['user']}@{config['remote']['ip']}"
        master_cmd_list = [
            'ssh',
            '-i', config['local']['ssh_key_path'],
            '-o', 'ControlMaster=auto',
            '-o', f"ControlPath=/tmp/ssh-%r@%h:%p",
            '-o', 'ControlPersist=yes',
            '-M', '-f', '-N', ssh_host_str
        ]
        run_shell_command(master_cmd_list, "Establishing persistent SSH connection...", hide_output=True)
        master_conn_established = True

        get_tower_paths(config['local'], config['remote'])
        run_pre_flight_checks(from_host=config['from_host'], local_config=config['local'], remote_config=config['remote'])
        display_confirmation_prompt(from_host=config['from_host'], to_host=config['to_host'], cluster=config['cluster'], local_config=config['local'], remote_config=config['remote'])
        
        timings, overall_start_time = execute_failover(from_host=config['from_host'], to_host=config['to_host'], local_config=config['local'], remote_config=config['remote'])
        
        verification_duration = run_verification(from_host=config['from_host'], to_host=config['to_host'], local_config=config['local'], remote_config=config['remote'])
        timings['verification'] = verification_duration

        # Finalize timing calculations now that all steps are complete.
        timings['total_duration'] = time.monotonic() - overall_start_time
        print_summary(timings)
        return True

    except Exception as e:
        log_msg("ERROR", f"An unexpected error occurred: {e}")
        log_msg("ERROR", "Failover may be in an inconsistent state. Manual review is required.")
        return False
    finally:
        # Ensure the persistent SSH connection is terminated on script exit.
        if master_conn_established:
            log_msg("INFO", "Closing persistent SSH connection")
            ssh_host_str = f"{config['remote']['user']}@{config['remote']['ip']}"
            teardown_cmd_list = [
                'ssh',
                '-o', f"ControlPath=/tmp/ssh-%r@%h:%p",
                '-O', 'exit',
                ssh_host_str
            ]
            subprocess.run(teardown_cmd_list, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) 