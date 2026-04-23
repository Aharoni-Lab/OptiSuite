from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

import cv2
import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from PIL import Image, ImageTk

from core.results import AnalyzerConfig, AnalyzerResult, ChartType, OverlayItem
from core.router import SUPPORTED_CHART_TYPES, TargetRouter
from core.visualization import render_result_image

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    DND_FILES = None
    TkinterDnD = None


SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff"}
VERTICAL_PROFILE_COLOR_HEX = "#d81b60"
HORIZONTAL_PROFILE_COLOR_HEX = "#1e88e5"
# OpenCV draws on BGR images before they are converted to RGB for Tk/PIL display.
VERTICAL_PROFILE_COLOR_BGR = (96, 27, 216)
HORIZONTAL_PROFILE_COLOR_BGR = (229, 136, 30)


class ResolutionApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Multi-target Resolution App")
        self.root.geometry("1280x840")
        self.root.minsize(980, 700)

        self.selected_items: list[str] = []
        self.analysis_results: list[dict[str, object]] = []
        self.preview_photo: ImageTk.PhotoImage | None = None
        self.plot_photo: ImageTk.PhotoImage | None = None
        self.current_overlay_image: Image.Image | None = None
        self.current_plot_image: Image.Image | None = None

        self.override_var = tk.StringVar(value="auto")
        self.threshold_var = tk.DoubleVar(value=0.2)
        self.preview_var = tk.BooleanVar(value=False)
        self.debug_var = tk.BooleanVar(value=False)
        self.model_assist_var = tk.BooleanVar(value=True)
        self.fallback_var = tk.BooleanVar(value=True)
        self.flip_mode_var = tk.StringVar(value="auto")
        self.status_var = tk.StringVar(value="Add images or folders, then run analysis.")
        self.output_group_var = tk.StringVar(value="n/a")
        self.output_element_var = tk.StringVar(value="n/a")
        self.output_lp_mm_var = tk.StringVar(value="n/a")
        self.output_mm_var = tk.StringVar(value="n/a")
        self.plot_group_var = tk.IntVar(value=2)
        self.plot_element_var = tk.IntVar(value=1)
        self.plot_info_var = tk.StringVar(value="Select a USAF result, then choose a group and element to plot.")
        self.preview_base_image: Image.Image | None = None
        self.preview_scale = 1.0
        self.preview_min_scale = 0.1
        self.preview_max_scale = 8.0
        self.preview_zoom_step = 1.08
        self.preview_zoom_var = tk.StringVar(value="100%")

        self._build_ui()

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=12)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=0)
        container.columnconfigure(1, weight=1)
        container.rowconfigure(1, weight=1)
        container.rowconfigure(2, weight=1)

        header = ttk.Label(
            container,
            text="Drop microscopy resolution-chart images, detect the target style, and report the highest feature above 20% contrast.",
        )
        header.grid(row=0, column=0, columnspan=2, sticky="w")

        left_panel = ttk.Frame(container)
        left_panel.grid(row=1, column=0, rowspan=2, sticky="nsw", padx=(0, 12))
        left_panel.columnconfigure(0, weight=1)

        input_frame = ttk.LabelFrame(left_panel, text="Inputs", padding=10)
        input_frame.grid(row=0, column=0, sticky="nsew")
        input_frame.columnconfigure(0, weight=1)
        input_frame.rowconfigure(1, weight=1)

        drop_text = "DROP IMAGES OR FOLDERS HERE\n\nDrag and drop files or folders into this box\nor click here to choose images."
        if DND_FILES is None:
            drop_text += "\n\nDrag and drop is unavailable because tkinterdnd2 is not installed."
        self.drop_label = tk.Label(
            input_frame,
            text=drop_text,
            anchor="center",
            justify="center",
            relief="solid",
            borderwidth=2,
            background="#1f3550",
            foreground="#ffffff",
            activebackground="#274264",
            activeforeground="#ffffff",
            padx=24,
            pady=28,
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
        )
        self.drop_label.grid(row=0, column=0, sticky="ew", pady=(0, 6), ipady=8)
        self.drop_label.bind("<Button-1>", lambda _event: self._choose_images())
        if DND_FILES is not None:
            self.drop_label.drop_target_register(DND_FILES)
            self.drop_label.dnd_bind("<<Drop>>", self._handle_drop)

        list_frame = ttk.Frame(input_frame)
        list_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.input_listbox = tk.Listbox(list_frame, width=42, height=18)
        self.input_listbox.grid(row=0, column=0, sticky="nsew")
        input_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.input_listbox.yview)
        input_scrollbar.grid(row=0, column=1, sticky="ns")
        self.input_listbox.configure(yscrollcommand=input_scrollbar.set)

        input_controls = ttk.Frame(input_frame)
        input_controls.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(input_controls, text="Add Images", command=self._choose_images, width=16).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(input_controls, text="Add Folder", command=self._choose_folder, width=16).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(input_controls, text="Clear", command=self._clear_inputs).grid(row=0, column=2)

        settings_frame = ttk.LabelFrame(left_panel, text="Settings", padding=10)
        settings_frame.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        settings_frame.columnconfigure(1, weight=1)

        ttk.Label(settings_frame, text="Chart type").grid(row=0, column=0, sticky="w")
        override_menu = ttk.Combobox(
            settings_frame,
            textvariable=self.override_var,
            values=SUPPORTED_CHART_TYPES,
            state="readonly",
        )
        override_menu.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        ttk.Label(settings_frame, text="Contrast threshold").grid(row=1, column=0, sticky="w", pady=(8, 0))
        threshold_spinbox = ttk.Spinbox(settings_frame, from_=0.05, to=0.95, increment=0.05, textvariable=self.threshold_var)
        threshold_spinbox.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))

        ttk.Label(settings_frame, text="USAF flip").grid(row=2, column=0, sticky="w", pady=(8, 0))
        flip_menu = ttk.Combobox(
            settings_frame,
            textvariable=self.flip_mode_var,
            values=("auto", "not_flipped", "flipped"),
            state="readonly",
        )
        flip_menu.grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))

        ttk.Checkbutton(settings_frame, text="Preview OpenCV debug windows", variable=self.preview_var).grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Checkbutton(settings_frame, text="Verbose debug mode", variable=self.debug_var).grid(row=4, column=0, columnspan=2, sticky="w")
        ttk.Checkbutton(settings_frame, text="Allow model assist inside analyzers", variable=self.model_assist_var).grid(row=5, column=0, columnspan=2, sticky="w")
        ttk.Checkbutton(settings_frame, text="Allow model fallback in router", variable=self.fallback_var).grid(row=6, column=0, columnspan=2, sticky="w")

        action_frame = ttk.Frame(left_panel)
        action_frame.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        self.run_button = ttk.Button(action_frame, text="Run Analysis", command=self._run_analysis)
        self.run_button.grid(row=0, column=0, sticky="ew")
        ttk.Button(action_frame, text="Export JSON", command=self._export_json).grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(action_frame, text="Export CSV", command=self._export_csv).grid(row=2, column=0, sticky="ew", pady=(8, 0))

        right_panel = ttk.Frame(container)
        right_panel.grid(row=1, column=1, rowspan=2, sticky="nsew")
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(0, weight=1)
        right_panel.rowconfigure(1, weight=1)

        results_frame = ttk.LabelFrame(right_panel, text="Results", padding=10)
        results_frame.grid(row=0, column=0, sticky="nsew")
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)

        columns = ("image", "chart_type", "reading", "confidence", "status")
        self.results_tree = ttk.Treeview(results_frame, columns=columns, show="headings", height=10)
        for column, heading, width in (
            ("image", "Image", 220),
            ("chart_type", "Chart Type", 120),
            ("reading", "Reading", 220),
            ("confidence", "Confidence", 90),
            ("status", "Status", 100),
        ):
            self.results_tree.heading(column, text=heading)
            self.results_tree.column(column, width=width, anchor="w")
        self.results_tree.grid(row=0, column=0, sticky="nsew")
        self.results_tree.bind("<<TreeviewSelect>>", self._on_result_selected)
        result_scrollbar = ttk.Scrollbar(results_frame, orient="vertical", command=self.results_tree.yview)
        result_scrollbar.grid(row=0, column=1, sticky="ns")
        self.results_tree.configure(yscrollcommand=result_scrollbar.set)

        lower_panel = ttk.Panedwindow(right_panel, orient="horizontal")
        lower_panel.grid(row=1, column=0, sticky="nsew", pady=(12, 0))

        preview_frame = ttk.LabelFrame(lower_panel, text="Overlay Preview", padding=10)
        details_frame = ttk.LabelFrame(lower_panel, text="Output Data And Plot", padding=10)
        lower_panel.add(preview_frame, weight=3)
        lower_panel.add(details_frame, weight=2)

        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)
        self.preview_canvas = tk.Canvas(preview_frame, background="#1e1e1e", highlightthickness=0)
        self.preview_canvas.grid(row=0, column=0, sticky="nsew")
        preview_y_scrollbar = ttk.Scrollbar(preview_frame, orient="vertical", command=self.preview_canvas.yview)
        preview_y_scrollbar.grid(row=0, column=1, sticky="ns")
        preview_x_scrollbar = ttk.Scrollbar(preview_frame, orient="horizontal", command=self.preview_canvas.xview)
        preview_x_scrollbar.grid(row=1, column=0, sticky="ew")
        self.preview_canvas.configure(xscrollcommand=preview_x_scrollbar.set, yscrollcommand=preview_y_scrollbar.set)
        self.preview_canvas.bind("<MouseWheel>", self._on_preview_mousewheel)
        self.preview_canvas.bind("<Button-4>", self._on_preview_mousewheel)
        self.preview_canvas.bind("<Button-5>", self._on_preview_mousewheel)
        self.preview_canvas.bind("<ButtonPress-1>", self._on_preview_pan_start)
        self.preview_canvas.bind("<B1-Motion>", self._on_preview_pan_move)
        self.preview_canvas.bind("<Configure>", self._on_preview_canvas_configure)
        preview_controls = ttk.Frame(preview_frame)
        preview_controls.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(preview_controls, text="Reset Zoom", command=self._reset_preview_zoom).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(preview_controls, text="Export Overlay", command=self._export_overlay_preview).grid(row=0, column=1, padx=(0, 8))
        ttk.Label(preview_controls, textvariable=self.preview_zoom_var).grid(row=0, column=2, sticky="w")

        details_frame.columnconfigure(0, weight=1)
        details_frame.rowconfigure(2, weight=1)
        details_frame.rowconfigure(3, weight=1)

        output_frame = ttk.LabelFrame(details_frame, text="Output Data", padding=8)
        output_frame.grid(row=0, column=0, sticky="ew")
        output_frame.columnconfigure(1, weight=1)

        ttk.Label(output_frame, text="Group #").grid(row=0, column=0, sticky="w")
        ttk.Label(output_frame, textvariable=self.output_group_var).grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Label(output_frame, text="Element #").grid(row=1, column=0, sticky="w")
        ttk.Label(output_frame, textvariable=self.output_element_var).grid(row=1, column=1, sticky="w", padx=(8, 0))
        ttk.Label(output_frame, text="Resolution (lp/mm)").grid(row=2, column=0, sticky="w")
        ttk.Label(output_frame, textvariable=self.output_lp_mm_var).grid(row=2, column=1, sticky="w", padx=(8, 0))
        ttk.Label(output_frame, text="Resolution (mm)").grid(row=3, column=0, sticky="w")
        ttk.Label(output_frame, textvariable=self.output_mm_var).grid(row=3, column=1, sticky="w", padx=(8, 0))

        plot_frame = ttk.LabelFrame(details_frame, text="Cross Section Plot", padding=8)
        plot_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        plot_frame.columnconfigure(5, weight=1)

        ttk.Label(plot_frame, text="Group #").grid(row=0, column=0, sticky="w")
        self.group_spinbox = ttk.Spinbox(plot_frame, from_=1, to=10, width=6, textvariable=self.plot_group_var)
        self.group_spinbox.grid(row=0, column=1, sticky="w", padx=(6, 12))
        ttk.Label(plot_frame, text="Element #").grid(row=0, column=2, sticky="w")
        self.element_spinbox = ttk.Spinbox(plot_frame, from_=1, to=6, width=6, textvariable=self.plot_element_var)
        self.element_spinbox.grid(row=0, column=3, sticky="w", padx=(6, 12))
        self.plot_button = ttk.Button(plot_frame, text="Plot Selected Group/Element", command=self._plot_selected_group_element)
        self.plot_button.grid(row=0, column=4, sticky="w")
        ttk.Button(plot_frame, text="Export Plot", command=self._export_plot_image).grid(row=0, column=5, sticky="w", padx=(8, 0))
        ttk.Label(plot_frame, textvariable=self.plot_info_var).grid(row=1, column=0, columnspan=7, sticky="w", pady=(8, 0))

        plot_image_frame = ttk.Frame(details_frame)
        plot_image_frame.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        plot_image_frame.columnconfigure(0, weight=1)
        plot_image_frame.rowconfigure(0, weight=1)
        self.plot_label = ttk.Label(plot_image_frame, anchor="center")
        self.plot_label.grid(row=0, column=0, sticky="nsew")

        self.details_text = ScrolledText(details_frame, wrap="word", state="disabled", height=10)
        self.details_text.grid(row=3, column=0, sticky="nsew", pady=(10, 0))

        ttk.Label(container, textvariable=self.status_var).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))

    def _handle_drop(self, event) -> None:
        paths = [path.strip("{}") for path in self.root.tk.splitlist(event.data)]
        self._add_items(paths)

    def _choose_images(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select chart images",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff"), ("All files", "*.*")],
        )
        self._add_items(paths)

    def _choose_folder(self) -> None:
        folder = filedialog.askdirectory(title="Select folder with chart images")
        if folder:
            self._add_items([folder])

    def _add_items(self, paths: list[str] | tuple[str, ...]) -> None:
        added = 0
        for raw_path in paths:
            path = Path(raw_path).expanduser()
            if not path.exists():
                continue
            if path.is_dir() or path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS:
                resolved = str(path.resolve())
                if resolved not in self.selected_items:
                    self.selected_items.append(resolved)
                    added += 1
        self._refresh_input_list()
        self.status_var.set(f"Added {added} item(s)." if added else "No new valid files or folders were added.")

    def _refresh_input_list(self) -> None:
        self.input_listbox.delete(0, tk.END)
        for item in self.selected_items:
            self.input_listbox.insert(tk.END, item)

    def _clear_inputs(self) -> None:
        self.selected_items.clear()
        self.analysis_results.clear()
        self._refresh_input_list()
        for row in self.results_tree.get_children():
            self.results_tree.delete(row)
        self._set_details("")
        self.preview_canvas.delete("all")
        self.preview_canvas.configure(scrollregion=(0, 0, 0, 0))
        self.preview_base_image = None
        self.current_overlay_image = None
        self.plot_label.configure(image="", text="")
        self.current_plot_image = None
        self._set_output_fields(None)
        self.plot_info_var.set("Select a USAF result, then choose a group and element to plot.")
        self.preview_zoom_var.set("100%")
        self.status_var.set("Inputs cleared.")

    def _collect_image_paths(self) -> list[str]:
        collected: list[str] = []
        for item in self.selected_items:
            path = Path(item)
            if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS:
                collected.append(str(path))
            elif path.is_dir():
                for root_dir, _dirs, filenames in os.walk(path):
                    for filename in filenames:
                        file_path = Path(root_dir) / filename
                        if file_path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS:
                            collected.append(str(file_path))
        return sorted(dict.fromkeys(collected))

    def _build_router(self) -> TargetRouter:
        return TargetRouter(
            AnalyzerConfig(
                contrast_threshold=float(self.threshold_var.get()),
                show_preview=self.preview_var.get(),
                debug_mode=self.debug_var.get(),
                use_detection_fallback=self.fallback_var.get(),
                allow_model_assist=self.model_assist_var.get(),
                flip_mode=self.flip_mode_var.get(),
            )
        )

    def _run_analysis(self) -> None:
        image_paths = self._collect_image_paths()
        if not image_paths:
            messagebox.showinfo("No images", "Add one or more image files or folders before running.")
            return

        self.analysis_results.clear()
        for row in self.results_tree.get_children():
            self.results_tree.delete(row)

        router = self._build_router()
        override = self.override_var.get()
        self.run_button.configure(state="disabled")
        self.status_var.set("Running analysis...")
        self.root.update_idletasks()

        success_count = 0
        try:
            for image_path in image_paths:
                decision, result = router.analyze_image(image_path, override_chart_type=override)
                self.analysis_results.append({"decision": decision, "result": result})
                if result.success:
                    success_count += 1
                self._insert_result_row(result)
        finally:
            self.run_button.configure(state="normal")

        self.status_var.set(f"Finished. {success_count} of {len(image_paths)} image(s) analyzed successfully.")
        if self.analysis_results:
            first_id = self.results_tree.get_children()[0]
            self.results_tree.selection_set(first_id)
            self._on_result_selected()

    def _insert_result_row(self, result: AnalyzerResult) -> None:
        row_id = str(len(self.analysis_results) - 1)
        self.results_tree.insert(
            "",
            "end",
            iid=row_id,
            values=(
                Path(result.image_path).name,
                result.chart_type,
                result.reading.value,
                f"{result.confidence:.2f}",
                "ok" if result.success else "error",
            ),
        )

    def _on_result_selected(self, _event=None) -> None:
        selection = self.results_tree.selection()
        if not selection:
            return
        index = int(selection[0])
        payload = self.analysis_results[index]
        decision = payload["decision"]
        result: AnalyzerResult = payload["result"]
        self._show_result_preview(result)
        self._set_output_fields(result)
        self._show_result_details(decision, result)
        self._set_default_plot_selection(result)
        self._auto_update_output_plot(result)

    def _show_result_preview(
        self,
        result: AnalyzerResult,
        extra_overlay_items: list[OverlayItem] | None = None,
        preserve_view: bool = False,
    ) -> None:
        image = render_result_image(result, extra_overlay_items=extra_overlay_items)
        self._set_preview_image(image, preserve_view=preserve_view)

    def _set_preview_image(self, image: Image.Image, preserve_view: bool = False) -> None:
        previous_x = self.preview_canvas.xview()[0] if preserve_view and self.preview_base_image is not None else 0.0
        previous_y = self.preview_canvas.yview()[0] if preserve_view and self.preview_base_image is not None else 0.0
        previous_scale = self.preview_scale if preserve_view and self.preview_base_image is not None else None

        self.current_overlay_image = image.copy()
        self.preview_base_image = image
        self.preview_canvas.update_idletasks()
        canvas_width = max(self.preview_canvas.winfo_width(), 1)
        canvas_height = max(self.preview_canvas.winfo_height(), 1)
        self.preview_min_scale = min(canvas_width / image.width, canvas_height / image.height)
        self.preview_min_scale = max(self.preview_min_scale, 0.05)
        if previous_scale is None:
            self.preview_scale = self.preview_min_scale
            self._render_preview()
        else:
            self.preview_scale = min(max(previous_scale, self.preview_min_scale), self.preview_max_scale)
            self._render_preview(scroll_fraction=(previous_x, previous_y))

    def _render_preview(
        self,
        anchor_image_point: tuple[float, float] | None = None,
        anchor_canvas_point: tuple[float, float] | None = None,
        scroll_fraction: tuple[float, float] | None = None,
    ) -> None:
        if self.preview_base_image is None:
            return

        width = max(1, int(round(self.preview_base_image.width * self.preview_scale)))
        height = max(1, int(round(self.preview_base_image.height * self.preview_scale)))
        display_image = self.preview_base_image.resize((width, height), Image.Resampling.LANCZOS)
        self.preview_photo = ImageTk.PhotoImage(display_image)

        self.preview_canvas.delete("all")
        self.preview_canvas.create_image(0, 0, image=self.preview_photo, anchor="nw")
        self.preview_canvas.configure(scrollregion=(0, 0, width, height))
        self.preview_canvas.update_idletasks()
        self.preview_zoom_var.set(f"Zoom: {self.preview_scale * 100:.0f}%")

        if anchor_image_point is None or anchor_canvas_point is None:
            if scroll_fraction is not None:
                self.preview_canvas.xview_moveto(min(max(scroll_fraction[0], 0.0), 1.0))
                self.preview_canvas.yview_moveto(min(max(scroll_fraction[1], 0.0), 1.0))
            else:
                self.preview_canvas.xview_moveto(0.0)
                self.preview_canvas.yview_moveto(0.0)
            return

        canvas_width = max(self.preview_canvas.winfo_width(), 1)
        canvas_height = max(self.preview_canvas.winfo_height(), 1)
        target_x = anchor_image_point[0] * self.preview_scale
        target_y = anchor_image_point[1] * self.preview_scale
        left = target_x - anchor_canvas_point[0]
        top = target_y - anchor_canvas_point[1]
        max_left = max(0.0, width - canvas_width)
        max_top = max(0.0, height - canvas_height)
        left = min(max(left, 0.0), max_left)
        top = min(max(top, 0.0), max_top)

        if width > canvas_width:
            self.preview_canvas.xview_moveto(min(max(left / width, 0.0), 1.0))
        else:
            self.preview_canvas.xview_moveto(0.0)
        if height > canvas_height:
            self.preview_canvas.yview_moveto(min(max(top / height, 0.0), 1.0))
        else:
            self.preview_canvas.yview_moveto(0.0)

    def _on_preview_canvas_configure(self, _event=None) -> None:
        if self.preview_base_image is not None and self.preview_scale <= self.preview_min_scale + 1e-6:
            self._set_preview_image(self.preview_base_image)

    def _on_preview_mousewheel(self, event) -> None:
        if self.preview_base_image is None:
            return

        ctrl_pressed = bool(getattr(event, "state", 0) & 0x0004)
        if not ctrl_pressed:
            if getattr(event, "delta", 0):
                self.preview_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
            elif getattr(event, "num", None) == 4:
                self.preview_canvas.yview_scroll(-1, "units")
            elif getattr(event, "num", None) == 5:
                self.preview_canvas.yview_scroll(1, "units")
            return

        if getattr(event, "delta", 0):
            wheel_steps = event.delta / 120.0
        elif getattr(event, "num", None) == 4:
            wheel_steps = 1.0
        elif getattr(event, "num", None) == 5:
            wheel_steps = -1.0
        else:
            return

        factor = self.preview_zoom_step ** wheel_steps
        new_scale = min(max(self.preview_scale * factor, self.preview_min_scale), self.preview_max_scale)
        if abs(new_scale - self.preview_scale) < 1e-9:
            return

        pointer_x = self.preview_canvas.winfo_pointerx() - self.preview_canvas.winfo_rootx()
        pointer_y = self.preview_canvas.winfo_pointery() - self.preview_canvas.winfo_rooty()
        pointer_x = min(max(pointer_x, 0), max(self.preview_canvas.winfo_width() - 1, 0))
        pointer_y = min(max(pointer_y, 0), max(self.preview_canvas.winfo_height() - 1, 0))

        image_x = self.preview_canvas.canvasx(pointer_x) / self.preview_scale
        image_y = self.preview_canvas.canvasy(pointer_y) / self.preview_scale
        self.preview_scale = new_scale
        self._render_preview(anchor_image_point=(image_x, image_y), anchor_canvas_point=(pointer_x, pointer_y))

    def _reset_preview_zoom(self) -> None:
        if self.preview_base_image is None:
            return
        self.preview_scale = self.preview_min_scale
        self._render_preview()

    def _on_preview_pan_start(self, event) -> None:
        self.preview_canvas.scan_mark(event.x, event.y)

    def _on_preview_pan_move(self, event) -> None:
        self.preview_canvas.scan_dragto(event.x, event.y, gain=1)

    def _set_output_fields(self, result: AnalyzerResult | None) -> None:
        if result is None or result.chart_type != "usaf" or not result.success:
            self.output_group_var.set("-")
            self.output_element_var.set("-")
            self.output_lp_mm_var.set("-")
            self.output_mm_var.set("-")
            return

        details = result.reading.details
        self.output_group_var.set(str(details.get("group", "n/a")))
        self.output_element_var.set(str(details.get("element", "n/a")))
        lp_mm = details.get("resolution_lp_mm")
        mm_value = details.get("resolution_mm")
        self.output_lp_mm_var.set(f"{lp_mm:.4f}" if isinstance(lp_mm, (int, float)) else "n/a")
        self.output_mm_var.set(f"{mm_value:.6f}" if isinstance(mm_value, (int, float)) else "n/a")

    def _set_default_plot_selection(self, result: AnalyzerResult) -> None:
        if result.chart_type == "usaf" and result.success:
            details = result.reading.details
            group = details.get("group")
            element = details.get("element")
            if isinstance(group, int):
                self.plot_group_var.set(group)
            if isinstance(element, int):
                self.plot_element_var.set(element)
            self.plot_info_var.set("USAF result selected. Showing the best detected group/element plot.")
        else:
            self.plot_info_var.set("Cross-section plotting is currently available for USAF results only.")

    def _selected_payload(self):
        selection = self.results_tree.selection()
        if not selection:
            return None
        return self.analysis_results[int(selection[0])]

    def _auto_update_output_plot(self, result: AnalyzerResult) -> None:
        if result.chart_type != "usaf" or not result.success:
            self.plot_label.configure(image="", text="Plot available for USAF results only.")
            self.plot_photo = None
            self.current_plot_image = None
            return

        group = result.reading.details.get("group")
        element = result.reading.details.get("element")
        if isinstance(group, int):
            self.plot_group_var.set(group)
        if isinstance(element, int):
            self.plot_element_var.set(element)
        self._plot_result_group_element(result, int(self.plot_group_var.get()), int(self.plot_element_var.get()), notify=False)

    def _plot_selected_group_element(self) -> None:
        payload = self._selected_payload()
        if payload is None:
            messagebox.showinfo("No result selected", "Select a result row before plotting a group and element.")
            return

        result: AnalyzerResult = payload["result"]
        if result.chart_type != "usaf":
            messagebox.showinfo("Unsupported chart type", "Group/element cross-section plotting is currently available for USAF results only.")
            return

        group = int(self.plot_group_var.get())
        element = int(self.plot_element_var.get())
        self._plot_result_group_element(result, group, element, notify=True)

    def _plot_result_group_element(self, result: AnalyzerResult, group: int, element: int, notify: bool) -> None:
        scanlines = result.metadata.get("scanlines", {})
        key = f"{group}:{element}"
        if key not in scanlines:
            if notify:
                messagebox.showinfo("Group/element unavailable", f"No scanline was available for group {group}, element {element}.")
            self.plot_label.configure(image="", text=f"No cross-section available for G{group} E{element}.")
            self.plot_photo = None
            self.current_plot_image = None
            self.plot_info_var.set(f"No cross-section available for G{group} E{element}.")
            return

        line_data = scanlines[key]
        normalized_gray = self._load_normalized_gray(result.image_path)
        plot_line_data = self._build_plot_line_data(line_data, normalized_gray.shape)
        plot_image_full = self._build_cross_section_plot_image(normalized_gray, plot_line_data, group, element)
        self.current_plot_image = plot_image_full.copy()
        plot_image = plot_image_full.copy()
        plot_image.thumbnail((520, 300))
        self.plot_photo = ImageTk.PhotoImage(plot_image)
        self.plot_label.configure(image=self.plot_photo, text="")

        lp_mm = line_data.get("lp_per_mm")
        mm_value = line_data.get("resolution_mm")
        self.plot_info_var.set(
            f"Plotting G{group} E{element} | {lp_mm:.4f} lp/mm | {mm_value:.6f} mm"
        )
        extra_overlay_items = [
            OverlayItem(
                kind="line",
                points=[tuple(plot_line_data["vertical"]["pt_a"]), tuple(plot_line_data["vertical"]["pt_b"])],
                color=VERTICAL_PROFILE_COLOR_BGR,
                thickness=1,
            ),
            OverlayItem(
                kind="line",
                points=[tuple(plot_line_data["horizontal"]["pt_a"]), tuple(plot_line_data["horizontal"]["pt_b"])],
                color=HORIZONTAL_PROFILE_COLOR_BGR,
                thickness=1,
            ),
        ]
        self._show_result_preview(result, extra_overlay_items=extra_overlay_items, preserve_view=True)

    def _load_normalized_gray(self, image_path: str) -> np.ndarray:
        image = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
        if image is None:
            raise FileNotFoundError(f"Could not read image: {image_path}")

        if image.ndim == 2:
            gray = image
        elif image.ndim == 3:
            channel_count = image.shape[2]
            if channel_count == 1:
                gray = image[:, :, 0]
            elif channel_count == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            elif channel_count == 4:
                gray = cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
            else:
                gray = image[:, :, 0]
        else:
            raise ValueError(f"Unsupported image shape for grayscale conversion: {image.shape}")

        brightest = float(np.max(gray))
        if brightest <= 0:
            return gray.astype(np.float32)
        return gray.astype(np.float32) / brightest

    def _sample_line_profile(self, gray_image: np.ndarray, pt_a: list[int], pt_b: list[int], sample_count: int = 320) -> tuple[np.ndarray, np.ndarray]:
        xs = np.linspace(pt_a[0], pt_b[0], sample_count, dtype=np.float32)
        ys = np.linspace(pt_a[1], pt_b[1], sample_count, dtype=np.float32)
        samples = cv2.remap(
            gray_image,
            xs.reshape(1, -1),
            ys.reshape(1, -1),
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT,
        ).reshape(-1)
        distance = np.linspace(0.0, float(np.hypot(pt_b[0] - pt_a[0], pt_b[1] - pt_a[1])), sample_count)
        return distance, samples

    def _plot_seed_points(self, orientation_data: dict) -> tuple[list[int], list[int]]:
        pt_a = orientation_data.get("plot_pt_a", orientation_data["pt_a"])
        pt_b = orientation_data.get("plot_pt_b", orientation_data["pt_b"])
        return list(pt_a), list(pt_b)

    def _extend_line(self, pt_a: list[int], pt_b: list[int], image_shape: tuple[int, ...], factor: float = 5.0, min_half_length: float = 12.0) -> tuple[list[int], list[int]]:
        point_a = np.array(pt_a, dtype=np.float32)
        point_b = np.array(pt_b, dtype=np.float32)
        delta = point_b - point_a
        length = float(np.linalg.norm(delta))
        if length < 1e-6:
            return pt_a, pt_b

        unit = delta / length
        midpoint = (point_a + point_b) / 2.0
        target_half_length = max((length * factor) / 2.0, min_half_length)

        if len(image_shape) < 2:
            return pt_a, pt_b
        height, width = image_shape[:2]
        max_distance = target_half_length
        for axis, limit in ((0, width - 1), (1, height - 1)):
            component = float(unit[axis])
            if abs(component) < 1e-6:
                continue
            distance_to_min = (0.0 - midpoint[axis]) / component
            distance_to_max = (limit - midpoint[axis]) / component
            positive_candidates = [value for value in (distance_to_min, distance_to_max) if value >= 0.0]
            negative_candidates = [-value for value in (distance_to_min, distance_to_max) if value <= 0.0]
            if positive_candidates:
                max_distance = min(max_distance, min(positive_candidates))
            if negative_candidates:
                max_distance = min(max_distance, min(negative_candidates))

        half_length = max(length / 2.0, max_distance)
        extended_a = midpoint - unit * half_length
        extended_b = midpoint + unit * half_length
        return [int(round(extended_a[0])), int(round(extended_a[1]))], [int(round(extended_b[0])), int(round(extended_b[1]))]

    def _build_plot_line_data(self, line_data: dict, image_shape: tuple[int, ...]) -> dict:
        plot_line_data = dict(line_data)
        plot_vertical = dict(line_data["vertical"])
        plot_horizontal = dict(line_data["horizontal"])
        vertical_pt_a, vertical_pt_b = self._plot_seed_points(plot_vertical)
        horizontal_pt_a, horizontal_pt_b = self._plot_seed_points(plot_horizontal)
        plot_vertical["pt_a"], plot_vertical["pt_b"] = self._extend_line(
            vertical_pt_a,
            vertical_pt_b,
            image_shape,
            factor=5.0,
            min_half_length=12.0,
        )
        plot_horizontal["pt_a"], plot_horizontal["pt_b"] = self._extend_line(
            horizontal_pt_a,
            horizontal_pt_b,
            image_shape,
            factor=5.0,
            min_half_length=12.0,
        )
        plot_line_data["vertical"] = plot_vertical
        plot_line_data["horizontal"] = plot_horizontal
        return plot_line_data

    def _build_cross_section_plot_image(self, normalized_gray: np.ndarray, line_data: dict, group: int, element: int) -> Image.Image:
        fig = Figure(figsize=(5.6, 3.6), dpi=110)
        ax = fig.add_subplot(111)

        for orientation, color in (
            ("vertical", VERTICAL_PROFILE_COLOR_HEX),
            ("horizontal", HORIZONTAL_PROFILE_COLOR_HEX),
        ):
            pt_a = line_data[orientation]["pt_a"]
            pt_b = line_data[orientation]["pt_b"]
            line_length = float(np.hypot(pt_b[0] - pt_a[0], pt_b[1] - pt_a[1]))
            sample_count = max(320, int(line_length * 3))
            distance, samples = self._sample_line_profile(
                normalized_gray,
                pt_a,
                pt_b,
                sample_count=sample_count,
            )
            ax.plot(distance, samples, label=f"{orientation.title()} cross section", color=color, linewidth=1.8)

        ax.set_title(f"USAF Cross Section: Group {group}, Element {element}")
        ax.set_xlabel("Distance (pixels)")
        ax.set_ylabel("Normalized intensity")
        ax.set_ylim(0.0, 1.05)
        ax.grid(True, alpha=0.3)
        ax.legend(loc="best")
        fig.tight_layout()

        canvas = FigureCanvasAgg(fig)
        canvas.draw()
        buffer, (width, height) = canvas.print_to_buffer()
        image = Image.frombuffer("RGBA", (width, height), buffer, "raw", "RGBA", 0, 1).convert("RGB")
        return image

    def _export_image_asset(self, image: Image.Image | None, title: str) -> None:
        if image is None:
            messagebox.showinfo("Nothing to export", f"There is no {title.lower()} available yet.")
            return

        path = filedialog.asksaveasfilename(
            title=title,
            defaultextension=".png",
            filetypes=[
                ("PNG image", "*.png"),
                ("TIFF image", "*.tif *.tiff"),
                ("JPEG image", "*.jpg *.jpeg"),
                ("Bitmap image", "*.bmp"),
            ],
        )
        if not path:
            return

        save_path = Path(path)
        format_map = {
            ".png": "PNG",
            ".tif": "TIFF",
            ".tiff": "TIFF",
            ".jpg": "JPEG",
            ".jpeg": "JPEG",
            ".bmp": "BMP",
        }
        image_format = format_map.get(save_path.suffix.lower())
        if image_format is None:
            image.save(save_path)
        else:
            image.save(save_path, format=image_format)
        self.status_var.set(f"Exported {title.lower()} to {save_path}")

    def _export_overlay_preview(self) -> None:
        self._export_image_asset(self.current_overlay_image, "Export Overlay Preview")

    def _export_plot_image(self) -> None:
        self._export_image_asset(self.current_plot_image, "Export Plot")

    def _show_result_details(self, decision, result: AnalyzerResult) -> None:
        lines = [
            f"Image: {Path(result.image_path).name}",
            f"Chart type: {result.chart_type}",
            f"Router reason: {decision.reason}",
            f"Reading: {result.reading.value} {result.reading.unit}".strip(),
            f"Threshold: {result.reading.threshold:.0%}",
            f"Confidence: {result.confidence:.2f}",
            f"Summary: {result.summary}",
        ]
        if result.chart_type == "usaf":
            flip_mode = result.reading.details.get("flip_mode")
            flipped_target = result.reading.details.get("flipped_target")
            if flip_mode is not None:
                lines.append(f"Flip mode: {flip_mode}")
            if flipped_target is not None:
                lines.append(f"Detected flipped target: {flipped_target}")
        if result.warnings:
            lines.append("Warnings:")
            lines.extend(f"- {warning}" for warning in result.warnings)
        if result.error:
            lines.append(f"Error: {result.error}")
        if result.contrast_curve:
            lines.append("")
            lines.append("Contrast curve:")
            for sample in result.contrast_curve[:30]:
                freq_text = f"{sample.frequency:.4f}" if sample.frequency is not None else "n/a"
                contrast_text = f"{sample.contrast:.3f}" if sample.contrast is not None else "n/a"
                lines.append(f"- {sample.label}: freq={freq_text}, contrast={contrast_text}, pass={sample.threshold_passed}")

        self._set_details("\n".join(lines))

    def _set_details(self, text: str) -> None:
        self.details_text.configure(state="normal")
        self.details_text.delete("1.0", tk.END)
        self.details_text.insert(tk.END, text)
        self.details_text.configure(state="disabled")

    def _export_json(self) -> None:
        if not self.analysis_results:
            messagebox.showinfo("No results", "Run at least one analysis before exporting.")
            return
        path = filedialog.asksaveasfilename(title="Export JSON", defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if not path:
            return
        payload = [
            {
                "decision": {
                    "chart_type": item["decision"].chart_type,
                    "confidence": item["decision"].confidence,
                    "reason": item["decision"].reason,
                    "candidates": item["decision"].candidates,
                    "used_model_fallback": item["decision"].used_model_fallback,
                },
                "result": item["result"].to_dict(),
            }
            for item in self.analysis_results
        ]
        Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.status_var.set(f"Exported JSON to {path}")

    def _export_csv(self) -> None:
        if not self.analysis_results:
            messagebox.showinfo("No results", "Run at least one analysis before exporting.")
            return
        path = filedialog.asksaveasfilename(title="Export CSV", defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if not path:
            return
        with Path(path).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "image_name",
                    "chart_type",
                    "group",
                    "element",
                    "resolution_lp_mm",
                    "resolution_mm",
                    "reading",
                    "reading_unit",
                    "confidence",
                    "success",
                    "summary",
                    "error",
                ],
            )
            writer.writeheader()
            for item in self.analysis_results:
                result: AnalyzerResult = item["result"]
                details = result.reading.details
                writer.writerow(
                    {
                        "image_name": Path(result.image_path).name,
                        "chart_type": result.chart_type,
                        "group": details.get("group", ""),
                        "element": details.get("element", ""),
                        "resolution_lp_mm": details.get("resolution_lp_mm", ""),
                        "resolution_mm": details.get("resolution_mm", ""),
                        "reading": result.reading.value,
                        "reading_unit": result.reading.unit,
                        "confidence": f"{result.confidence:.2f}",
                        "success": result.success,
                        "summary": result.summary,
                        "error": result.error or "",
                    }
                )
        self.status_var.set(f"Exported CSV to {path}")


def main() -> None:
    root_class = TkinterDnD.Tk if TkinterDnD is not None else tk.Tk
    root = root_class()
    app = ResolutionApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

