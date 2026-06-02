"""Workstation lock detection utility."""
import ctypes
import logging

logger = logging.getLogger("clicker")

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


def is_workstation_locked() -> bool:
    """Check if the Windows workstation is locked (lock screen active).

    Opens the input desktop with DESKTOP_READOBJECTS access.
    Returns True when the input desktop cannot be opened (locked).
    """
    DESKTOP_READOBJECTS = 0x0001
    handle = user32.OpenInputDesktop(0, False, DESKTOP_READOBJECTS)
    if handle:
        user32.CloseDesktop(handle)
        return False

    error = kernel32.GetLastError()
    locked = (error == 5)  # ERROR_ACCESS_DENIED
    logger.info(f"Lock check: OpenInputDesktop failed, GetLastError={error}, {'LOCKED' if locked else 'UNLOCKED (unexpected error)'}")
    return locked
