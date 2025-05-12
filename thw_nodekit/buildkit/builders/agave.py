"""Agave Builder Implementation."""

import logging
import os

from .base import BaseBuilder
from thw_nodekit.buildkit.operations import git, filesystem, commands

logger = logging.getLogger(__name__)

class AgaveBuilder(BaseBuilder):
    """Builder for Agave projects."""

    def _prepare_source(self) -> None:
        # Ensure source and install directories exist
        filesystem.ensure_directory_exists(self.source_dir)
        filesystem.ensure_directory_exists(self.install_dir)

        # 1. Clone the repository with the specific tag and recurse submodules
        git.clone_repo(
            repo_url=self.repo_url,
            target_dir=self.source_dir,
            branch=self.tag, # Clone the specific tag
            recurse_submodules=True # Recurse submodules during clone
        )
        
        # 2. Checkout the specific tag (explicitly, matching docs sequence after cd)
        git.checkout_tag(repo_path=self.source_dir, tag=self.tag)
        
        # 3. Update submodules explicitly
        git.update_submodules(repo_path=self.source_dir)
        
    def _compile(self) -> None:
        # Agave/Jito combine compile and install in the cargo-install-all script
        logger.info("Compile step handled by _install for Agave.")
        pass

    def _install(self) -> None:
        script_path = os.path.join(self.source_dir, "scripts", "cargo-install-all.sh")
        if not os.path.exists(script_path):
            raise FileNotFoundError(f"Installation script not found: {script_path}")
            
        # Get commit hash for CI_COMMIT env var, mimicking the script
        try:
             commit_hash = git.get_commit_hash(self.source_dir)
             install_env = self.build_env.copy()
             install_env['CI_COMMIT'] = commit_hash
             logger.info(f"Using CI_COMMIT={commit_hash} for installation script.")
        except Exception as e:
             logger.warning(f"Could not get commit hash from {self.source_dir}: {e}. Proceeding without CI_COMMIT env var.")
             install_env = self.build_env

        # Run the installation script, passing the install directory
        logger.info("Running cargo-install-all.sh (output will stream below...)")
        commands.run_script(
            script_path=script_path,
            args=[self.install_dir],
            cwd=self.source_dir, # Run script from source dir
            env=install_env,
            check=True, # Raise error if script fails
            stream_output=True # Stream output to terminal
        )

    def _verify_install(self) -> None:
        solana_executable = os.path.join(self.install_dir, "bin", "solana")
        validator_executable = os.path.join(self.install_dir, "bin", "agave-validator")
        
        # Verify Solana executable exists and get version
        if not os.path.exists(solana_executable):
             raise FileNotFoundError(f"Solana executable not found after install: {solana_executable}")
        
        logger.info(f"Checking installed Solana version at: {solana_executable}")
        solana_version_output = commands.get_solana_version(executable_path=solana_executable)
        logger.info(f"Version reported by {solana_executable}: {solana_version_output}")

        # Verify Agave Validator executable exists and get version
        if not os.path.exists(validator_executable):
            raise FileNotFoundError(f"Agave Validator executable not found after install: {validator_executable}")

        logger.info(f"Checking installed Agave Validator version at: {validator_executable}")
        validator_version_output = commands.get_agave_validator_version(executable_path=validator_executable)
        logger.info(f"Version reported by {validator_executable}: {validator_version_output}")

    def _verify_symlink(self) -> None:
        logger.info("Checking Solana version using system path (via active_release symlink if updated)...")
        solana_version_output = commands.get_solana_version() # Uses default 'solana' command
        logger.info(f"Version reported by system 'solana': {solana_version_output}")
        logger.info("Checking Agave Validator version using system path...")
        validator_version_output = commands.get_agave_validator_version() # Uses default 'agave-validator' command
        logger.info(f"Version reported by system 'agave-validator': {validator_version_output}")