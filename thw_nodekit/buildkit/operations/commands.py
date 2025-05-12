"""Handles execution of external shell commands."""

import subprocess
import logging
import os
from typing import List, Dict, Optional, Tuple

# Configure logging
logger = logging.getLogger(__name__)

class CommandError(Exception):
    """Custom exception for command execution errors."""
    def __init__(self, message: str, returncode: int, stdout: str, stderr: str):
        super().__init__(message)
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

def _run_command(
    command: List[str],
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    capture_output: bool = True,
    stream_output: bool = False
) -> Tuple[int, str, str]:
    """Internal helper to run a command and handle common logic."""
    log_cwd = cwd or os.getcwd()
    logger.info(f"Running command: '{' '.join(command)}' in cwd: {log_cwd}")
    
    # Merge with existing environment if env is provided
    process_env = os.environ.copy()
    if env:
        process_env.update(env)

    # Determine stdout/stderr handling
    stdout_pipe = subprocess.PIPE if capture_output and not stream_output else None
    stderr_pipe = subprocess.PIPE if capture_output and not stream_output else None
    # If streaming, output goes directly to parent process's stdout/stderr (the terminal)

    try:
        process = subprocess.run(
            command,
            cwd=cwd,
            env=process_env,
            stdout=stdout_pipe, # Set based on flags
            stderr=stderr_pipe, # Set based on flags
            text=True,
            check=False # We check manually 
        )

        # Get output only if captured
        stdout = process.stdout.strip() if stdout_pipe and process.stdout else ""
        stderr = process.stderr.strip() if stderr_pipe and process.stderr else ""

        # Log captured output
        if stdout_pipe and stdout:
            logger.debug(f"Command stdout: {stdout}")
        if stderr_pipe and stderr:
            logger.warning(f"Command stderr: {stderr}")

        # Log exit code if non-zero, regardless of capture/stream
        if process.returncode != 0:
             logger.warning(f"Command '{' '.join(command)}' finished with non-zero exit code: {process.returncode}")

        return process.returncode, stdout, stderr

    except FileNotFoundError:
        msg = f"Command not found: {command[0]}"
        logger.error(msg)
        raise CommandError(msg, -1, "", "")
    except Exception as e:
        msg = f"Error running command '{' '.join(command)}': {e}"
        logger.exception(msg)
        raise CommandError(msg, -1, "", str(e))


def run_command_check(
    command: List[str],
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    stream_output: bool = False
) -> Tuple[str, str]:
    """Runs a command, raises CommandError if it fails. Optionally streams output."""
    returncode, stdout, stderr = _run_command(
        command, cwd, env, 
        capture_output=not stream_output, # Capture only if not streaming
        stream_output=stream_output
    )
    if returncode != 0:
        error_message = f"Command '{' '.join(command)}' failed with exit code {returncode}"
        # If streaming, output went to terminal already. If captured, it's in vars.
        log_stderr = stderr if not stream_output else "(output streamed to terminal)"
        log_stdout = stdout if not stream_output else "(output streamed to terminal)"
        logger.error(f"{error_message}\\n--- Stderr ---\\n{log_stderr}\\n--- Stdout ---\\n{log_stdout}")
        # Raise with captured output if available, otherwise empty strings
        raise CommandError(error_message, returncode, stdout, stderr)
    return stdout, stderr

def run_make(cwd: str, jobs: int, targets: List[str]) -> None:
    """Runs make with specified job count and targets, streaming output."""
    command = ["make", f"-j{jobs}"] + targets
    # Use run_command_check with streaming enabled
    try:
         run_command_check(command, cwd=cwd, stream_output=True)
    except CommandError as e:
         # Error is already logged by run_command_check
         # Re-raise a simpler error maybe, or just re-raise e?
         raise CommandError(f"Make command failed.", e.returncode, "", "") from e

def run_script(
    script_path: str, 
    args: Optional[List[str]] = None, 
    cwd: Optional[str] = None, 
    env: Optional[Dict[str, str]] = None, 
    check: bool = True, 
    stream_output: bool = False
) -> Tuple[str, str]:
    """Runs a shell script, optionally streaming output."""
    command = ["bash", script_path] + (args if args else [])
    if check:
        # Pass stream_output flag to run_command_check
        return run_command_check(command, cwd=cwd, env=env, stream_output=stream_output)
    else:
        # If not checking, run and stream but don't capture or raise on error
        logger.info(f"Running script without check (streaming={stream_output}): {' '.join(command)}")
        _run_command(command, cwd=cwd, env=env, capture_output=False, stream_output=True) 
        # Return empty strings as output is not captured and errors aren't checked
        return "", ""

def get_solana_version(executable_path: str = "solana") -> str:
    """Gets the Solana version using the specified executable."""
    command = [executable_path, "--version"]
    try:
        stdout, _ = run_command_check(command)
        # Return the full output string directly
        return stdout.strip()
    except CommandError as e:
        logger.error(f"Failed to get Solana version from {executable_path}: {e}")
        return "Error getting solanaversion"

def get_agave_validator_version(executable_path: str = "agave-validator") -> str:
    """Gets the Agave Validator version using the specified executable."""
    command = [executable_path, "--version"]
    try:
        # Use run_command_check to capture output and check for errors
        stdout, _ = run_command_check(command)
        # Return the full output string directly
        return stdout.strip()
    except CommandError as e:
        logger.error(f"Failed to get Agave Validator version from {executable_path}: {e}")
        # Provide a distinct error message
        return "Error getting agave-validator version"

def get_fdctl_version(executable_path: str = "fdctl") -> str:
    """Gets the Fdctl version using the specified executable."""
    command = [executable_path, "version"]
    try:
        stdout, _ = run_command_check(command)
        # Assuming output is just the version string or similar
        # Firedancer version output might vary, adjust parsing as needed
        return stdout.strip()
    except CommandError as e:
        logger.error(f"Failed to get fdctl version from {executable_path}: {e}")
        return "Error getting fdctlversion"

def run_yes_pipe(command: List[str], cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None) -> None:
    """Runs a command piping 'yes y' into it, streaming output."""
    log_cwd = cwd or os.getcwd()
    logger.info(f"Running command with 'yes y |': '{' '.join(command)}' in cwd: {log_cwd}")

    process_env = os.environ.copy()
    if env:
        process_env.update(env)

    yes_process = None
    target_process = None
    try:
        # Start 'yes y'
        yes_process = subprocess.Popen(["yes", "y"], stdout=subprocess.PIPE)

        # Start the target command, taking stdin from yes_process
        # Let stdout/stderr inherit from the parent process (this process) to stream
        target_process = subprocess.Popen(
            command,
            cwd=cwd,
            env=process_env,
            stdin=yes_process.stdout,
            stdout=None, # Inherit
            stderr=None, # Inherit
            text=True
        )

        # Allow yes_process to receive a SIGPIPE if target_process exits.
        if yes_process.stdout:
             yes_process.stdout.close()

        # Wait for target_process to finish
        returncode = target_process.wait()

        # Log and raise error if needed
        if returncode != 0:
            error_message = f"Command '{' '.join(command)}' (piped from 'yes y') failed with exit code {returncode}"
            # Output was already streamed
            logger.error(f"{error_message} (output streamed to terminal)")
            raise CommandError(error_message, returncode, "(streamed)", "(streamed)")

    except FileNotFoundError:
        msg = f"Command or 'yes' not found for piped execution: {command[0]}"
        logger.error(msg)
        raise CommandError(msg, -1, "", "")
    except Exception as e:
        msg = f"Error running piped command '{' '.join(command)}': {e}"
        logger.exception(msg)
        raise CommandError(msg, -1, "", str(e))
    finally:
        # Ensure yes_process is terminated if it's still running
        if yes_process and yes_process.poll() is None:
            try:
                 yes_process.terminate()
                 yes_process.wait(timeout=1) # Add a small timeout
            except subprocess.TimeoutExpired:
                 yes_process.kill()
                 yes_process.wait()
            except Exception as e:
                 logger.warning(f"Error terminating 'yes' process: {e}")
        # Ensure target_process is handled (though wait() should cover it)
        if target_process and target_process.poll() is None:
             logger.warning("Target process still running after wait(), attempting termination.")
             try:
                 target_process.terminate()
                 target_process.wait(timeout=1)
             except subprocess.TimeoutExpired:
                 target_process.kill()
                 target_process.wait()
             except Exception as e:
                 logger.warning(f"Error terminating target process: {e}") 