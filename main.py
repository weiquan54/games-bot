"""Game Auto Clicker — Entry Point."""

import sys
import os
import logging
import shutil

# Resolve base dir: works for both dev (`python main.py`) and PyInstaller exe
if getattr(sys, 'frozen', False):
    # PyInstaller bundle: resources in _MEIPASS, logs/config next to exe
    RES_DIR = sys._MEIPASS
    WORK_DIR = os.path.dirname(sys.executable)
else:
    RES_DIR = os.path.dirname(os.path.abspath(__file__))
    WORK_DIR = RES_DIR

os.chdir(RES_DIR)
sys.path.insert(0, RES_DIR)

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from config.manager import ConfigManager
from engine.clicker import ClickEngine
from ui.floating_window import FloatingWindow


def setup_logging():
    # Log to the work dir (next to exe, or project root for dev)
    log_dir = os.path.join(WORK_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "game_bot.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def main():
    # MUST set before QApplication is created
    QApplication.setAttribute(Qt.AA_DisableHighDpiScaling, False)

    setup_logging()
    logger = logging.getLogger("main")
    logger.info(f"RES_DIR={RES_DIR}, WORK_DIR={WORK_DIR}")

    # For exe: copy bundled settings.json to writable work dir on first run
    work_settings = os.path.join(WORK_DIR, "settings.json")
    bundled_settings = os.path.join(RES_DIR, "settings.json")
    if getattr(sys, 'frozen', False) and not os.path.exists(work_settings):
        shutil.copy(bundled_settings, work_settings)
        logger.info("Initialized settings.json in work directory")

    config = ConfigManager(WORK_DIR)
    engine = ClickEngine(config, RES_DIR)

    # Pre-load all templates
    actions = config.actions
    if actions:
        engine.load_all_templates()
        loaded = len(engine._templates)
        if loaded > 0:
            logger.info(f"Loaded {loaded}/{len(actions)} templates")
        else:
            logger.warning("No templates could be loaded")

    app = QApplication(sys.argv)

    window = FloatingWindow(config, engine)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
