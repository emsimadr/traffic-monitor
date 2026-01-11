"""
Process management utilities for single-instance enforcement.

This module provides:
- PID file management (write on start, check for existing, cleanup)
- Graceful shutdown support
- Stale process detection and cleanup
"""

from __future__ import annotations

import atexit
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Optional

# Default PID file location
DEFAULT_PID_FILE = "data/traffic_monitor.pid"


def get_pid_file_path(pid_file: Optional[str] = None) -> Path:
    """Get the PID file path."""
    return Path(pid_file or DEFAULT_PID_FILE)


def read_pid_file(pid_file: Optional[str] = None) -> Optional[int]:
    """
    Read the PID from the PID file.
    
    Returns:
        The PID if file exists and is valid, None otherwise.
    """
    path = get_pid_file_path(pid_file)
    if not path.exists():
        return None
    
    try:
        content = path.read_text().strip()
        return int(content)
    except (ValueError, OSError):
        return None


def is_process_running(pid: int) -> bool:
    """
    Check if a process with the given PID is running.
    
    Works cross-platform (Windows and Unix).
    """
    if pid <= 0:
        return False
    
    if sys.platform == "win32":
        # Windows: use ctypes to check process
        import ctypes
        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    else:
        # Unix: send signal 0 to check if process exists
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def kill_process(pid: int, force: bool = False) -> bool:
    """
    Kill a process by PID.
    
    Args:
        pid: Process ID to kill.
        force: If True, use SIGKILL (Unix) or TerminateProcess (Windows).
    
    Returns:
        True if process was killed or doesn't exist, False on error.
    """
    if pid <= 0:
        return True
    
    if not is_process_running(pid):
        return True
    
    try:
        if sys.platform == "win32":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            PROCESS_TERMINATE = 0x0001
            handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
            if handle:
                result = kernel32.TerminateProcess(handle, 1)
                kernel32.CloseHandle(handle)
                return bool(result)
            return False
        else:
            sig = signal.SIGKILL if force else signal.SIGTERM
            os.kill(pid, sig)
            return True
    except Exception as e:
        logging.warning(f"Failed to kill process {pid}: {e}")
        return False


def write_pid_file(pid_file: Optional[str] = None) -> None:
    """
    Write the current process PID to the PID file.
    
    Also registers cleanup on exit.
    """
    path = get_pid_file_path(pid_file)
    
    # Ensure directory exists
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write PID
    path.write_text(str(os.getpid()))
    logging.debug(f"Wrote PID {os.getpid()} to {path}")
    
    # Register cleanup
    atexit.register(remove_pid_file, pid_file)


def remove_pid_file(pid_file: Optional[str] = None) -> None:
    """Remove the PID file."""
    path = get_pid_file_path(pid_file)
    try:
        if path.exists():
            path.unlink()
            logging.debug(f"Removed PID file: {path}")
    except OSError as e:
        logging.warning(f"Failed to remove PID file: {e}")


def ensure_single_instance(pid_file: Optional[str] = None, kill_existing: bool = False) -> bool:
    """
    Ensure only one instance of the application is running.
    
    Args:
        pid_file: Path to PID file (default: data/traffic_monitor.pid).
        kill_existing: If True, kill any existing instance before starting.
    
    Returns:
        True if we can proceed (no other instance or killed it).
        False if another instance is running and kill_existing is False.
    
    Side effects:
        - Writes PID file for current process.
        - Registers cleanup on exit.
    """
    existing_pid = read_pid_file(pid_file)
    
    if existing_pid is not None:
        if is_process_running(existing_pid):
            if kill_existing:
                logging.info(f"Killing existing instance (PID {existing_pid})...")
                if kill_process(existing_pid):
                    # Wait a moment for cleanup
                    import time
                    time.sleep(1)
                    logging.info(f"Killed existing instance (PID {existing_pid})")
                else:
                    logging.error(f"Failed to kill existing instance (PID {existing_pid})")
                    return False
            else:
                logging.error(
                    f"Another instance is already running (PID {existing_pid}). "
                    f"Use --kill-existing to replace it, or stop it manually."
                )
                return False
        else:
            # Stale PID file - process no longer running
            logging.info(f"Removing stale PID file (PID {existing_pid} not running)")
            remove_pid_file(pid_file)
    
    # Write our PID
    write_pid_file(pid_file)
    return True


def stop_existing_instance(pid_file: Optional[str] = None) -> bool:
    """
    Stop any existing instance of the application.
    
    Args:
        pid_file: Path to PID file.
    
    Returns:
        True if no instance running or successfully stopped.
        False if failed to stop.
    """
    existing_pid = read_pid_file(pid_file)
    
    if existing_pid is None:
        print("No PID file found - no instance to stop.")
        return True
    
    if not is_process_running(existing_pid):
        print(f"PID file exists but process {existing_pid} is not running. Cleaning up.")
        remove_pid_file(pid_file)
        return True
    
    print(f"Stopping instance (PID {existing_pid})...")
    if kill_process(existing_pid):
        import time
        # Wait for process to exit
        for _ in range(10):
            if not is_process_running(existing_pid):
                break
            time.sleep(0.5)
        
        if is_process_running(existing_pid):
            print(f"Process {existing_pid} didn't stop gracefully, force killing...")
            kill_process(existing_pid, force=True)
            time.sleep(0.5)
        
        remove_pid_file(pid_file)
        print(f"Instance stopped (PID {existing_pid})")
        return True
    else:
        print(f"Failed to stop instance (PID {existing_pid})")
        return False

