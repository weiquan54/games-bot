"""Click engine — multi-action sequential click loop in a background thread."""

import time
import logging
import os
import threading
import traceback
from pathlib import Path

import cv2
import pyautogui
pyautogui.FAILSAFE = False
import numpy as np
import win32gui
import win32con
import win32api
import ctypes
from ctypes import wintypes

from engine.matcher import match_template
from config.manager import ConfigManager

logger = logging.getLogger("clicker")


class ClickEngine:
    def __init__(self, config: ConfigManager, base_dir: str = None):
        self.config = config
        self.base_dir = base_dir
        self._running = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self.status = "idle"  # idle / running / clicked / notfound / stopped
        self._templates: dict[str, np.ndarray] = {}
        self._current_action_idx = 0
        self._current_round = 0
        self._total_rounds_done = 0
        self._consecutive_notfound = 0
        self._window_title = "panoptyca"

    def load_all_templates(self):
        """Pre-load all action templates from config."""
        self._templates.clear()
        for action in self.config.actions:
            path = action["template"]
            # If running as PyInstaller bundle, resolve path relative to base_dir
            if self.base_dir and not os.path.isabs(path):
                path = os.path.join(self.base_dir, path)
            # Also try relative to base_dir even if path is absolute (exe fallback)
            if not os.path.exists(path) and self.base_dir:
                alt = os.path.join(self.base_dir, "templates", os.path.basename(path))
                if os.path.exists(alt):
                    path = alt
            img = cv2.imread(path, cv2.IMREAD_COLOR)
            if img is not None:
                self._templates[path] = img
            else:
                logger.warning(f"Cannot load template: {path}")

    def load_template(self, path: str):
        """Load a single template (compatibility wrapper)."""
        img = cv2.imread(path, cv2.IMREAD_COLOR)
        if img is None:
            raise FileNotFoundError(f"Cannot load template: {path}")
        self._templates[path] = img

    @property
    def running(self) -> bool:
        return self._running

    @property
    def details(self) -> dict:
        """Returns current execution details for UI display."""
        actions = self.config.actions
        total = len(actions)
        return {
            "total_actions": total,
            "current_action": min(self._current_action_idx + 1, total) if self._running else 0,
            "current_action_name": actions[self._current_action_idx].get("name", "?") if self._running and self._current_action_idx < total else "",
            "current_round": self._current_round,
            "total_rounds_done": self._total_rounds_done,
        }

    def start(self):
        if self._running:
            return
        actions = self.config.actions
        if not actions:
            self.status = "stopped"
            logger.warning("No actions configured, cannot start")
            return
        self.load_all_templates()
        if not self._templates:
            self.status = "stopped"
            logger.warning("No templates loaded, cannot start")
            return

        self._running = True
        self._stop_event.clear()
        self._current_action_idx = 0
        self._current_round = 0
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self.status = "running"
        logger.info("Click engine started")

    def stop(self):
        self._stop_event.set()
        self._running = False
        self.status = "stopped"
        logger.info("Click engine stopped")

    def _prevent_lock(self):
        """Prevent Windows from locking the session while bot is running.
        
        Uses SetThreadExecutionState with ES_AWAYMODE_REQUIRED:
        - Display can still turn off (privacy / power saving)
        - System stays awake
        - Session stays active (no lock screen)
        Resets automatically when the thread exits or stop() is called.
        """
        ES_CONTINUOUS = 0x80000000
        ES_SYSTEM_REQUIRED = 0x00000001
        ES_AWAYMODE_REQUIRED = 0x00000040
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
        )
        logger.info("Lock prevention enabled (away mode — display can still sleep)")

    def _allow_lock(self):
        """Restore default power management."""
        ES_CONTINUOUS = 0x80000000
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        logger.info("Lock prevention disabled")

    def _loop(self):
        self._prevent_lock()
        try:
            bw, bh = self.config.baseline_resolution
            actions = self.config.actions
            total = len(actions)

            while not self._stop_event.is_set():
                self._current_round += 1
                self._consecutive_notfound = 0
                logger.info(f"--- Round {self._current_round} start ---")

                for idx, action in enumerate(actions):
                    if self._stop_event.is_set():
                        break

                    self._current_action_idx = idx
                    template_path = action["template"]
                    template = self._templates.get(template_path)
                    if template is None:
                        logger.warning(f"Template not loaded: {action['name']}")
                        continue

                    post_delay = action.get("post_delay", 2.0)
                    timeout = action.get("timeout", 10.0)
                    found = False
                    deadline = time.time() + timeout
                    restart_round = False

                    while not self._stop_event.is_set() and not found and time.time() < deadline:
                        try:
                            try:
                                screenshot = pyautogui.screenshot()
                            except OSError as e:
                                logger.warning(f"Screenshot failed ({e}) — sending wake signal, waiting 2s")
                                self.status = "locked"
                                self._wake_display()
                                self._stop_event.wait(2.0)
                                if self._stop_event.is_set():
                                    return
                                self.status = "running"
                                continue
                            frame = np.array(screenshot)
                            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

                            # Detect black screen (display off) — 90th percentile < 25 means mostly black
                            if np.percentile(frame, 90) < 25:
                                logger.warning("Black screen detected — waking display and restarting round")
                                self._wake_display()
                                self._stop_event.wait(3.0)
                                if self._stop_event.is_set():
                                    return
                                restart_round = True
                                break

                            sf = 1.0
                            if bw > 0 and bh > 0:
                                h, w = frame.shape[:2]
                                sf = min(w / bw, h / bh)

                            result = match_template(frame, template, self.config.threshold, sf)
                            if result is not None:
                                cx, cy = result
                                pyautogui.click(cx, cy)
                                self.status = "clicked"
                                logger.info(f"[{action['name']}] Clicked at ({cx}, {cy})")
                                found = True
                                if self._stop_event.wait(post_delay):
                                    break
                            else:
                                self.status = "notfound"
                                self._consecutive_notfound += 1
                                if self._consecutive_notfound >= 20:
                                    logger.warning(f"{self._consecutive_notfound} consecutive not found — activating window '{self._window_title}' and restarting round")
                                    self._consecutive_notfound = 0
                                    self._activate_window()
                                    restart_round = True
                                    break
                                time.sleep(0.05)

                        except Exception as e:
                            logger.error(f"Click loop error: {e}\n{traceback.format_exc()}")
                            print(f"\n  [CLICKER CRASH] {e}", flush=True)
                            traceback.print_exc()
                            self.status = "stopped"
                            self._running = False
                            return

                    if self._stop_event.is_set():
                        break

                    if restart_round:
                        logger.info(f"[{action['name']}] Restarting round from button_1")
                        break

                    if not found:
                        logger.info(f"[{action['name']}] Timeout ({timeout}s), skipped")

                if self._stop_event.is_set():
                    break

                if restart_round:
                    continue

                self._total_rounds_done += 1
                self._current_action_idx = 0

                logger.info(
                    f"--- Round {self._current_round} complete, "
                    f"next in {self.config.round_interval}s ---"
                )
                self._turn_off_screen()
                self.status = "countdown"
                remaining = self.config.round_interval
                while remaining > 0 and not self._stop_event.is_set():
                    self.status = f"countdown:{remaining}"
                    if self._stop_event.wait(1.0):
                        break
                    remaining -= 1
                if self._stop_event.is_set():
                    break
                # Wake screen before starting next round, verify it's actually on
                for wake_attempt in range(5):
                    self._wake_display()
                    self._stop_event.wait(2.0)
                    if self._stop_event.is_set():
                        break
                    try:
                        test = np.array(pyautogui.screenshot())
                        if np.percentile(test, 90) > 25:
                            break  # screen is on
                    except OSError:
                        pass
                    logger.warning(f"Screen still off after wake (attempt {wake_attempt+1}/5)")
                if self._stop_event.is_set():
                    break
                # Screen is on — aggressively dismiss any login/lock overlays
                for _ in range(3):
                    win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
                    time.sleep(0.1)
                    win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)
                    time.sleep(0.4)
                win32api.keybd_event(win32con.VK_SPACE, 0, 0, 0)
                time.sleep(0.1)
                win32api.keybd_event(win32con.VK_SPACE, 0, win32con.KEYEVENTF_KEYUP, 0)
                time.sleep(0.4)
                win32api.keybd_event(win32con.VK_ESCAPE, 0, 0, 0)
                time.sleep(0.1)
                win32api.keybd_event(win32con.VK_ESCAPE, 0, win32con.KEYEVENTF_KEYUP, 0)
                time.sleep(0.5)
                self._activate_window()
                self._stop_event.wait(1.0)

            self._running = False
            self.status = "stopped"
            logger.info("Click engine stopped")
        finally:
            self._allow_lock()

    def _wake_display(self):
        """Wake up display — temporarily override AwayMode to force screen on."""
        try:
            ES_CONTINUOUS = 0x80000000
            ES_SYSTEM_REQUIRED = 0x00000001
            ES_DISPLAY_REQUIRED = 0x00000002
            # Temporarily force display ON (overrides AwayMode)
            ctypes.windll.kernel32.SetThreadExecutionState(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
            )
            time.sleep(1.0)
            # Also send key events as backup
            win32api.keybd_event(win32con.VK_SCROLL, 0, 0, 0)
            time.sleep(0.05)
            win32api.keybd_event(win32con.VK_SCROLL, 0, win32con.KEYEVENTF_KEYUP, 0)
            # Wait for display to stabilize
            time.sleep(2.0)
            # Restore AwayMode so screen can sleep again later
            ES_AWAYMODE_REQUIRED = 0x00000040
            ctypes.windll.kernel32.SetThreadExecutionState(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
            )
        except Exception as e:
            logger.warning(f"Wake display failed: {e}")

    def _turn_off_screen(self):
        """Turn off display between rounds (zero process overhead — just a Windows API call)."""
        try:
            HWND_BROADCAST = 0xFFFF
            WM_SYSCOMMAND = 0x0112
            SC_MONITORPOWER = 0xF170
            ctypes.windll.user32.PostMessageW(HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, 2)
            logger.debug("Screen turned off for power saving")
        except Exception as e:
            logger.warning(f"Turn off screen failed: {e}")

    def _activate_window(self):
        """Bring the target game window to foreground."""
        try:
            hwnd = win32gui.FindWindow(None, self._window_title)
            if not hwnd:
                logger.warning(f"Window not found: {self._window_title}")
                return

            # Restore if minimized
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.2)

            # Trick Windows: pressing Alt gives this thread foreground activation permission
            win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
            time.sleep(0.05)
            win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
            time.sleep(0.1)

            try:
                win32gui.SetForegroundWindow(hwnd)
            except Exception:
                # Fallback: simulate Alt+Tab to switch to the game window
                logger.info("SetForegroundWindow failed — trying Alt+Tab fallback")
                self._alt_tab_to_window(hwnd)

            logger.info(f"Activated window: {self._window_title}")
        except Exception as e:
            logger.error(f"Failed to activate window: {e}")

    def _alt_tab_to_window(self, hwnd):
        """Fallback: use Alt+Tab simulation to switch to the target window."""
        try:
            # Bring window to top of Z-order first
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, 0, 0, 0, 0,
                                  win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW)
            # Simulate Alt+Tab to switch
            win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
            time.sleep(0.05)
            for _ in range(2):
                win32api.keybd_event(win32con.VK_TAB, 0, 0, 0)
                time.sleep(0.05)
                win32api.keybd_event(win32con.VK_TAB, 0, win32con.KEYEVENTF_KEYUP, 0)
                time.sleep(0.05)
            time.sleep(0.05)
            win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
            time.sleep(0.3)
        except Exception as e:
            logger.error(f"Alt+Tab fallback failed: {e}")
