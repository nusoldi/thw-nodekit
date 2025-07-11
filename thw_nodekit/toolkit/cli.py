"""CLI interface for the Toolkit component."""

import argparse
from typing import Any
import sys # For sys.exit

# --- Affinity Command ---
def setup_affinity_args(parser: argparse.ArgumentParser):
    """Set up arguments for the 'affinity' command."""
    parser.add_argument("--core", type=int, help="CPU core to set solPohTickProd affinity to (overrides config's toolkit.poh_core). Optional.")

def handle_affinity_command(args: Any):
    """Handle the 'affinity' command."""
    from thw_nodekit.toolkit.commands.affinity import manage_affinity
    manage_affinity(
        core_override=args.core
        # config_path is implicitly handled by get_config() in manage_affinity
    )

# --- TVC Command ---
def setup_tvc_args(parser: argparse.ArgumentParser):
    """Set up arguments for the 'tvc' command."""
    parser.add_argument("cluster", choices=["um", "ut"], help="Cluster to use (um=mainnet, ut=testnet)")
    parser.add_argument("identity", nargs="?", help="Validator identity public key (optional, uses config default if not provided)")
    parser.add_argument("--interval", "-i", type=float, default=1.0, help="Display refresh interval in seconds (how often the UI updates)")

def handle_tvc_command(args: Any):
    """Handle the 'tvc' command."""
    from thw_nodekit.toolkit.monitors.tvc_tracker import monitor_tvc
    monitor_tvc(
        identity=args.identity,
        interval=args.interval,
        cluster=args.cluster,
        config_path=args.config if hasattr(args, "config") else None
    )

# --- Snapshot Command (snap-finder) ---
def setup_snap_finder_args(parser: argparse.ArgumentParser):
    """Set up arguments for the 'snap-finder' command."""
    parser.add_argument("cluster", choices=["um", "ut"], help="Cluster to find snapshot for (um=mainnet, ut=testnet)")

def handle_snap_finder_command(args: Any):
    """Handle the 'snap-finder' command."""
    from thw_nodekit.toolkit.commands.snap_finder import run_snap_finder # Updated import
    success = run_snap_finder(
        cluster_arg=args.cluster,
        verbose=args.verbose # Pass verbose from root parser
    )
    if not success:
        sys.exit(1) # Exit with error code if snapshot operation failed

# --- Snapshot Command (snap-avorio) ---
def setup_snap_avorio_args(parser: argparse.ArgumentParser):
    """Set up arguments for the 'snap-avorio' command."""
    parser.add_argument("cluster", choices=["um", "ut"], help="Cluster to download snapshot for (um=mainnet, ut=testnet)")
    parser.add_argument("snap_type", choices=["full", "incr", "both"], help="Type of snapshot to download (full, incr, or both)")

def handle_snap_avorio_command(args: Any):
    """Handle the 'snap-avorio' command."""
    from thw_nodekit.toolkit.commands.snap_avorio import download_snapshot
    success = download_snapshot(
        cluster=args.cluster,
        snap_type=args.snap_type
    )
    if not success:
        sys.exit(1) # Exit with error code if snapshot operation failed

# --- Symlink Command ---
def setup_symlink_args(parser: argparse.ArgumentParser):
    """Set up arguments for the 'symlink' command."""
    parser.add_argument("client", choices=["agave", "jito", "firedancer"], help="The client to symlink (agave, jito, or firedancer).")
    parser.add_argument("tag", help="The release tag (e.g., v1.18.2) to symlink.")

def handle_symlink_command(args: Any):
    """Handle the 'symlink' command."""
    from thw_nodekit.toolkit.commands.symlink import manage_symlink
    success = manage_symlink(
        client=args.client,
        tag=args.tag,
        config_path=args.config if hasattr(args, "config") else None
    )
    if not success:
        # The manage_symlink function logs errors but may return True if user aborts.
        # Only exit if it explicitly returns False indicating a script failure.
        sys.exit(1)

# --- Failover Command ---
def setup_failover_args(parser: argparse.ArgumentParser):
    """Set up arguments for the 'failover' command."""
    parser.add_argument("from_host", help="The hostname of the currently ACTIVE (local) node.")
    parser.add_argument("to_host", help="The hostname of the INACTIVE (remote) node.")
    parser.add_argument("cluster", choices=["mainnet", "testnet"], help="The cluster context for the failover.")

def handle_failover_command(args: Any):
    """Handle the 'failover' command."""
    from thw_nodekit.toolkit.commands.failover import manage_failover
    success = manage_failover(
        from_host=args.from_host,
        to_host=args.to_host,
        cluster=args.cluster,
        config_path=args.config if hasattr(args, "config") else None
    )
    if not success:
        sys.exit(1)
