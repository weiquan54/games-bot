"""Game Auto Clicker — Entry Point."""

import sys
import os
import logging

# Resolve base dir: works for both dev (`python main.py`) and PyInstaller exe
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from config.manager import ConfigManager
from engine.clicker import ClickEngine
from ui.floating_window import FloatingWindow


def setup_logging():
    log_dir = os.path.join(BASE_DIR, "logs")
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

    config = ConfigManager(BASE_DIR)
    engine = ClickEngine(config, BASE_DIR)

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
