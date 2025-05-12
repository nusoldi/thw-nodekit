"""Firedancer Builder Implementation."""

import logging
import os

from .base import BaseBuilder
from thw_nodekit.buildkit.operations import git, filesystem, commands

logger = logging.getLogger(__name__)

class FiredancerBuilder(BaseBuilder):
    """Builder for Firedancer projects."""

    def _prepare_source(self) -> None:
        # Firedancer source_dir == install_dir
        filesystem.ensure_directory_exists(self.install_dir)

        # 1. Clone the repository with the specific tag and recurse submodules
        git.clone_repo(
            repo_url=self.repo_url,
            target_dir=self.source_dir, # source_dir is install_dir here
            branch=self.tag, # Clone the specific tag
            recurse_submodules=True # Script uses it on clone
        )

        # 2. Checkout tag only if it's an 'official' build
        if self.repo_type == "official":
            logger.info("Official build detected, checking out specific tag...")
            git.checkout_tag(repo_path=self.source_dir, tag=self.tag)
        else:
            logger.info("Mod build detected, skipping explicit tag checkout (assuming correct branch/tag was cloned or is default).")

        # Run dependencies script
        deps_script_path = os.path.join(self.source_dir, "deps.sh")
        if not os.path.exists(deps_script_path):
            raise FileNotFoundError(f"Dependencies script not found: {deps_script_path}")

        logger.info("Running Firedancer dependencies script (deps.sh) with 'yes y |'...")
        commands.run_yes_pipe(
            command=["bash", deps_script_path],
            cwd=self.source_dir
        )

    def _compile(self) -> None:
        logger.info(f"Compiling Firedancer using 'make -j{self.build_threads} fdctl solana'...")
        commands.run_make(
            cwd=self.source_dir,
            jobs=self.build_threads,
            targets=["fdctl", "solana"]
        )

    def _install(self) -> None:
        # Firedancer compiles directly into the target structure within install_dir
        logger.info("Install step is integrated with compile for Firedancer.")
        pass

    def _get_binary_path(self, name: str) -> str:
        # Construct the expected path based on symlink_subpath logic
        # config.get_symlink_target already calculates install_dir + subpath
        # The actual binaries are usually in a 'bin' subdir relative to the target
        base_path = self.symlink_target # This is install_dir/build/native/gcc for Firedancer
        return os.path.join(base_path, "bin", name)

    def _verify_install(self) -> None:
        solana_executable = self._get_binary_path("solana")
        fdctl_executable = self._get_binary_path("fdctl")

        if not os.path.exists(solana_executable):
             raise FileNotFoundError(f"Solana executable not found after install: {solana_executable}")
        if not os.path.exists(fdctl_executable):
             raise FileNotFoundError(f"Fdctl executable not found after install: {fdctl_executable}")

        logger.info(f"Checking installed Solana version at: {solana_executable}")
        solana_version = commands.get_solana_version(executable_path=solana_executable)
        logger.info(f"Output of {solana_executable} --version: {solana_version}")
        # Firedancer versioning might be complex, just log for now
        # if self.tag not in solana_version:
        #     logger.warning(f"Installed Solana version '{solana_version}' may not match tag '{self.tag}'. Check manually.")

        logger.info(f"Checking installed Fdctl version at: {fdctl_executable}")
        fdctl_version = commands.get_fdctl_version(executable_path=fdctl_executable)
        logger.info(f"Output of {fdctl_executable} version: {fdctl_version}")
        # if self.tag not in fdctl_version:
        #     logger.warning(f"Installed Fdctl version '{fdctl_version}' may not match tag '{self.tag}'. Check manually.")

    def _verify_symlink(self) -> None:
        logger.info("Checking Solana/Fdctl versions using system path (via active_release symlink if updated)...")
        solana_version = commands.get_solana_version()
        logger.info(f"Output of solana --version: {solana_version}")
        fdctl_version = commands.get_fdctl_version()
        logger.info(f"Output of fdctl version: {fdctl_version}") 