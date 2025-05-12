"""Abstract Base Class for Buildkit builders."""

import abc
import logging
import os
from typing import Dict, Any, Optional

from thw_nodekit.config import Config
from thw_nodekit.buildkit.operations import git, filesystem, commands

logger = logging.getLogger(__name__)

class BaseBuilder(abc.ABC):
    """Abstract Base Class for project builders."""

    def __init__(
        self,
        config: Config,
        client: str,
        repo_type: str, # e.g., 'official' or 'mod'
        tag: str,
        update_symlink: bool,
        build_threads: int
    ):
        self.config = config
        self.client = client
        self.repo_type = repo_type
        self.tag = tag
        self.update_symlink = update_symlink
        self.build_threads = build_threads

        # Derive configuration values
        self.repo_url = config.get_repo_url(client, repo_type)
        if not self.repo_url:
            raise ValueError(f"Repository URL not found for {client}-{repo_type}")
        
        self.install_dir = config.get_install_dir(client, tag)
        self.source_dir = config.get_source_dir(client, tag) # Handles Firedancer vs others
        self.symlink_path = config.get_symlink_path()
        self.symlink_target = config.get_symlink_target(client, tag) # Handles Firedancer vs others
        self.build_env = {"CARGO_BUILD_JOBS": str(build_threads)}

    def _log_step_start(self, step_number: int, description: str):
        """Logs the start of a build step."""
        logger.info(f"--- Build Step {step_number}: {description} ---")

    def _log_step_end(self, step_number: int, success: bool = True):
        """Logs the end of a build step."""
        status = "COMPLETED" if success else "FAILED"
        log_level = logging.INFO if success else logging.ERROR
        logger.log(log_level, f"--- Build Step {step_number} {status} ---")

    def _user_confirmation(self) -> bool:
        """Display build details and prompt user for confirmation with aligned output."""
        # Determine max label length for alignment
        labels = [
            "Client:", "Type:", "Release Tag:", "Repository:", 
            "Source Directory:", "Install Directory:", "Build Threads:",
            "Symlink Update:", "Symlink Path:", "Symlink Target:"
        ]
        max_label_len = max(len(label) for label in labels)
        padding = max_label_len + 2 # Add 2 for spacing
        # ANSI Color Codes
        COLOR_BOLD_GREEN = "\033[1;32m"
        COLOR_BRIGHT_CYAN = "\033[1;36m"
        COLOR_YELLOW = "\033[1;33m" # For the warning
        COLOR_RESET = "\033[0m"

        # Define labels and calculate padding based on uncolored labels
        labels = {
            "Client:": self.client,
            "Type:": self.repo_type,
            "Release Tag:": self.tag,
            "Repository:": self.repo_url,
            "Source Directory:": self.source_dir,
            "Install Directory:": self.install_dir,
            "Build Threads:": self.build_threads,
            "Symlink Update:": "ENABLED" if self.update_symlink else "DISABLED",
        }
        if self.update_symlink:
            labels["Symlink Path:"] = self.symlink_path
            labels["Symlink Target:"] = self.symlink_target
            
        max_label_len = max(len(label) for label in labels.keys())
        padding = max_label_len + 4 # Add 4 for spacing

        separator = "-" * 120 # Adjusted separator length slightly

        print(f"{COLOR_BRIGHT_CYAN}{separator}{COLOR_RESET}")
        print(f"{COLOR_BOLD_GREEN}THW-NodeKit {COLOR_BRIGHT_CYAN}| Solana Client Buildkit{COLOR_RESET}")
        print(f"{COLOR_BRIGHT_CYAN}{separator}{COLOR_RESET}")

        # Print details with colored labels
        print(f"{COLOR_BRIGHT_CYAN}{'Client:':<{padding}}{COLOR_RESET}{self.client}")
        print(f"{COLOR_BRIGHT_CYAN}{'Type:':<{padding}}{COLOR_RESET}{self.repo_type}")
        print(f"{COLOR_BRIGHT_CYAN}{'Release TAG:':<{padding}}{COLOR_RESET}{self.tag}")
        print(f"{COLOR_BRIGHT_CYAN}{'Repository:':<{padding}}{COLOR_RESET}{self.repo_url}")
        print(f"{COLOR_BRIGHT_CYAN}{'Source Directory:':<{padding}}{COLOR_RESET}{self.source_dir}")
        print(f"{COLOR_BRIGHT_CYAN}{'Install Directory:':<{padding}}{COLOR_RESET}{self.install_dir}")
        print(f"{COLOR_BRIGHT_CYAN}{'Build Threads:':<{padding}}{COLOR_RESET}{self.build_threads}")

        if self.update_symlink:
            print(f"{COLOR_BRIGHT_CYAN}{'Symlink Update:':<{padding}}{COLOR_RESET}ENABLED")
            print(f"{COLOR_BRIGHT_CYAN}{'Symlink Target:':<{padding}}{COLOR_RESET}{self.symlink_target}")
            print(f"{COLOR_BRIGHT_CYAN}{'Symlink Path:':<{padding}}{COLOR_RESET}{self.symlink_path}")
        else:
            print(f"{COLOR_BRIGHT_CYAN}{'Symlink Update:':<{padding}}{COLOR_RESET}DISABLED")
            print() # Add a blank line for spacing
            print(f"{COLOR_YELLOW}WARNING: Active release will not match installed version (symlink update disabled){COLOR_RESET}")

        print(f"{COLOR_BRIGHT_CYAN}{separator}{COLOR_RESET}")

        try:
            # Prompt with colored text
            prompt_text = f"{COLOR_BOLD_GREEN}Proceed with installation? (y/n): {COLOR_RESET}"
            confirm = input(prompt_text)
            return confirm.lower() == 'y'
        except EOFError: # Handle non-interactive environments
            logger.warning("EOFError reading input, assuming non-interactive environment. Proceeding without confirmation.")
            return True

    @abc.abstractmethod
    def _prepare_source(self) -> None:
        """Prepare the source directory (clone, checkout, deps)."""
        pass

    @abc.abstractmethod
    def _compile(self) -> None:
        """Compile the source code."""
        pass

    @abc.abstractmethod
    def _install(self) -> None:
        """Install the compiled artifacts."""
        pass

    @abc.abstractmethod
    def _verify_install(self) -> None:
        """Verify the installation by checking versions."""
        pass

    def _perform_symlink(self) -> None:
        """Create or update the active_release symlink."""
        step_desc = f"Creating symlink: {self.symlink_path} -> {self.symlink_target}"
        self._log_step_start(5, step_desc) # Assuming this is step 5
        success = False
        try:
            filesystem.create_symlink(
                target=self.symlink_target,
                link_path=self.symlink_path,
                force=True,
                no_dereference=True,
                symbolic=True
            )
            success = True
        except Exception as e:
            logger.error(f"Failed during symlink creation: {e}")
            # Log end step as failed before re-raising
            self._log_step_end(5, success=False)
            raise
        finally:
             # Log success only if no exception occurred during the try block
             # If exception happened, it's logged as failed above
             if success:
                 self._log_step_end(5, success=True)

    @abc.abstractmethod
    def _verify_symlink(self) -> None:
        """Verify versions using the symlinked executables."""
        pass

    def build(self) -> None:
        """Main build orchestration method."""
        if not self._user_confirmation():
            logger.warning("Installation aborted by user.")
            print(f"{COLOR_YELLOW}Installation aborted by user.{COLOR_RESET}")
            return

        current_step = 0
        try:
            # Step 1: Prepare Source
            current_step = 1
            self._log_step_start(current_step, f"Preparing source ({self.client} {self.repo_type} {self.tag}) in {self.source_dir}")
            self._prepare_source()
            self._log_step_end(current_step)

            # Step 2: Compile
            current_step = 2
            self._log_step_start(current_step, f"Compiling {self.client} {self.repo_type} {self.tag}")
            self._compile()
            self._log_step_end(current_step)

            # Step 3: Install
            current_step = 3
            self._log_step_start(current_step, f"Installing to {self.install_dir}")
            self._install()
            self._log_step_end(current_step)

            # Step 4: Verify Installation
            current_step = 4
            self._log_step_start(current_step, f"Verifying installation in {self.install_dir}")
            self._verify_install()
            self._log_step_end(current_step)

            # Step 5 & 6: Handle Symlink & Verification
            if self.update_symlink:
                # Step 5: Perform Symlink (logging handled within the method)
                current_step = 5
                self._perform_symlink() 
                # Step 6: Verify Symlink
                current_step = 6
                self._log_step_start(current_step, f"Verifying active release via symlink ({self.symlink_path})")
                self._verify_symlink()
                self._log_step_end(current_step)
            else:
                logger.info("-- Skipping symlink update as per request. --")
                # Still run verification using system paths (Step 6)
                current_step = 6 
                self._log_step_start(current_step, "Verifying system path versions (symlink not updated)")
                self._verify_symlink()
                self._log_step_end(current_step)
                logger.warning("The versions displayed above may not match the installed release because the symlink was not updated.")

            logger.info("*** Build process completed successfully. ***")

        except (commands.CommandError, FileNotFoundError, ValueError, Exception) as e:
            logger.error(f"!!! BUILD FAILED during Step {current_step} !!!")
            logger.error(f"Error details: {e}")
            # Ensure the failed step is marked in logs if possible
            print(f"{COLOR_RED}BUILD FAILED during Step {current_step}.{COLOR_RESET}")
            if current_step > 0: 
                 self._log_step_end(current_step, success=False) 
            raise 