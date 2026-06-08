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
        self.status = "idle"
        self._templates: dict[str, np.ndarray] = {}
        self._current_action_idx = 0
        self._current_round = 0
        self._total_rounds_done = 0
        self._consecutive_notfound = 0
        self._window_title = "panoptyca"

    def load_all_templates(self):
        self._templates.clear()
        for action in self.config.actions:
            path = action["template"]
            if self.base_dir and not os.path.isabs(path):
                path = os.path.join(self.base_dir, path)
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
        img = cv2.imread(path, cv2.IMREAD_COLOR)
        if img is None:
            raise FileNotFoundError(f"Cannot load template: {path}")
        self._templates[path] = img

    @property
    def running(self) -> bool:
        return self._running

    @property
    def details(self) -> dict:
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
        ES_CONTINUOUS = 0x80000000
        ES_SYSTEM_REQUIRED = 0x00000001
        ES_AWAYMODE_REQUIRED = 0x00000040
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
        )
        logger.info("Lock prevention enabled (away mode)")

    def _allow_lock(self):
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
                try:
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
                                    logger.warning(f"Screenshot failed ({e}) — waking display")
                                    self.status = "locked"
                                    self._wake_display()
                                    self._stop_event.wait(2.0)
                                    if self._stop_event.is_set():
                                        return
                                    self.status = "running"
                                    continue
                                frame = np.array(screenshot)
                                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

                                if np.percentile(frame, 90) < 25:
                                    logger.warning("Black screen detected — waking display")
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
                                    win32api.SetCursorPos((cx, cy))
                                    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                                    time.sleep(0.03)
                                    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                                    self.status = "clicked"
                                    logger.info(f"[{action['name']}] Clicked at ({cx}, {cy})")
                                    found = True
                                    if self._stop_event.wait(post_delay):
                                        break
                                else:
                                    self.status = "notfound"
                                    self._consecutive_notfound += 1
                                    if self._consecutive_notfound >= 20:
                                        logger.warning(f"{self._consecutive_notfound} consecutive not found — activating window")
                                        self._consecutive_notfound = 0
                                        self._activate_window()
                                        restart_round = True
                                        break
                                    time.sleep(0.05)

                            except Exception as e:
                                logger.error(f"Button loop error: {e}", exc_info=True)
                                self._stop_event.wait(1.0)
                                continue

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
                    delay = self.config.screen_off_delay
                    if delay > 0:
                        self._stop_event.wait(delay)
                    self._turn_off_screen()
                    self.status = "countdown"
                    remaining = self.config.round_interval
                    idle_ticks = 0
                    while remaining > 0 and not self._stop_event.is_set():
                        self.status = f"countdown:{remaining}"
                        if self._stop_event.wait(1.0):
                            break
                        remaining -= 1
                        idle_ticks += 1
                        if idle_ticks >= 30:
                            win32api.keybd_event(win32con.VK_F15, 0, 0, 0)
                            time.sleep(0.02)
                            win32api.keybd_event(win32con.VK_F15, 0, win32con.KEYEVENTF_KEYUP, 0)
                            idle_ticks = 0
                    if self._stop_event.is_set():
                        break
                    self._wake_display()
                    self._stop_event.wait(3.0)
                    wake_delay = self.config.wake_delay
                    if wake_delay > 0:
                        logger.info(f"Waiting {wake_delay}s for game to stabilize")
                        self._stop_event.wait(wake_delay)

                except Exception as e:
                    logger.error(f"Round crashed: {e}", exc_info=True)
                    self.status = "crashed"
                    self._stop_event.wait(5.0)

            self._running = False
            self.status = "stopped"
            logger.info("Click engine stopped")
        finally:
            self._allow_lock()

    def _wake_display(self):
        """Force display ON — async PostMessage + key events."""
        try:
            HWND_BROADCAST = 0xFFFF
            WM_SYSCOMMAND = 0x0112
            SC_MONITORPOWER = 0xF170
            result = ctypes.windll.user32.PostMessageW(HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, -1)
            if result == 0:
                logger.warning("PostMessage(SC_MONITORPOWER, -1) failed")
            time.sleep(0.5)
            win32api.keybd_event(win32con.VK_SCROLL, 0, 0, 0)
            time.sleep(0.05)
            win32api.keybd_event(win32con.VK_SCROLL, 0, win32con.KEYEVENTF_KEYUP, 0)
        except Exception as e:
            logger.warning(f"Wake display failed: {e}")

    def _turn_off_screen(self):
        """Turn off display — async PostMessage (non-blocking)."""
        try:
            HWND_BROADCAST = 0xFFFF
            WM_SYSCOMMAND = 0x0112
            SC_MONITORPOWER = 0xF170
            result = ctypes.windll.user32.PostMessageW(HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, 2)
            if result == 0:
                logger.warning("PostMessage(SC_MONITORPOWER) returned 0 — screen may not have turned off")
        except Exception as e:
            logger.warning(f"Turn off screen failed: {e}")

    def _activate_window(self):
        try:
            hwnd = win32gui.FindWindow(None, self._window_title)
            if not hwnd:
                logger.warning(f"Window not found: {self._window_title}")
                return
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.2)
            win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
            time.sleep(0.05)
            win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
            time.sleep(0.1)
            try:
                win32gui.SetForegroundWindow(hwnd)
            except Exception:
                self._alt_tab_to_window(hwnd)
            logger.info(f"Activated window: {self._window_title}")
        except Exception as e:
            logger.error(f"Failed to activate window: {e}")

    def _alt_tab_to_window(self, hwnd):
        try:
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, 0, 0, 0, 0,
                                  win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW)
            win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
            time.sleep(0.05)
            for _ in range(2):
                win32api.keybd_event(win32con.VK_TAB, 0, 0, 0)
                time.sleep(0.05)
                win32api.keybd_event(win32con.VK_TAB, 0, win32con.KEYEVENTF_KEYUP, 0)
                time.sleep(0.05)
            win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
            time.sleep(0.3)
        except Exception as e:
            logger.error(f"Alt+Tab fallback failed: {e}")
