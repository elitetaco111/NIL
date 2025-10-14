import json
import os
import copy
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont


class CoordsBuilderApp:
    HANDLE_RADIUS = 6

    def __init__(self, master):
        self.master = master
        self.master.title("Jersey Coords Builder")

        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.template_path = None
        self.team_folder = None
        self.coords_data = {}
        self.element_entries = {}
        self.current_element = None
        self.photo_image = None
        self.image_id = None
        self.blank_images = {}
        self.blank_paths = {}
        self.side = "front"
        self.drawing_temp = False
        self.temp_rect_id = None
        self.start_point = None
        self.listbox_order = []
        self.font_cache = {}
        self.rotation_scale = None
        self.rotation_value_label = None
        self.rotation_entry = None
        self.spacing_scale = None
        self.spacing_value_label = None
        self.spacing_entry = None
        self.text_entry = None
        self.font_entry = None
        self.font_browse_btn = None
        self.number_entry = None
        self.number_browse_btn = None
        self._control_guard = False

        self._build_ui()

    def _build_ui(self):
        root = self.master
        root.geometry("1100x750")

        sidebar = tk.Frame(root, padx=10, pady=10)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)

        btn_frame = tk.Frame(sidebar)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Button(btn_frame, text="Load coords.json", command=self.load_coords).pack(fill=tk.X)
        tk.Button(btn_frame, text="Load jersey blank", command=self.load_image).pack(fill=tk.X, pady=5)
        tk.Button(btn_frame, text="Save to temp-coords.json", command=self.save_coords).pack(fill=tk.X)
        tk.Button(btn_frame, text="Load team folder", command=self.load_team_folder).pack(fill=tk.X)
        side_frame = tk.Frame(btn_frame)
        side_frame.pack(fill=tk.X, pady=5)
        tk.Button(side_frame, text="Show Front", command=lambda: self._set_side("front")).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))
        tk.Button(side_frame, text="Show Back", command=lambda: self._set_side("back")).pack(side=tk.LEFT, expand=True, fill=tk.X)

        tk.Label(sidebar, text="Elements").pack(anchor="w", pady=(10, 3))
        self.element_listbox = tk.Listbox(sidebar, height=25, exportselection=False)
        self.element_listbox.pack(fill=tk.BOTH, expand=True)
        self.element_listbox.bind("<<ListboxSelect>>", self.on_element_select)

        self.include_var = tk.BooleanVar(value=True)
        self.include_check = tk.Checkbutton(
            sidebar,
            text="Include element",
            variable=self.include_var,
            command=self.on_include_toggle
        )
        self.include_check.pack(fill=tk.X, pady=(6, 6))
        self.include_check.config(state=tk.DISABLED)

        rotation_frame = tk.LabelFrame(sidebar, text="Rotation", padx=6, pady=6)
        rotation_frame.pack(fill=tk.X, pady=(0, 6))
        self.rotation_scale = tk.Scale(
            rotation_frame,
            from_=-180,
            to=180,
            orient=tk.HORIZONTAL,
            resolution=0.1,
            command=self.on_rotation_slider,
            state=tk.DISABLED
        )
        self.rotation_scale.pack(fill=tk.X)
        self.rotation_value_label = tk.Label(rotation_frame, text="--", anchor="e")
        self.rotation_value_label.pack(fill=tk.X)
        self.rotation_entry = tk.Entry(rotation_frame, state=tk.DISABLED, justify="center")
        self.rotation_entry.pack(fill=tk.X, pady=(4, 0))
        self.rotation_entry.bind("<Return>", self.on_rotation_entry_change)
        self.rotation_entry.bind("<FocusOut>", self.on_rotation_entry_change)

        spacing_frame = tk.LabelFrame(sidebar, text="Spacing Factor", padx=6, pady=6)
        spacing_frame.pack(fill=tk.X, pady=(0, 6))
        self.spacing_scale = tk.Scale(
            spacing_frame,
            from_=0.0,
            to=0.5,
            resolution=0.001,
            orient=tk.HORIZONTAL,
            command=self.on_spacing_slider,
            state=tk.DISABLED
        )
        self.spacing_scale.pack(fill=tk.X)
        self.spacing_value_label = tk.Label(spacing_frame, text="--", anchor="e")
        self.spacing_value_label.pack(fill=tk.X)
        self.spacing_entry = tk.Entry(spacing_frame, state=tk.DISABLED, justify="center")
        self.spacing_entry.pack(fill=tk.X, pady=(4, 0))
        self.spacing_entry.bind("<Return>", self.on_spacing_entry_change)
        self.spacing_entry.bind("<FocusOut>", self.on_spacing_entry_change)

        preview_frame = tk.LabelFrame(sidebar, text="Text Preview", padx=6, pady=6)
        preview_frame.pack(fill=tk.X, pady=(0, 6))
        tk.Label(preview_frame, text="Font file:").pack(anchor="w")
        font_row = tk.Frame(preview_frame)
        font_row.pack(fill=tk.X, pady=(0, 4))
        self.font_entry = tk.Entry(font_row)
        self.font_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.font_entry.config(state=tk.DISABLED)
        self.font_entry.bind("<FocusOut>", self.on_font_entry_change)
        self.font_entry.bind("<Return>", self.on_font_entry_change)
        self.font_browse_btn = tk.Button(font_row, text="Browse", command=self.on_browse_font, state=tk.DISABLED)
        self.font_browse_btn.pack(side=tk.LEFT, padx=(5, 0))

        tk.Label(preview_frame, text="Number folder:").pack(anchor="w")
        number_row = tk.Frame(preview_frame)
        number_row.pack(fill=tk.X, pady=(0, 4))
        self.number_entry = tk.Entry(number_row)
        self.number_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.number_entry.config(state=tk.DISABLED)
        self.number_entry.bind("<FocusOut>", self.on_number_entry_change)
        self.number_entry.bind("<Return>", self.on_number_entry_change)
        self.number_browse_btn = tk.Button(number_row, text="Browse", command=self.on_browse_number_folder, state=tk.DISABLED)
        self.number_browse_btn.pack(side=tk.LEFT, padx=(5, 0))
        tk.Label(preview_frame, text="Text:").pack(anchor="w")
        self.text_entry = tk.Entry(preview_frame)
        self.text_entry.pack(fill=tk.X)
        self.text_entry.config(state=tk.DISABLED)
        self.text_entry.bind("<KeyRelease>", self.on_text_entry_change)

        help_text = (
            "Instructions:\n"
            "1. Load a team folder containing coords.json and blanks.\n"
            "2. Use Show Front/Back to swap between blank images.\n"
            "3. Select an element, adjust its box/rotation, and preview numbers or text.\n"
            "4. Repeat for required items and save."
        )
        tk.Label(sidebar, text=help_text, justify=tk.LEFT, wraplength=240).pack(fill=tk.X, pady=(10, 0))

        canvas_frame = tk.Frame(root, bd=1, relief=tk.SUNKEN)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.canvas = tk.Canvas(canvas_frame, background="#202020")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<ButtonPress-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)

        self.drag_context = {"element": None, "handle": None}

    def load_coords(self):
        path = filedialog.askopenfilename(
            title="Select coords.json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            messagebox.showerror("Load Error", f"Failed to read JSON:\n{exc}")
            return

        self.template_path = path
        self.coords_data = data
        self.font_cache.clear()
        self.element_entries.clear()
        self.element_listbox.delete(0, tk.END)
        self.current_element = None
        self.listbox_order = []
        self.include_check.config(state=tk.DISABLED)
        self.include_var.set(False)
        self.rotation_scale.config(state=tk.DISABLED)
        self.rotation_scale.set(0)
        self.rotation_value_label.config(text="--")
        self.rotation_entry.config(state=tk.DISABLED)
        self.rotation_entry.delete(0, tk.END)
        self.spacing_scale.config(state=tk.DISABLED)
        self.spacing_scale.set(0.0)
        self.spacing_value_label.config(text="--")
        self.spacing_entry.config(state=tk.DISABLED)
        self.spacing_entry.delete(0, tk.END)
        self.font_entry.config(state=tk.DISABLED)
        self.font_entry.delete(0, tk.END)
        self.font_browse_btn.config(state=tk.DISABLED)
        self.text_entry.config(state=tk.DISABLED)
        self.text_entry.delete(0, tk.END)

        keys = list(data.keys())
        keys.sort()
        self.listbox_order = keys
        template_dir = os.path.dirname(path)
        for name in keys:
            base = data[name]
            coords = None
            if isinstance(base, dict) and "coords" in base and len(base["coords"]) == 4:
                coords = list(map(float, base["coords"]))
            elif isinstance(base, list) and len(base) == 4:
                coords = list(map(float, base))

            meta = copy.deepcopy(base) if isinstance(base, dict) else None

            # Always allow rotation for FrontNumber and BackNumber
            is_number = name in ("FrontNumber", "BackNumber")
            has_rotation = (
                isinstance(base, dict) and "rotation" in base
            ) or is_number
            rotation_val = 0.0
            if has_rotation:
                try:
                    rotation_val = float(meta.get("rotation", 0.0)) if meta else 0.0
                except (TypeError, ValueError):
                    rotation_val = 0.0

            has_spacing = isinstance(base, dict) and "spacing_factor" in base
            spacing_val = 0.06
            if has_spacing:
                try:
                    spacing_val = float(meta.get("spacing_factor", 0.06))
                except (TypeError, ValueError):
                    spacing_val = 0.06

            font_path = None
            number_folder = None
            if isinstance(base, dict):
                font_candidate = base.get("font")
                if font_candidate:
                    resolved = self._resolve_font_path(font_candidate, base_dir_override=template_dir)
                    font_path = resolved or font_candidate
                number_folder = base.get("number_folder")

            self.element_entries[name] = {
                "coords": coords,
                "rect_id": None,
                "handle_ids": [],
                "active": True,
                "meta": meta,
                "rotation": rotation_val,
                "has_rotation": has_rotation,
                "spacing": spacing_val,
                "has_spacing": has_spacing and not is_number,
                "text": "12" if is_number else "",
                "font_path": font_path,
                "preview_id": None,
                "preview_photo": None,
                "is_number": is_number,
                "number_folder": number_folder
            }
            self.element_listbox.insert(tk.END, self._label_for(name))

        messagebox.showinfo("Coords Loaded", f"Loaded {len(keys)} elements.")

    def load_team_folder(self):
        folder = filedialog.askdirectory(title="Select team folder")
        if not folder:
            return

        coords_path = os.path.join(folder, "coords.json")
        front_path = os.path.join(folder, "blanks", "front.png")
        back_path = os.path.join(folder, "blanks", "back.png")

        if not os.path.isfile(coords_path):
            messagebox.showerror("Load Error", "coords.json not found in selected folder.")
            return
        if not os.path.isfile(front_path) or not os.path.isfile(back_path):
            messagebox.showerror("Load Error", "Missing blanks/front.png or blanks/back.png.")
            return

        try:
            with open(coords_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            messagebox.showerror("Load Error", f"Failed to read JSON:\n{exc}")
            return

        self.team_folder = folder
        self.template_path = coords_path
        self.blank_paths = {"front": front_path, "back": back_path}
        self.blank_images = {}
        try:
            self.blank_images["front"] = Image.open(front_path).convert("RGBA")
            self.blank_images["back"] = Image.open(back_path).convert("RGBA")
        except Exception as exc:
            messagebox.showerror("Image Error", f"Failed to load blank images:\n{exc}")
            return

        self.coords_data = data
        self.font_cache.clear()
        self.element_entries.clear()
        self.element_listbox.delete(0, tk.END)
        self.current_element = None
        self.listbox_order = []
        self.include_check.config(state=tk.DISABLED)
        self.include_var.set(False)
        self.rotation_scale.config(state=tk.DISABLED)
        self.rotation_scale.set(0)
        self.rotation_value_label.config(text="--")
        self.rotation_entry.config(state=tk.DISABLED)
        self.rotation_entry.delete(0, tk.END)
        self.spacing_scale.config(state=tk.DISABLED)
        self.spacing_scale.set(0.0)
        self.spacing_value_label.config(text="--")
        self.spacing_entry.config(state=tk.DISABLED)
        self.spacing_entry.delete(0, tk.END)
        self.font_entry.config(state=tk.DISABLED)
        self.font_entry.delete(0, tk.END)
        self.font_browse_btn.config(state=tk.DISABLED)
        self.number_entry.config(state=tk.DISABLED)
        self.number_entry.delete(0, tk.END)
        self.number_browse_btn.config(state=tk.DISABLED)
        self.text_entry.config(state=tk.DISABLED)
        self.text_entry.delete(0, tk.END)

        keys = sorted(data.keys())
        self.listbox_order = keys
        for name in keys:
            base = data[name]
            coords = None
            if isinstance(base, dict) and "coords" in base and len(base["coords"]) == 4:
                coords = list(map(float, base["coords"]))
            elif isinstance(base, list) and len(base) == 4:
                coords = list(map(float, base))

            meta = copy.deepcopy(base) if isinstance(base, dict) else None
            is_number = name in ("FrontNumber", "BackNumber", "FLShoulder", "FRShoulder", "BLShoulder", "BRShoulder")
            has_rotation = (isinstance(base, dict) and "rotation" in base) or is_number
            rotation_val = 0.0
            if has_rotation:
                try:
                    rotation_val = float(meta.get("rotation", 0.0)) if meta else 0.0
                except (TypeError, ValueError):
                    rotation_val = 0.0

            has_spacing = isinstance(base, dict) and "spacing_factor" in base
            spacing_val = 0.06
            if has_spacing:
                try:
                    spacing_val = float(meta.get("spacing_factor", 0.06))
                except (TypeError, ValueError):
                    spacing_val = 0.06

            font_path = None
            if name == "NamePlate":
                candidate = os.path.join(folder, "fonts", "NamePlate.otf")
                if os.path.isfile(candidate):
                    font_path = candidate

            number_folder = None
            if is_number:
                number_folder = self._default_number_folder(name)

            self.element_entries[name] = {
                "coords": coords,
                "rect_id": None,
                "handle_ids": [],
                "active": True,
                "meta": meta,
                "rotation": rotation_val,
                "has_rotation": has_rotation,
                "spacing": spacing_val,
                "has_spacing": name == "NamePlate" and has_spacing,
                "text": "12" if is_number else "",
                "font_path": font_path,
                "preview_id": None,
                "preview_photo": None,
                "is_number": is_number,
                "number_folder": number_folder
            }
            self.element_listbox.insert(tk.END, self._label_for(name))

        messagebox.showinfo("Team Loaded", f"Loaded {len(keys)} elements.")
        self._set_side("front")

        
    def load_image(self):
        path = filedialog.askopenfilename(
            title="Select jersey blank image",
            filetypes=[("Image Files", "*.png;*.jpg;*.jpeg"), ("All Files", "*.*")]
        )
        if not path:
            return

        try:
            img = Image.open(path).convert("RGBA")
        except Exception as exc:
            messagebox.showerror("Image Error", f"Failed to load image:\n{exc}")
            return

        width, height = img.size
        self.canvas.config(width=width, height=height, scrollregion=(0, 0, width, height))
        self.canvas.delete("all")
        self.photo_image = ImageTk.PhotoImage(img)
        self.image_id = self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo_image)

        for entry in self.element_entries.values():
            entry["rect_id"] = None
            entry["handle_ids"] = []
            entry["preview_id"] = None
            entry["preview_photo"] = None

        for name, entry in self.element_entries.items():
            coords = entry["coords"]
            if coords:
                self._draw_element(name, coords)

    def on_element_select(self, _event):
        selection = self.element_listbox.curselection()
        if not selection:
            self.current_element = None
            self.include_check.config(state=tk.DISABLED)
            self.include_var.set(False)
            self._control_guard = True
            self.rotation_scale.config(state=tk.DISABLED)
            self.rotation_scale.set(0)
            self.rotation_value_label.config(text="--")
            self.rotation_entry.config(state=tk.DISABLED)
            self.rotation_entry.delete(0, tk.END)
            self.spacing_scale.config(state=tk.DISABLED)
            self.spacing_scale.set(0.0)
            self.spacing_value_label.config(text="--")
            self.spacing_entry.config(state=tk.DISABLED)
            self.spacing_entry.delete(0, tk.END)
            self.font_entry.config(state=tk.DISABLED)
            self.font_entry.delete(0, tk.END)
            self.font_browse_btn.config(state=tk.DISABLED)
            self.text_entry.config(state=tk.DISABLED)
            self.text_entry.delete(0, tk.END)
            self._control_guard = False
            return
        idx = selection[0]
        name = self.listbox_order[idx]
        self.current_element = name
        entry = self.element_entries.get(name)
        self._control_guard = True
        if entry:
            self.include_check.config(state=tk.NORMAL)
            self.include_var.set(entry.get("active", True))
            if entry.get("has_rotation"):
                self.rotation_scale.config(state=tk.NORMAL)
                self.rotation_scale.set(entry.get("rotation", 0.0))
                self.rotation_value_label.config(text=f"{entry.get('rotation', 0.0):.1f}°")
                self.rotation_entry.config(state=tk.NORMAL)
                self.rotation_entry.delete(0, tk.END)
                self.rotation_entry.insert(0, f"{entry.get('rotation', 0.0):.2f}")
            else:
                self.rotation_scale.config(state=tk.DISABLED)
                self.rotation_scale.set(0)
                self.rotation_value_label.config(text="--")
                self.rotation_entry.config(state=tk.DISABLED)
                self.rotation_entry.delete(0, tk.END)
            if entry.get("has_spacing"):
                self.spacing_scale.config(state=tk.NORMAL)
                self.spacing_scale.set(entry.get("spacing", 0.06))
                self.spacing_value_label.config(text=f"{entry.get('spacing', 0.06):.3f}")
                self.spacing_entry.config(state=tk.NORMAL)
                self.spacing_entry.delete(0, tk.END)
                self.spacing_entry.insert(0, f"{entry.get('spacing', 0.06):.3f}")
            else:
                self.spacing_scale.config(state=tk.DISABLED)
                self.spacing_scale.set(0.0)
                self.spacing_value_label.config(text="--")
                self.spacing_entry.config(state=tk.DISABLED)
                self.spacing_entry.delete(0, tk.END)

            if entry.get("is_number"):
                self.font_entry.config(state=tk.DISABLED)
                self.font_entry.delete(0, tk.END)
                self.font_browse_btn.config(state=tk.DISABLED)
                self.number_entry.config(state=tk.NORMAL)
                self.number_entry.delete(0, tk.END)
                if entry.get("number_folder"):
                    self.number_entry.insert(0, entry["number_folder"])
                self.number_browse_btn.config(state=tk.NORMAL)
            else:
                self.font_entry.config(state=tk.NORMAL)
                self.font_entry.delete(0, tk.END)
                if entry.get("font_path"):
                    self.font_entry.insert(0, entry["font_path"])
                self.font_browse_btn.config(state=tk.NORMAL)
                self.number_entry.config(state=tk.DISABLED)
                self.number_entry.delete(0, tk.END)
                self.number_browse_btn.config(state=tk.DISABLED)

            self.text_entry.config(state=tk.NORMAL)
            self.text_entry.delete(0, tk.END)
            if entry.get("text"):
                self.text_entry.insert(0, entry["text"])
            elif entry.get("is_number"):
                self.text_entry.insert(0, "12")
        else:
            self.include_check.config(state=tk.DISABLED)
            self.include_var.set(False)
            self.rotation_scale.config(state=tk.DISABLED)
            self.rotation_scale.set(0)
            self.rotation_value_label.config(text="--")
            self.rotation_entry.config(state=tk.DISABLED)
            self.rotation_entry.delete(0, tk.END)
            self.spacing_scale.config(state=tk.DISABLED)
            self.spacing_scale.set(0.0)
            self.spacing_value_label.config(text="--")
            self.spacing_entry.config(state=tk.DISABLED)
            self.spacing_entry.delete(0, tk.END)
            self.font_entry.config(state=tk.DISABLED)
            self.font_entry.delete(0, tk.END)
            self.font_browse_btn.config(state=tk.DISABLED)
            self.text_entry.config(state=tk.DISABLED)
            self.text_entry.delete(0, tk.END)
        self._control_guard = False
        self._highlight_element(name)
        self._update_preview(name)

    def on_canvas_press(self, event):
        if not self.current_element or not self.coords_data:
            return
        entry = self.element_entries.get(self.current_element)
        if not entry or not entry.get("active", True):
            return
        if not self.photo_image:
            messagebox.showwarning("No Image", "Load a jersey blank before placing coordinates.")
            return

        hit = self._locate_handle(event.x, event.y)
        if hit:
            self.drag_context["element"], self.drag_context["handle"] = hit
            return

        self.drawing_temp = True
        self.start_point = (event.x, event.y)
        if self.temp_rect_id:
            self.canvas.delete(self.temp_rect_id)
        color = "#00ffae"
        self.temp_rect_id = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline=color, width=2, dash=(4, 2)
        )

    def on_canvas_drag(self, event):
        if self.drag_context["handle"] is not None:
            self._drag_handle(event.x, event.y)
        elif self.drawing_temp and self.temp_rect_id:
            self.canvas.coords(self.temp_rect_id, self.start_point[0], self.start_point[1], event.x, event.y)

    def on_canvas_release(self, event):
        if self.drag_context["handle"] is not None:
            self.drag_context["handle"] = None
            self.drag_context["element"] = None
            self._refresh_listbox_labels()
            return

        if self.drawing_temp and self.temp_rect_id:
            x0, y0, x1, y1 = self.canvas.coords(self.temp_rect_id)
            self.canvas.delete(self.temp_rect_id)
            self.temp_rect_id = None
            self.drawing_temp = False
            if abs(x1 - x0) < 5 or abs(y1 - y0) < 5:
                return
            coords = [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]
            self._draw_element(self.current_element, coords)
            self._refresh_listbox_labels()

    def _draw_element(self, name, coords):
        entry = self.element_entries.get(name)
        if not entry:
            return

        coords = list(map(float, coords))
        entry["coords"] = coords

        if not entry.get("active", True):
            self._hide_element_visuals(name)
            return

        if entry["rect_id"] is None:
            rect_id = self.canvas.create_rectangle(*coords, outline="#19f38d", width=2)
            entry["rect_id"] = rect_id
        else:
            self.canvas.coords(entry["rect_id"], *coords)

        for hid in entry["handle_ids"]:
            self.canvas.delete(hid)
        entry["handle_ids"] = []

        points = [
            (coords[0], coords[1]),
            (coords[2], coords[1]),
            (coords[2], coords[3]),
            (coords[0], coords[3])
        ]

        for idx, (x, y) in enumerate(points):
            handle_id = self._create_handle(name, idx, x, y)
            entry["handle_ids"].append(handle_id)

        self._highlight_element(name)
        self._update_preview(name)
        self._refresh_listbox_labels()

    def _highlight_element(self, name):
        for elem, entry in self.element_entries.items():
            rect_id = entry["rect_id"]
            if rect_id:
                active = entry.get("active", True)
                if active:
                    color = "#00ffd0" if elem == name else "#35a7ff"
                    width = 3 if elem == name else 1
                    handle_selected = "#00ffa0"
                    handle_default = "#f2e75d"
                else:
                    color = "#7a7a7a" if elem == name else "#555555"
                    width = 2 if elem == name else 1
                    handle_selected = "#a8a8a8"
                    handle_default = "#666666"
                self.canvas.itemconfigure(rect_id, outline=color, width=width)
                for hid in entry["handle_ids"]:
                    fill = handle_selected if elem == name else handle_default
                    self.canvas.itemconfigure(hid, fill=fill)

    def _create_handle(self, name, idx, x, y):
        r = self.HANDLE_RADIUS
        handle_id = self.canvas.create_oval(x - r, y - r, x + r, y + r, fill="#f2e75d", outline="#222")
        self.canvas.tag_bind(handle_id, "<ButtonPress-1>",
                             lambda e, n=name, i=idx: self._start_handle_drag(n, i))
        self.canvas.tag_bind(handle_id, "<B1-Motion>",
                             lambda e, n=name, i=idx: self._handle_drag_motion(e, n, i))
        self.canvas.tag_bind(handle_id, "<ButtonRelease-1>",
                             lambda e: self._stop_handle_drag())
        return handle_id

    def _start_handle_drag(self, name, idx):
        self.drag_context["element"] = name
        self.drag_context["handle"] = idx
        self.current_element = name
        self._highlight_element(name)

    def _handle_drag_motion(self, event, name, idx):
        if self.drag_context["handle"] is None:
            return
        self._drag_handle(event.x, event.y, name=name, idx=idx)

    def _drag_handle(self, x, y, name=None, idx=None):
        name = name or self.drag_context["element"]
        idx = idx or self.drag_context["handle"]
        if not name or idx is None:
            return

        entry = self.element_entries.get(name)
        if not entry or entry["coords"] is None or not entry.get("active", True):
            return

        coords = entry["coords"][:]
        if idx == 0:
            coords[0], coords[1] = x, y
        elif idx == 1:
            coords[2], coords[1] = x, y
        elif idx == 2:
            coords[2], coords[3] = x, y
        elif idx == 3:
            coords[0], coords[3] = x, y

        x0, x1 = sorted([coords[0], coords[2]])
        y0, y1 = sorted([coords[1], coords[3]])
        coords = [x0, y0, x1, y1]
        entry["coords"] = coords

        self.canvas.coords(entry["rect_id"], *coords)
        self._update_handle_positions(name)
        self._highlight_element(name)
        self._update_preview(name)

    def _stop_handle_drag(self):
        self.drag_context["handle"] = None
        self.drag_context["element"] = None
        self._refresh_listbox_labels()

    def _update_handle_positions(self, name):
        entry = self.element_entries.get(name)
        if not entry or not entry["coords"]:
            return
        coords = entry["coords"]
        points = [
            (coords[0], coords[1]),
            (coords[2], coords[1]),
            (coords[2], coords[3]),
            (coords[0], coords[3])
        ]
        r = self.HANDLE_RADIUS
        for handle_id, (x, y) in zip(entry["handle_ids"], points):
            self.canvas.coords(handle_id, x - r, y - r, x + r, y + r)

    def _locate_handle(self, x, y):
        r = self.HANDLE_RADIUS + 3
        hits = self.canvas.find_overlapping(x - r, y - r, x + r, y + r)
        for item in hits:
            for name, entry in self.element_entries.items():
                if item in entry["handle_ids"]:
                    if not entry.get("active", True):
                        continue
                    idx = entry["handle_ids"].index(item)
                    return name, idx
        return None

    def _label_for(self, name):
        entry = self.element_entries.get(name)
        if not entry:
            return name
        parts = []
        if not entry.get("active", True):
            parts.append("[skip]")
        if entry.get("coords") is not None:
            parts.append("✓")
        prefix = (" ".join(parts) + " ") if parts else ""
        return f"{prefix}{name}"

    def _refresh_listbox_labels(self):
        if not self.listbox_order:
            return
        selected = {self.listbox_order[i] for i in self.element_listbox.curselection()}
        self.element_listbox.delete(0, tk.END)
        for name in self.listbox_order:
            self.element_listbox.insert(tk.END, self._label_for(name))
        for idx, name in enumerate(self.listbox_order):
            if name in selected:
                self.element_listbox.selection_set(idx)

    def on_rotation_slider(self, value):
        if self._control_guard or not self.current_element:
            return
        entry = self.element_entries.get(self.current_element)
        if not entry or not entry.get("has_rotation"):
            return
        try:
            deg = float(value)
        except (TypeError, ValueError):
            return
        entry["rotation"] = deg
        self.rotation_value_label.config(text=f"{deg:.1f}°")
        if self.rotation_entry["state"] == tk.NORMAL:
            self._control_guard = True
            self.rotation_entry.delete(0, tk.END)
            self.rotation_entry.insert(0, f"{deg:.2f}")
            self._control_guard = False
        self._update_preview(self.current_element)

    def on_rotation_entry_change(self, _event=None):
        if self._control_guard or not self.current_element:
            return
        entry = self.element_entries.get(self.current_element)
        if not entry or not entry.get("has_rotation") or self.rotation_entry["state"] == tk.DISABLED:
            return
        raw = self.rotation_entry.get().strip()
        if not raw:
            return
        try:
            deg = float(raw)
        except ValueError:
            return
        deg = max(-180.0, min(180.0, deg))
        entry["rotation"] = deg
        self._control_guard = True
        self.rotation_scale.set(deg)
        self.rotation_value_label.config(text=f"{deg:.1f}°")
        self.rotation_entry.delete(0, tk.END)
        self.rotation_entry.insert(0, f"{deg:.2f}")
        self._control_guard = False
        self._update_preview(self.current_element)

    def on_spacing_slider(self, value):
        if self._control_guard or not self.current_element:
            return
        entry = self.element_entries.get(self.current_element)
        if not entry or not entry.get("has_spacing"):
            return
        try:
            spacing = float(value)
        except (TypeError, ValueError):
            return
        spacing = max(0.0, min(0.5, spacing))
        entry["spacing"] = spacing
        self.spacing_value_label.config(text=f"{spacing:.3f}")
        if self.spacing_entry["state"] == tk.NORMAL:
            self._control_guard = True
            self.spacing_entry.delete(0, tk.END)
            self.spacing_entry.insert(0, f"{spacing:.3f}")
            self._control_guard = False
        self._update_preview(self.current_element)

    def on_spacing_entry_change(self, _event=None):
        if self._control_guard or not self.current_element:
            return
        entry = self.element_entries.get(self.current_element)
        if not entry or not entry.get("has_spacing") or self.spacing_entry["state"] == tk.DISABLED:
            return
        raw = self.spacing_entry.get().strip()
        if not raw:
            return
        try:
            spacing = float(raw)
        except ValueError:
            return
        spacing = max(0.0, min(0.5, spacing))
        entry["spacing"] = spacing
        self._control_guard = True
        self.spacing_scale.set(spacing)
        self.spacing_value_label.config(text=f"{spacing:.3f}")
        self.spacing_entry.delete(0, tk.END)
        self.spacing_entry.insert(0, f"{spacing:.3f}")
        self._control_guard = False
        self._update_preview(self.current_element)

    def on_text_entry_change(self, _event=None):
        if self._control_guard or not self.current_element:
            return
        entry = self.element_entries.get(self.current_element)
        if not entry or self.text_entry["state"] == tk.DISABLED:
            return
        entry["text"] = self.text_entry.get()
        self._update_preview(self.current_element)

    def on_font_entry_change(self, _event=None):
        if self._control_guard or not self.current_element:
            return
        entry = self.element_entries.get(self.current_element)
        if not entry or self.font_entry["state"] == tk.DISABLED:
            return
        path = self.font_entry.get().strip()
        entry["font_path"] = path or None
        self._update_preview(self.current_element)

    def on_number_entry_change(self, _event=None):
        if self._control_guard or not self.current_element:
            return
        entry = self.element_entries.get(self.current_element)
        if not entry or not entry.get("is_number") or self.number_entry["state"] == tk.DISABLED:
            return
        path = self.number_entry.get().strip()
        entry["number_folder"] = path or None
        self._update_preview(self.current_element)

    def on_browse_font(self):
        if not self.current_element:
            return
        path = filedialog.askopenfilename(
            title="Select font file",
            filetypes=[("Font Files", "*.otf;*.ttf"), ("All Files", "*.*")]
        )
        if not path:
            return
        self._control_guard = True
        self.font_entry.config(state=tk.NORMAL)
        self.font_entry.delete(0, tk.END)
        self.font_entry.insert(0, path)
        self._control_guard = False
        entry = self.element_entries.get(self.current_element)
        if entry:
            entry["font_path"] = path
            self._update_preview(self.current_element)

    def on_browse_number_folder(self):
        if not self.current_element:
            return
        path = filedialog.askdirectory(
            title="Select number sprite folder"
        )
        if not path:
            return
        self._control_guard = True
        self.number_entry.config(state=tk.NORMAL)
        self.number_entry.delete(0, tk.END)
        self.number_entry.insert(0, path)
        self._control_guard = False
        entry = self.element_entries.get(self.current_element)
        if entry:
            entry["number_folder"] = path
            self._update_preview(self.current_element)

    def _resolve_font_path(self, font_path, base_dir_override=None):
        if not font_path:
            return None
        font_path = font_path.strip()
        if not font_path:
            return None
        if os.path.isabs(font_path) and os.path.isfile(font_path):
            return font_path
        search_roots = []
        if base_dir_override:
            search_roots.append(base_dir_override)
        if self.template_path:
            search_roots.append(os.path.dirname(self.template_path))
        search_roots.append(self.base_dir)
        for root in search_roots:
            candidate = os.path.join(root, font_path)
            if os.path.isfile(candidate):
                return candidate
        if os.path.isfile(font_path):
            return os.path.abspath(font_path)
        return None

    def _clear_preview(self, name):
        entry = self.element_entries.get(name)
        if not entry:
            return
        if entry.get("preview_id"):
            self.canvas.delete(entry["preview_id"])
            entry["preview_id"] = None
            entry["preview_photo"] = None

    def _hide_element_visuals(self, name):
        entry = self.element_entries.get(name)
        if not entry:
            return
        if entry.get("rect_id"):
            self.canvas.delete(entry["rect_id"])
            entry["rect_id"] = None
        for hid in entry.get("handle_ids", []):
            self.canvas.delete(hid)
        entry["handle_ids"] = []
        self._clear_preview(name)

    def _update_preview(self, name):
        entry = self.element_entries.get(name)
        if not entry:
            return
        self._clear_preview(name)
        if not entry.get("active", True):
            return
        coords = entry.get("coords")
        if not coords or self.photo_image is None:
            return

        if entry.get("is_number"):
            number_str = (entry.get("text") or "").strip() or "12"
            folder = entry.get("number_folder")
            if not folder or not os.path.isdir(folder):
                return
            rotation = entry.get("rotation", 0.0) if entry.get("has_rotation") else 0.0
            preview_img = self._render_number_preview(number_str, folder, coords, rotation)
            if preview_img is None:
                return
            x0, y0, x1, y1 = coords
            box_width = int(round(x1 - x0))
            box_height = int(round(y1 - y0))
            if rotation != 0:
                paste_x = int(round(x0 + (box_width - preview_img.size[0]) / 2))
                paste_y = int(round(y0 + (box_height - preview_img.size[1]) / 2))
            else:
                paste_x = int(round(x0))
                paste_y = int(round(y0))
            preview_photo = ImageTk.PhotoImage(preview_img)
            entry["preview_photo"] = preview_photo
            entry["preview_id"] = self.canvas.create_image(paste_x, paste_y, anchor=tk.NW, image=preview_photo)
            if entry["rect_id"]:
                self.canvas.tag_lower(entry["preview_id"], entry["rect_id"])
            for hid in entry["handle_ids"]:
                self.canvas.tag_raise(hid)
            return

        text = (entry.get("text") or "").strip()
        if not text:
            return
        resolved_font = self._resolve_font_path(entry.get("font_path"))
        if not resolved_font:
            return
        meta = entry.get("meta") or {}
        nameplate_obj = dict(meta) if isinstance(meta, dict) else {}
        nameplate_obj["coords"] = coords
        rotation = entry.get("rotation", 0.0) if entry.get("has_rotation") else nameplate_obj.get("rotation", 0.0)
        nameplate_obj["rotation"] = rotation
        if entry.get("has_spacing"):
            nameplate_obj["spacing_factor"] = entry.get("spacing", nameplate_obj.get("spacing_factor", 0.06))
        preview_img = self._render_nameplate_preview(text, resolved_font, nameplate_obj)
        if preview_img is None:
            return
        x0, y0, x1, y1 = coords
        box_width = int(round(x1 - x0))
        paste_x = int(round(x0 + (box_width - preview_img.size[0]) / 2))
        paste_y = int(round(y0))
        preview_photo = ImageTk.PhotoImage(preview_img)
        entry["preview_photo"] = preview_photo
        entry["preview_id"] = self.canvas.create_image(paste_x, paste_y, anchor=tk.NW, image=preview_photo)
        if entry["rect_id"]:
            self.canvas.tag_lower(entry["preview_id"], entry["rect_id"])
        for hid in entry["handle_ids"]:
            self.canvas.tag_raise(hid)

    def _render_nameplate_preview(self, text, font_path, nameplate_obj):
        coords = nameplate_obj["coords"]
        color = nameplate_obj.get("color", "#FFFFFF")
        spacing_factor = nameplate_obj.get("spacing_factor", 0.06)
        word_spacing_factor = nameplate_obj.get("word_spacing_factor", 0.33)
        vertical_align = (nameplate_obj.get("vertical_align") or "top").lower()
        rotation_angle = nameplate_obj.get("rotation", 0.0) or 0.0
        y_offset_extra = nameplate_obj.get("y_offset_extra", 0)
        x0, y0, x1, y1 = coords
        box_width = max(1, int(round(x1 - x0)))
        box_height = max(1, int(round(y1 - y0)))

        font, metrics = self._fit_text_to_box(
            text, font_path, box_width, box_height, spacing_factor, word_spacing_factor
        )
        if not font or not metrics:
            return None

        total_width, text_height, bbox, spacing, char_advances, word_spacing = metrics
        img = Image.new("RGBA", (box_width, box_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        fill_color = self._hex_to_rgba(color)

        x_cursor = (box_width - total_width) // 2
        if vertical_align == "center":
            y_offset = (box_height - text_height) // 2 - bbox[1] + y_offset_extra
        elif vertical_align == "bottom":
            y_offset = box_height - text_height - bbox[1] + y_offset_extra
        else:
            y_offset = -bbox[1] + y_offset_extra

        for i, char in enumerate(text):
            if char == " ":
                x_cursor += word_spacing
                continue
            draw.text((x_cursor, y_offset), char, font=font, fill=fill_color)
            x_cursor += char_advances[i]
            if i < len(text) - 1 and text[i + 1] != " ":
                x_cursor += spacing

        if rotation_angle:
            img = img.rotate(rotation_angle, expand=True, resample=Image.BICUBIC, fillcolor=(0, 0, 0, 0))
            bbox_img = img.getbbox()
            if bbox_img:
                img = img.crop(bbox_img)
        else:
            bbox_img = img.getbbox()
            if bbox_img:
                img = img.crop(bbox_img)
        return img

    def _fit_text_to_box(self, text, font_path, box_width, box_height, spacing_factor, word_spacing_factor):
        if not text:
            return (None, None)
        min_font_size = 10
        max_font_size = 400
        best = None
        margin = int(box_height * 0.08)

        def _advance(font_obj, s):
            if hasattr(font_obj, "getlength"):
                return font_obj.getlength(s)
            bbox = font_obj.getbbox(s)
            return bbox[2] - bbox[0]

        while min_font_size <= max_font_size:
            mid = (min_font_size + max_font_size) // 2
            try:
                font = self._get_font(font_path, mid)
            except OSError:
                return (None, None)
            spacing = int(mid * spacing_factor)
            word_spacing = int(mid * word_spacing_factor)
            char_advances = []
            for ch in text:
                if ch == " ":
                    char_advances.append(0)
                else:
                    char_advances.append(_advance(font, ch))
            total_width = 0
            for i, ch in enumerate(text):
                if ch == " ":
                    total_width += word_spacing
                else:
                    total_width += char_advances[i]
                    if i < len(text) - 1 and text[i + 1] != " ":
                        total_width += spacing
            bbox = font.getbbox(text)
            text_height = bbox[3] - bbox[1]
            if total_width <= box_width and text_height <= (box_height - margin):
                best = (font, total_width, text_height, bbox, spacing, char_advances, word_spacing)
                min_font_size = mid + 1
            else:
                max_font_size = mid - 1

        if not best:
            return (None, None)
        font, total_width, text_height, bbox, spacing, char_advances, word_spacing = best
        metrics = (total_width, text_height, bbox, spacing, char_advances, word_spacing)
        return font, metrics

    def _hex_to_rgba(self, hex_color):
        hex_color = str(hex_color).lstrip('#')
        lv = len(hex_color)
        if lv == 6:
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4)) + (255,)
        if lv == 8:
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4, 6))
        raise ValueError("Invalid hex color")

    def _get_font(self, font_path, size):
        key = (font_path, size)
        if key in self.font_cache:
            return self.font_cache[key]
        font = ImageFont.truetype(font_path, size)
        self.font_cache[key] = font
        return font

    def on_include_toggle(self):
        if not self.current_element:
            return
        entry = self.element_entries.get(self.current_element)
        if not entry:
            return
        entry["active"] = self.include_var.get()
        if entry["active"]:
            if entry.get("coords"):
                self._draw_element(self.current_element, entry["coords"])
        else:
            self._hide_element_visuals(self.current_element)
        self._highlight_element(self.current_element)
        self._refresh_listbox_labels()

    def save_coords(self):
        if not self.coords_data:
            messagebox.showwarning("No Template", "Load a coords.json template before saving.")
            return

        output_data = copy.deepcopy(self.coords_data)
        missing = []

        for name in self.listbox_order:
            entry = self.element_entries[name]
            coords = entry["coords"]
            active = entry.get("active", True)
            if coords is None:
                if active:
                    missing.append(name)
                continue
            rounded = [int(round(v)) for v in coords]
            target = output_data.get(name)
            if isinstance(target, dict) and "coords" in target:
                target["coords"] = rounded
                if entry.get("has_rotation"):
                    rotation_val = float(entry.get("rotation", target.get("rotation", 0) or 0))
                    target["rotation"] = rotation_val
                if entry.get("has_spacing"):
                    spacing_val = float(entry.get("spacing", target.get("spacing_factor", 0.06) or 0.06))
                    target["spacing_factor"] = spacing_val
                if entry.get("is_number") and entry.get("number_folder"):
                    target["number_folder"] = entry["number_folder"]
            elif isinstance(target, list) and len(target) == 4:
                if entry.get("has_rotation"):
                    output_data[name] = {
                        "coords": rounded,
                        "rotation": float(entry.get("rotation", 0.0))
                    }
                    if entry.get("is_number") and entry.get("number_folder"):
                        output_data[name]["number_folder"] = entry["number_folder"]
                else:
                    output_data[name] = rounded
            else:
                if entry.get("has_rotation"):
                    output_data[name] = {
                        "coords": rounded,
                        "rotation": float(entry.get("rotation", 0.0))
                    }
                    if entry.get("has_spacing"):
                        output_data[name]["spacing_factor"] = float(entry.get("spacing", 0.06))
                    if entry.get("is_number") and entry.get("number_folder"):
                        output_data[name]["number_folder"] = entry["number_folder"]
                else:
                    output_data[name] = rounded

        save_dir = os.path.dirname(self.template_path) if self.template_path else self.base_dir
        out_path = os.path.join(save_dir, "temp-coords.json")
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2)
        except Exception as exc:
            messagebox.showerror("Save Error", f"Failed to save file:\n{exc}")
            return

        if missing:
            messagebox.showwarning(
                "Saved with gaps",
                f"Saved to {out_path}, but the following elements are missing coordinates:\n"
                + "\n".join(missing)
            )
        else:
            messagebox.showinfo("Saved", f"Coordinates saved to {out_path}")

    def _render_number_preview(self, number_str, number_folder, coords, rotation_angle):
        composed = self._compose_number_image(number_str, number_folder, coords)
        if composed is None:
            return None
        if rotation_angle:
            composed = composed.rotate(
                rotation_angle,
                expand=True,
                resample=Image.BICUBIC,
                fillcolor=(0, 0, 0, 0)
            )
            bbox_img = composed.getbbox()
            if bbox_img:
                composed = composed.crop(bbox_img)
        return composed

    def _compose_number_image(self, number_str, number_folder, coords):
        digits = list(str(number_str).strip())
        if not digits:
            return None
        try:
            digit_imgs = [
                Image.open(os.path.join(number_folder, f"{d}.png")).convert("RGBA")
                for d in digits
            ]
        except (FileNotFoundError, OSError):
            return None

        widths, heights = zip(*(img.size for img in digit_imgs))
        x0, y0, x1, y1 = coords
        box_width = max(1, int(round(x1 - x0)))
        box_height = max(1, int(round(y1 - y0)))

        if len(digits) == 1 and digits[0] == "1":
            orig = digit_imgs[0]
            scale = box_height / heights[0] * 0.9
            new_size = (int(widths[0] * scale), int(heights[0] * scale))
            scaled = orig.resize(new_size, Image.LANCZOS)
            final = Image.new("RGBA", (box_width, box_height), (0, 0, 0, 0))
            offset = ((box_width - new_size[0]) // 2, (box_height - new_size[1]) // 2)
            final.paste(scaled, offset, scaled)
            return final

        if len(digits) == 1:
            composite_width = widths[0] * 2
            composite_height = heights[0]
            composite = Image.new("RGBA", (composite_width, composite_height), (0, 0, 0, 0))
            offset_x = (composite_width - widths[0]) // 2
            composite.paste(digit_imgs[0], (offset_x, 0), digit_imgs[0])
            scale = box_height / composite_height
            scaled = composite.resize((int(composite_width * scale), box_height), Image.LANCZOS)
            final = Image.new("RGBA", (box_width, box_height), (0, 0, 0, 0))
            final.paste(scaled, ((box_width - scaled.size[0]) // 2, 0), scaled)
            return final

        if len(digits) == 2 and digits[0] == "1" and digits[1] == "1":
            gap = int(widths[0] * 0.2)
            composite_width = widths[0] + widths[1] + gap
            composite_height = max(heights)
            composite = Image.new("RGBA", (composite_width, composite_height), (0, 0, 0, 0))
            composite.paste(digit_imgs[0], (0, (composite_height - heights[0]) // 2), digit_imgs[0])
            composite.paste(
                digit_imgs[1],
                (widths[0] + gap, (composite_height - heights[1]) // 2),
                digit_imgs[1]
            )
            scale = box_height / composite_height
            scaled = composite.resize((int(composite_width * scale), box_height), Image.LANCZOS)
            final = Image.new("RGBA", (box_width, box_height), (0, 0, 0, 0))
            final.paste(scaled, ((box_width - scaled.size[0]) // 2, 0), scaled)
            return final

        if len(digits) == 2 and ("1" in digits):
            scaled = []
            base_widths = []
            for img in digit_imgs:
                s = box_height / float(img.size[1])
                w = max(1, int(round(img.size[0] * s)))
                base_widths.append(w)
                scaled.append(img.resize((w, box_height), Image.LANCZOS))
            base_total = sum(base_widths)
            final = Image.new("RGBA", (box_width, box_height), (0, 0, 0, 0))
            if base_total <= box_width:
                idx_non1 = 0 if digits[0] != "1" else 1
                non1_w = base_widths[idx_non1]
                max_increase = int(round(non1_w * 0.1))
                extra_needed = box_width - base_total
                increase = max(0, min(extra_needed, max_increase))
                if increase > 0:
                    new_w = non1_w + increase
                    scaled[idx_non1] = scaled[idx_non1].resize((new_w, box_height), Image.LANCZOS)
                    base_widths[idx_non1] = new_w
                comp_w = sum(base_widths)
                composite = Image.new("RGBA", (comp_w, box_height), (0, 0, 0, 0))
                x = 0
                for img in scaled:
                    composite.paste(img, (x, 0), img)
                    x += img.size[0]
                final.paste(composite, ((box_width - comp_w) // 2, 0), composite)
                return final
            composite = Image.new("RGBA", (base_total, box_height), (0, 0, 0, 0))
            x = 0
            for img in scaled:
                composite.paste(img, (x, 0), img)
                x += img.size[0]
            return composite.resize((box_width, box_height), Image.LANCZOS)

        composite_width = sum(widths)
        composite_height = max(heights)
        composite = Image.new("RGBA", (composite_width, composite_height), (0, 0, 0, 0))
        x = 0
        for img in digit_imgs:
            y = (composite_height - img.size[1]) // 2
            composite.paste(img, (x, y), img)
            x += img.size[0]
        return composite.resize((box_width, box_height), Image.LANCZOS)

    def _default_number_folder(self, name):
        if not self.team_folder:
            return None
        if name == "FrontNumber":
            folder = os.path.join(self.team_folder, "number_front")
        elif name == "BackNumber":
            folder = os.path.join(self.team_folder, "number_back")
        else:
            folder = os.path.join(self.team_folder, "number_shoulder")
        return folder if os.path.isdir(folder) else None

    def _set_side(self, side):
        if side not in ("front", "back"):
            return
        if not self.blank_images:
            messagebox.showwarning("No Team Folder", "Load a team folder first.")
            return
        self.side = side
        self._display_current_blank()
        self._apply_side_activation()
        self._refresh_listbox_labels()
        if self.current_element:
            entry = self.element_entries.get(self.current_element)
            if entry:
                self._control_guard = True
                self.include_var.set(entry.get("active", True))
                self._control_guard = False
                self._highlight_element(self.current_element)

    def _display_current_blank(self):
        img = self.blank_images.get(self.side)
        if img is None:
            return
        width, height = img.size
        self.canvas.config(width=width, height=height, scrollregion=(0, 0, width, height))
        photo = ImageTk.PhotoImage(img)
        self.photo_image = photo
        if self.image_id is None:
            self.canvas.delete("all")
            self.image_id = self.canvas.create_image(0, 0, anchor=tk.NW, image=photo)
            for name, entry in self.element_entries.items():
                entry["rect_id"] = None
                entry["handle_ids"] = []
                entry["preview_id"] = None
                entry["preview_photo"] = None
                if entry.get("coords") and entry.get("active", True):
                    self._draw_element(name, entry["coords"])
        else:
            self.canvas.itemconfigure(self.image_id, image=photo)

    def _apply_side_activation(self):
        front_active = {"FrontNumber", "FLShoulder", "FRShoulder"}
        back_active = {"BackNumber", "BLShoulder", "BRShoulder", "NamePlate"}
        required = front_active if self.side == "front" else back_active
        for name, entry in self.element_entries.items():
            should_active = name in required
            entry["active"] = should_active
            if should_active:
                if entry.get("coords"):
                    self._draw_element(name, entry["coords"])
            else:
                self._hide_element_visuals(name)
        if self.current_element:
            entry = self.element_entries.get(self.current_element)
            if entry:
                self._control_guard = True
                self.include_var.set(entry.get("active", True))
                self._control_guard = False
                self._highlight_element(self.current_element)

def main():
    root = tk.Tk()
    app = CoordsBuilderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
