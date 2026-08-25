from PyQt5.QtWidgets import QApplication, QDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QListWidget, QAbstractItemView, QComboBox, QCheckBox, QDoubleSpinBox, QWidget
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QListWidgetItem






class StageSequenceEditorDialog(QDialog):
    def __init__(self, stops=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set Stage Sequence")
        self.resize(920, 420)
        self.property_options = ["Start", "imaging", "projection", "powermeter", "spectrometer", "image sensor", "resolution", "auto solid projection"]
        self.screens = QApplication.screens()
        self._applying_offset = False

        self.stop_list = QListWidget()
        self.stop_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.stop_list.setDefaultDropAction(Qt.MoveAction)
        self.stop_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.stop_list.model().rowsMoved.connect(lambda *args: self._refresh_first_stop_constraint())

        add_btn = QPushButton("+")
        remove_btn = QPushButton("-")
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        add_btn.setFixedWidth(36)
        remove_btn.setFixedWidth(36)

        add_btn.clicked.connect(lambda: self.add_stop())
        remove_btn.clicked.connect(self.remove_selected_stop)
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)

        hint = QLabel(
            "Drag stops up/down to change order. Enter X/Y start error as the current zeroed field of view "
            "offset from the intended start position; stop coordinates are corrected by adding that error. "
            f"Detected projectors/displays: {len(self.screens)}. For projection stops, select the projector/display to use."
        )
        hint.setWordWrap(True)

        self.start_offset_x_spin = self._offset_spin()
        self.start_offset_y_spin = self._offset_spin()
        self.start_offset_x_spin.valueChanged.connect(self._apply_start_offset_to_all_stops)
        self.start_offset_y_spin.valueChanged.connect(self._apply_start_offset_to_all_stops)
        self.global_z_check = QCheckBox("Global Z")
        self.global_z_spin = self._coordinate_spin(80.0)
        self.global_z_spin.setSuffix(" mm")
        self.global_z_spin.setEnabled(False)
        self.global_z_check.stateChanged.connect(self._apply_global_z_to_all_stops)
        self.global_z_spin.valueChanged.connect(self._apply_global_z_to_all_stops)

        edit_row = QHBoxLayout()
        edit_row.addWidget(QLabel("Stops:"))
        edit_row.addWidget(add_btn)
        edit_row.addWidget(remove_btn)
        edit_row.addSpacing(16)
        edit_row.addWidget(QLabel("Start error X:"))
        edit_row.addWidget(self.start_offset_x_spin)
        edit_row.addWidget(QLabel("Y:"))
        edit_row.addWidget(self.start_offset_y_spin)
        edit_row.addSpacing(16)
        edit_row.addWidget(self.global_z_check)
        edit_row.addWidget(self.global_z_spin)
        edit_row.addStretch(1)

        action_row = QHBoxLayout()
        action_row.addStretch(1)
        action_row.addWidget(save_btn)
        action_row.addWidget(cancel_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        layout.addLayout(edit_row)
        layout.addWidget(self.stop_list)
        layout.addLayout(action_row)

        initial_stops = stops if stops else [
            (0.0, 0.0, 80.0, "Start"),
            (12.145, 0.0, 80.0, "imaging"),
            (32.49, 0.0, 80.0, "imaging"),
            (32.49, 25.0, 80.0, "imaging"),
            (32.49, 50.0, 80.0, "imaging"),
            (59.12, 50.0, 80.0, "imaging"),
            (59.12, 25.0, 80.0, "imaging"),
            (59.12, 0.0, 80.0, "imaging"),
            (83.88, 5.0, 80.0, "imaging"),
            (85.88, 25.0, 80.0, "imaging"),
            (91.64, 55.0, 80.0, "imaging"),
            (0.0, 55.0, 80.0, "imaging"),
            (0.0, 15.0, 80.0, "imaging"),
        ]
        for stop in initial_stops:
            x, y, z, prop, projector = self._normalize_stop(stop)
            self.add_stop(x, y, z, prop, projector)
        self._refresh_first_stop_constraint()

    def add_stop(self, x=0.0, y=0.0, z=80.0, prop="imaging", projector=None):
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(6, 4, 6, 4)
        row_layout.setSpacing(6)

        title = QLabel()
        title.setFixedWidth(54)
        x_spin = self._coordinate_spin(self._corrected_x(x))
        y_spin = self._coordinate_spin(self._corrected_y(y))
        z_spin = self._coordinate_spin(self._global_z() if self._global_z_enabled() else z)
        property_combo = QComboBox()
        property_combo.addItems(self.property_options)
        property_index = property_combo.findText(str(prop))
        property_combo.setCurrentIndex(max(0, property_index))
        property_combo.setFixedWidth(118)
        projector_combo = QComboBox()
        self._populate_projector_combo(projector_combo)
        projector_index = projector_combo.findData(projector)
        if projector_index < 0 and projector_combo.count() > 0:
            projector_index = 0
        projector_combo.setCurrentIndex(max(0, projector_index))
        projector_combo.setFixedWidth(220)
        property_combo.currentTextChanged.connect(
            lambda _text, widget=row_widget: self._refresh_projector_state(widget)
        )

        row_widget.title_label = title
        row_widget.nominal_x = float(x)
        row_widget.nominal_y = float(y)
        row_widget.x_spin = x_spin
        row_widget.y_spin = y_spin
        row_widget.z_spin = z_spin
        row_widget.property_combo = property_combo
        row_widget.projector_combo = projector_combo
        x_spin.valueChanged.connect(lambda _value, widget=row_widget: self._on_stop_xy_changed(widget, "x"))
        y_spin.valueChanged.connect(lambda _value, widget=row_widget: self._on_stop_xy_changed(widget, "y"))

        row_layout.addWidget(title)
        row_layout.addWidget(QLabel("X:"))
        row_layout.addWidget(x_spin)
        row_layout.addWidget(QLabel("Y:"))
        row_layout.addWidget(y_spin)
        row_layout.addWidget(QLabel("Z:"))
        row_layout.addWidget(z_spin)
        row_layout.addWidget(QLabel("Property:"))
        row_layout.addWidget(property_combo)
        row_layout.addWidget(QLabel("Projector:"))
        row_layout.addWidget(projector_combo)
        row_layout.addStretch(1)

        item = QListWidgetItem()
        item.setSizeHint(row_widget.sizeHint())
        self.stop_list.addItem(item)
        self.stop_list.setItemWidget(item, row_widget)
        self.stop_list.setCurrentItem(item)
        self._refresh_projector_state(row_widget)
        self._refresh_first_stop_constraint()

    def remove_selected_stop(self):
        row = self.stop_list.currentRow()
        if row >= 0:
            self.stop_list.takeItem(row)
        if self.stop_list.count() == 0:
            self.add_stop(0.0, 0.0, 80.0, "imaging")
        self._refresh_first_stop_constraint()

    def get_stops(self):
        stops = []
        for row in range(self.stop_list.count()):
            widget = self.stop_list.itemWidget(self.stop_list.item(row))
            if widget is None:
                continue
            stops.append(
                (
                    float(widget.x_spin.value()),
                    float(widget.y_spin.value()),
                    float(widget.z_spin.value()),
                    str(widget.property_combo.currentText()),
                    widget.projector_combo.currentData(),
                )
            )
        return stops

    def _normalize_stop(self, stop):
        projector = None
        if len(stop) >= 5:
            projector = stop[4]
        if len(stop) >= 4:
            return float(stop[0]), float(stop[1]), float(stop[2]), str(stop[3]), projector
        return float(stop[0]), float(stop[1]), float(stop[2]), "imaging", projector

    def _populate_projector_combo(self, combo):
        if not self.screens:
            combo.addItem("No projector/display detected", None)
            combo.setEnabled(False)
            return
        primary = QApplication.primaryScreen()
        for index, screen in enumerate(self.screens):
            geo = screen.geometry()
            primary_label = " primary" if screen == primary else " external/projector"
            combo.addItem(
                f"Display {index + 1}: {screen.name()}{primary_label} ({geo.width()}x{geo.height()})",
                index,
            )

    def _refresh_projector_state(self, widget):
        if widget is None:
            return
        enabled = widget.property_combo.currentText().lower() == "projection"
        widget.projector_combo.setEnabled(enabled and bool(self.screens))

    def _coordinate_spin(self, value):
        spin = QDoubleSpinBox()
        spin.setDecimals(4)
        spin.setRange(-50000.0, 50000.0)
        spin.setSingleStep(0.1)
        spin.setKeyboardTracking(False)
        spin.setValue(float(value))
        spin.setFixedWidth(92)
        return spin

    def _offset_spin(self):
        spin = self._coordinate_spin(0.0)
        spin.setSuffix(" mm")
        spin.setToolTip("Offset to add to each stop coordinate from the intended start position.")
        return spin

    def _global_z_enabled(self):
        return bool(self.global_z_check.isChecked())

    def _global_z(self):
        return float(self.global_z_spin.value())

    def _start_offset_x(self):
        return float(self.start_offset_x_spin.value())

    def _start_offset_y(self):
        return float(self.start_offset_y_spin.value())

    def _corrected_x(self, nominal_x):
        return float(nominal_x) + self._start_offset_x()

    def _corrected_y(self, nominal_y):
        return float(nominal_y) + self._start_offset_y()

    def _on_stop_xy_changed(self, widget, axis):
        if self._applying_offset or widget is None:
            return
        if axis == "x":
            widget.nominal_x = float(widget.x_spin.value()) - self._start_offset_x()
        elif axis == "y":
            widget.nominal_y = float(widget.y_spin.value()) - self._start_offset_y()

    def _set_corrected_xy(self, widget):
        if widget is None:
            return
        widget.x_spin.setValue(self._corrected_x(getattr(widget, "nominal_x", widget.x_spin.value())))
        widget.y_spin.setValue(self._corrected_y(getattr(widget, "nominal_y", widget.y_spin.value())))

    def _apply_start_offset_to_all_stops(self):
        self._applying_offset = True
        try:
            for row in range(self.stop_list.count()):
                widget = self.stop_list.itemWidget(self.stop_list.item(row))
                self._set_corrected_xy(widget)
        finally:
            self._applying_offset = False

    def _apply_global_z_to_all_stops(self):
        enabled = self._global_z_enabled()
        self.global_z_spin.setEnabled(enabled)
        for row in range(self.stop_list.count()):
            widget = self.stop_list.itemWidget(self.stop_list.item(row))
            if widget is None:
                continue
            if enabled:
                widget.z_spin.setValue(self._global_z())
            widget.z_spin.setEnabled(not enabled)

    def _refresh_first_stop_constraint(self):
        self._applying_offset = True
        try:
            for row in range(self.stop_list.count()):
                widget = self.stop_list.itemWidget(self.stop_list.item(row))
                if widget is None:
                    continue
                widget.title_label.setText(f"Stop {row + 1}")
                is_first = row == 0
                if is_first:
                    widget.nominal_x = 0.0
                    widget.nominal_y = 0.0
                    self._set_corrected_xy(widget)
                    start_index = widget.property_combo.findText("Start")
                    if start_index >= 0:
                        widget.property_combo.setCurrentIndex(start_index)
                widget.x_spin.setEnabled(not is_first)
                widget.y_spin.setEnabled(not is_first)
                widget.z_spin.setEnabled(not self._global_z_enabled())
                widget.property_combo.setEnabled(not is_first)
                self._refresh_projector_state(widget)
        finally:
            self._applying_offset = False
        self._apply_global_z_to_all_stops()

