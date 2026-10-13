import json
from pathlib import Path

from PyQt5.QtWidgets import (
    QDialog,
    QFileDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


class ConfigurationDialog(QDialog):
    """Small button-only JSON configuration loader/saver."""

    def __init__(self, config_path, current_config=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuration")
        self.resize(420, 220)
        self.config_path = Path(config_path)
        self.current_config = current_config if current_config is not None else {}
        self.load_path_selected = Path(config_path)
        self.save_folder_selected = Path(config_path).parent
        self.load_config = False

        self.load_status = QLabel(f"Load file: {self.load_path_selected}")
        self.load_status.setWordWrap(True)
        self.save_status = QLabel(f"Save folder: {self.save_folder_selected}")
        self.save_status.setWordWrap(True)

        pick_file_btn = QPushButton("Pick config file")
        pick_folder_btn = QPushButton("Pick save folder")
        load_btn = QPushButton("Load config")
        save_btn = QPushButton("Save config")
        cancel_btn = QPushButton("Cancel")
        pick_file_btn.clicked.connect(self.pick_config_file)
        pick_folder_btn.clicked.connect(self.pick_save_folder)
        load_btn.clicked.connect(self.load_selected_config)
        save_btn.clicked.connect(self.save_current_config)
        cancel_btn.clicked.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.load_status)
        layout.addWidget(pick_file_btn)
        layout.addWidget(load_btn)
        layout.addWidget(self.save_status)
        layout.addWidget(pick_folder_btn)
        layout.addWidget(save_btn)
        layout.addWidget(cancel_btn)

    def pick_config_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load configuration JSON",
            str(self.load_path_selected.parent),
            "JSON Files (*.json);;All Files (*)",
        )
        if not path:
            return
        self.load_path_selected = Path(path)
        self.load_status.setText(f"Load file: {self.load_path_selected}")

    def pick_save_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select folder to save configuration",
            str(self.save_folder_selected),
        )
        if not folder:
            return
        self.save_folder_selected = Path(folder)
        self.save_status.setText(f"Save folder: {self.save_folder_selected}")

    def load_selected_config(self):
        try:
            self.load_config = True
            self.config_path = self.load_path_selected
            self.accept()
        except Exception as exc:
            QMessageBox.warning(self, "Load failed", str(exc))

    def save_current_config(self):
        try:
            self.save_folder_selected.mkdir(parents=True, exist_ok=True)
            path = self.save_folder_selected / "config.json"
            if path.exists():
                stem = path.stem
                suffix = path.suffix
                index = 1
                while path.exists():
                    path = self.save_folder_selected / f"{stem}_{index}{suffix}"
                    index += 1
            with open(path, "w", encoding="utf-8") as file:
                json.dump(self.current_config, file, indent=4)
            self.config_path = path
            self.accept()
        except Exception as exc:
            QMessageBox.warning(self, "Save failed", str(exc))
