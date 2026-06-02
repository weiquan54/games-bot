"""Game Auto Clicker — Entry Point."""

import sys
import os
import logging

# Ensure project root is on path
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from config.manager import ConfigManager
from engine.clicker import ClickEngine
from ui.floating_window import FloatingWindow


def setup_logging():
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
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

    base_dir = os.path.dirname(os.path.abspath(__file__))
    config = ConfigManager(base_dir)
    engine = ClickEngine(config)

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
