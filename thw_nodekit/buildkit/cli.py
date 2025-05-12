"""Command Line Interface for Buildkit."""

import argparse
import logging
import sys
from typing import Optional # Added for type hinting clarity

from thw_nodekit.config import get_config, Config
from thw_nodekit.buildkit.builders import get_builder
from thw_nodekit.buildkit.operations.commands import CommandError

# Configure logging for the buildkit module specifically
logger = logging.getLogger(__name__) # Use __name__ for module-specific logger

def setup_buildkit_parser(parser: argparse.ArgumentParser):
    """Adds buildkit specific arguments to the provided parser."""
    parser.add_argument(
        "client", 
        choices=["agave", "jito", "firedancer"],
        help="The client to build (agave, jito, or firedancer)."
    )
    parser.add_argument(
        "type", 
        choices=["official", "mod"],
        help="The type of repository build (official or mod)."
    )
    parser.add_argument(
        "tag", 
        help="The release tag (e.g., v1.18.2) to build."
    )
    parser.add_argument(
        "update_symlink", 
        choices=["true", "false"],
        help="Whether to update the active_release symlink (true or false)."
    )
    parser.add_argument(
        "build_threads", 
        type=int, 
        nargs='?', # Optional argument
        default=None, # Will be overridden by config default if not provided
        help="Number of parallel build threads (optional, defaults to value in config)."
    )

def run_build(args: argparse.Namespace):
    """Executes the build process based on parsed arguments."""
    
    # Set logging level based on verbosity (assuming --verbose is parsed globally)
    if hasattr(args, 'verbose') and args.verbose:
        # Set level for buildkit's logger and potentially core modules if needed
        logger.setLevel(logging.DEBUG)
        logging.getLogger("thw_nodekit.buildkit.operations").setLevel(logging.DEBUG) 
        logging.getLogger("thw_nodekit.buildkit.builders").setLevel(logging.DEBUG)
        logger.info("Verbose logging enabled for buildkit.")
    else:
        # Ensure buildkit loggers respect INFO level if not verbose
        logger.setLevel(logging.INFO)
        logging.getLogger("thw_nodekit.buildkit.operations").setLevel(logging.INFO)
        logging.getLogger("thw_nodekit.buildkit.builders").setLevel(logging.INFO)


    # Validate tag explicitly - prevents issues later
    if not args.tag:
         # Use logger.error and sys.exit for consistency if main parser isn't used directly
         logger.error("The 'tag' argument cannot be empty. Please provide a valid release tag.")
         sys.exit(1) 

    try:
        # Load configuration (respecting global --config if present)
        config_path = args.config if hasattr(args, 'config') else None
        config = get_config(custom_path=config_path)
        
        # Determine build threads: command line > config > default
        build_threads = args.build_threads if args.build_threads is not None else config.get_build_jobs()
        logger.info(f"Using {build_threads} build threads.")
        
        # Convert update_symlink string to boolean
        update_symlink_bool = args.update_symlink.lower() == 'true'

        # Get the appropriate builder instance
        builder = get_builder(
            config=config,
            client=args.client,
            repo_type=args.type,
            tag=args.tag,
            update_symlink=update_symlink_bool,
            build_threads=build_threads
        )
        
        # Execute the build process (includes confirmation prompt)
        builder.build()
        
        logger.info(f"Build process for {args.client} {args.type} {args.tag} completed successfully.")
        # Let the main CLI handle exit codes if possible, otherwise:
        # sys.exit(0) 
        
    except (ValueError, FileNotFoundError, CommandError) as e:
        logger.error(f"Build failed: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"An unexpected error occurred during build: {e}") # Log traceback 
        sys.exit(2)
        