"""
Main CLI dispatcher for THW-NodeKit.
"""

import sys
import argparse
import logging

# Import buildkit command setup and handler functions
from thw_nodekit.buildkit.cli import setup_buildkit_parser, run_build

# Import toolkit command setup and handler functions
from thw_nodekit.toolkit.cli import (
    setup_affinity_args, handle_affinity_command,
    setup_tvc_args, handle_tvc_command,
    setup_snap_finder_args, handle_snap_finder_command,
    setup_snap_avorio_args, handle_snap_avorio_command,
    setup_symlink_args, handle_symlink_command,
    setup_failover_args, handle_failover_command
)

def main():
    """Main entry point for the unified CLI."""
    parser = argparse.ArgumentParser(
        description="THW-NodeKit - Solana validator tools"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run", required=True)
    
    # Buildkit command
    build_parser = subparsers.add_parser("build", help="Build and install Solana clients")
    setup_buildkit_parser(build_parser)
    
    # Toolkit commands
    affinity_parser = subparsers.add_parser("affinity", help="Manage CPU affinity for the Agave PoH thread.")
    setup_affinity_args(affinity_parser)
    
    tvc_parser = subparsers.add_parser("tvc", help="Track vote credits for a validator.")
    setup_tvc_args(tvc_parser)
    
    # Snapshot command (snap-finder)
    snap_finder_parser = subparsers.add_parser("snap-finder", help="Find and download a Solana snapshot from other nodes in gossip.")
    setup_snap_finder_args(snap_finder_parser)
    
    # Snapshot command (snap-avorio)
    snap_avorio_parser = subparsers.add_parser("snap-avorio", help="Download a Solana snapshot from Avorio network.")
    setup_snap_avorio_args(snap_avorio_parser)

    # Symlink command
    symlink_parser = subparsers.add_parser("symlink", help="Create or update the active_release symlink for a Solana client.")
    setup_symlink_args(symlink_parser)
    
    # Failover command
    failover_parser = subparsers.add_parser("failover", help="Perform an identity swap (failover) between two nodes.")
    setup_failover_args(failover_parser)
    
    # Add common arguments (apply to all commands)
    parser.add_argument("--config", help="Path to a custom TOML configuration file.")
    parser.add_argument("--version", action="store_true", help="Show version and exit.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose (DEBUG level) logging for all modules.")
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', force=True)
    if args.verbose:
        logging.getLogger("thw_nodekit").setLevel(logging.DEBUG)
        
    logger = logging.getLogger("thw_nodekit.cli")
    logger.info(f"Log level set to {logging.getLevelName(log_level)}")

    if args.version:
        from thw_nodekit import __version__
        print(f"THW-NodeKit v{__version__}")
        sys.exit(0)
    
    # Dispatch to appropriate command handler function
    if args.command == "build":
        run_build(args)
    elif args.command == "affinity":
        handle_affinity_command(args)
    elif args.command == "tvc":
        handle_tvc_command(args)
    elif args.command == "snap-finder":
        handle_snap_finder_command(args)
    elif args.command == "snap-avorio":
        handle_snap_avorio_command(args)
    elif args.command == "symlink":
        handle_symlink_command(args)
    elif args.command == "failover":
        handle_failover_command(args)
    else:
        logger.error(f"Unhandled command: {args.command}")
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
