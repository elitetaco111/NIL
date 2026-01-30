import json
import os
import re
import traceback
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

try:
	import tkinter as tk
	from tkinter import filedialog
except Exception:
	tk = None
	filedialog = None

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "jerseystocreate.csv")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
LOCAL_BIN_DIR = os.path.join(BASE_DIR, "bin")
ROOT_BIN_DIR = os.path.abspath(os.path.join(BASE_DIR, os.pardir, "bin"))
COMBINED_CANVAS_SIZE = (700, 1000)
FRONT_SUFFIX = 3
BACK_SUFFIX = 2
COMBINED_SUFFIX = 1
COMBINED_SCALE = 0.8
NAMEPLATE_SUPERSAMPLE = 2


@dataclass
class JerseyOrder:
	"""Represents a single row/request from the CSV."""

	name: str
	jersey_style_number: str
	team: str
	color_list: str
	jersey_characters: str
	player_name: str
	garment_group: str
	sport_specific: str
	jersey_name_text: str
	jersey_number: str

	@property
	def is_youth(self) -> bool:
		return (self.garment_group or "").strip().lower() == "youth"

	@property
	def file_stub(self) -> str:
		raw_value = self.name or f"{self.team}-{self.jersey_number}".strip()
		sanitized = sanitize_filename_component(raw_value)
		return sanitized or "jersey"


def sanitize_filename_component(value: str) -> str:
	value = (value or "").strip()
	clean = re.sub(r"[^A-Za-z0-9_-]+", "_", value)
	return clean.strip("_")


def parse_name_and_number(jersey_characters: str) -> Tuple[str, str]:
	if not jersey_characters or not str(jersey_characters).strip():
		raise ValueError("Missing Jersey Characters value")

	data = str(jersey_characters).strip()
	match = re.search(r"(\d+)\s*$", data)
	if not match:
		raise ValueError(f"Unable to find player number in '{data}'")

	number = match.group(1)
	name = data[: match.start()].strip(" -,_")
	if not name:
		raise ValueError(f"Unable to parse player name from '{data}'")

	return name, number


def build_order(row: Dict[str, str]) -> JerseyOrder:
	required_columns = [
		"Name",
		"Team",
		"Color List",
		"Jersey Characters",
		"Sport Specific",
	]
	for col in required_columns:
		if pd.isna(row.get(col)) or not str(row.get(col)).strip():
			raise ValueError(f"Missing required column '{col}'")

	jersey_name_text, jersey_number = parse_name_and_number(row.get("Jersey Characters", ""))
	if not jersey_number.isdigit():
		raise ValueError(f"Parsed jersey number '{jersey_number}' is not numeric")

	return JerseyOrder(
		name=str(row.get("Name", "")).strip(),
		jersey_style_number=str(row.get("Jersey Style Number", "")).strip(),
		team=str(row.get("Team", "")).strip(),
		color_list=str(row.get("Color List", "")).strip(),
		jersey_characters=str(row.get("Jersey Characters", "")).strip(),
		player_name=str(row.get("Player Name", "")).strip(),
		garment_group=str(row.get("Mens or Youth", "")).strip(),
		sport_specific=str(row.get("Sport Specific", "")).strip(),
		jersey_name_text=jersey_name_text,
		jersey_number=jersey_number,
	)


def normalized(value: str) -> str:
	return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def candidate_folder_names(team: str, color_list: str) -> List[str]:
	team = (team or "").strip()
	color_list = (color_list or "").strip()
	combos = []
	if team and color_list:
		combos.extend(
			[
				f"{team}-{color_list}",
				f"{team} - {color_list}",
				f"{team} {color_list}",
				f"{team}_{color_list}",
			]
		)
	if team:
		combos.append(team)
	if color_list:
		combos.append(color_list)
	# Remove duplicates while preserving order
	seen = set()
	ordered: List[str] = []
	for combo in combos:
		norm = normalized(combo)
		if combo and norm not in seen:
			seen.add(norm)
			ordered.append(combo)
	return ordered


def get_bin_directories() -> List[str]:
	bins = []
	if os.path.isdir(LOCAL_BIN_DIR):
		bins.append(LOCAL_BIN_DIR)
	if os.path.isdir(ROOT_BIN_DIR) and ROOT_BIN_DIR not in bins:
		bins.append(ROOT_BIN_DIR)
	return bins


def prompt_csv_via_dialog(initial_dir: Optional[str] = None) -> Optional[str]:
	if filedialog is None or tk is None:
		print("GUI file picker unavailable; pass a CSV path on the command line instead.")
		return None

	root = tk.Tk()
	root.withdraw()
	root.attributes('-topmost', True)

	try:
		selected = filedialog.askopenfilename(
			title="Select jersey CSV",
			initialdir=initial_dir or BASE_DIR,
			filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
		)
	finally:
		root.destroy()

	return selected or None


def locate_team_folder(order: JerseyOrder) -> str:
	norm_targets = {normalized(name) for name in candidate_folder_names(order.team, order.color_list)}
	if not norm_targets:
		raise FileNotFoundError("No valid team/color combination provided")

	for bin_dir in get_bin_directories():
		sport_dir = os.path.join(bin_dir, order.sport_specific)
		if not os.path.isdir(sport_dir):
			continue
		for entry in os.listdir(sport_dir):
			full_path = os.path.join(sport_dir, entry)
			if not os.path.isdir(full_path):
				continue
			entry_norm = normalized(entry)
			if entry_norm in norm_targets:
				return full_path
			# Allow partial matches so long as both strings share prefix
			if any(entry_norm.startswith(t) or t.startswith(entry_norm) for t in norm_targets):
				return full_path

	raise FileNotFoundError(
		f"Unable to find asset folder for sport '{order.sport_specific}' with team '{order.team}' and colors '{order.color_list}'"
	)


def load_coords_json(team_folder: str) -> Dict:
	coords_path = os.path.join(team_folder, "coords.json")
	with open(coords_path, "r", encoding="utf-8") as handle:
		return json.load(handle)


def load_youth_overlay() -> Optional[Image.Image]:
	for bin_dir in get_bin_directories():
		path = os.path.join(bin_dir, "youth.png")
		if os.path.exists(path):
			try:
				return Image.open(path).convert("RGBA")
			except Exception as exc:
				print(f"⚠️  Unable to load youth overlay from {path}: {exc}")
	return None


def add_number_stroke_border(img, border_color, border_width):
	"""Add a stroke border to number images using multiple draws"""
	padding = border_width + 2
	new_width = img.size[0] + (padding * 2)
	new_height = img.size[1] + (padding * 2)

	result = Image.new("RGBA", (new_width, new_height), (0, 0, 0, 0))
	border_img = Image.new("RGBA", img.size, (0, 0, 0, 0))

	if img.mode == "RGBA":
		alpha = img.split()[3]
		border_rgb = border_color[:3] if len(border_color) >= 3 else border_color
		border_img = Image.new("RGBA", img.size, border_rgb + (255,))
		border_img.putalpha(alpha)

	center_x, center_y = padding, padding
	offsets = [
		(-border_width, -border_width),
		(-border_width, 0),
		(-border_width, border_width),
		(0, -border_width),
		(0, border_width),
		(border_width, -border_width),
		(border_width, 0),
		(border_width, border_width),
	]

	for dx, dy in offsets:
		result.paste(border_img, (center_x + dx, center_y + dy), border_img)

	result.paste(img, (center_x, center_y), img)
	return result


def apply_text_border(draw, text, position, font, text_color, border_config):
	if not border_config or border_config.get("width", 0) <= 0:
		return

	border_type = border_config.get("type", "solid")
	border_color = hex_to_rgba(border_config.get("color", "#000000"))
	border_width = int(round(border_config["width"]))
	x, y = position

	if border_type == "solid":
		for dx in range(-border_width, border_width + 1):
			for dy in range(-border_width, border_width + 1):
				if dx != 0 or dy != 0:
					draw.text((x + dx, y + dy), text, font=font, fill=border_color)
	elif border_type in {"shadow", "3d"}:
		shadow_offset = border_width
		shadow_color = border_color
		for i in range(1, shadow_offset + 1):
			distance_factor = (shadow_offset - i + 1) / shadow_offset
			base_opacity = 0.8
			opacity = int(255 * base_opacity * distance_factor)
			opacity = max(80, min(200, opacity))
			shadow_with_opacity = shadow_color[:3] + (opacity,)
			draw.text((x + i, y + i), text, font=font, fill=shadow_with_opacity)
		if border_width >= 2:
			outline_opacity = 150
			outline_color = shadow_color[:3] + (outline_opacity,)
			for dx, dy in [
				(-1, -1),
				(-1, 0),
				(-1, 1),
				(0, -1),
				(0, 1),
				(1, -1),
				(1, 0),
				(1, 1),
			]:
				draw.text((x + dx, y + dy), text, font=font, fill=outline_color)


def add_image_border_with_type(img, border_color, border_width, border_type="solid"):
	if border_width <= 0:
		return img

	if border_type == "solid":
		old_width, old_height = img.size
		new_width = old_width + (border_width * 2)
		new_height = old_height + (border_width * 2)
		result = Image.new("RGBA", (new_width, new_height), (0, 0, 0, 0))

		if img.mode == "RGBA":
			alpha = img.split()[3]
			border_layer = Image.new("RGBA", img.size, border_color[:3] + (255,))
			border_layer.putalpha(alpha)
			center_x, center_y = border_width, border_width
			for dx in range(-border_width, border_width + 1):
				for dy in range(-border_width, border_width + 1):
					if dx != 0 or dy != 0:
						distance = max(abs(dx), abs(dy))
						if distance <= border_width:
							result.paste(border_layer, (center_x + dx, center_y + dy), border_layer)
		result.paste(img, (border_width, border_width), img)
		return result

	if border_type in {"shadow", "3d"}:
		shadow_offset = border_width
		old_width, old_height = img.size
		new_width = old_width + shadow_offset + 1
		new_height = old_height + shadow_offset + 1
		result = Image.new("RGBA", (new_width, new_height), (0, 0, 0, 0))

		if img.mode == "RGBA":
			alpha = img.split()[3]
			for i in range(1, shadow_offset + 1):
				distance_factor = (shadow_offset - i + 1) / shadow_offset
				base_opacity = 0.5
				opacity = int(255 * base_opacity * distance_factor)
				opacity = max(40, min(120, opacity))
				shadow_layer = Image.new("RGBA", img.size, border_color[:3] + (opacity,))
				shadow_layer.putalpha(alpha)
				result.paste(shadow_layer, (i, i), shadow_layer)

		result.paste(img, (0, 0), img)
		return result

	return add_image_border_with_type(img, border_color, border_width, "solid")


def composite_numbers(number_str, number_folder, target_box, border_settings=None):
	digits = list(str(number_str))
	digit_imgs = [Image.open(os.path.join(number_folder, f"{d}.png")).convert("RGBA") for d in digits]
	widths, heights = zip(*(img.size for img in digit_imgs))

	if len(digits) == 1:
		composite_width = widths[0] * 2
		composite_height = heights[0]
		composite = Image.new("RGBA", (composite_width, composite_height), (0, 0, 0, 0))
		offset_x = (composite_width - widths[0]) // 2
		composite.paste(digit_imgs[0], (offset_x, 0), digit_imgs[0])
	elif len(digits) == 2 and digits[0] == "1" and digits[1] == "1":
		overlap = int(widths[0] * 0.15)
		composite_width = widths[0] + widths[1] - overlap
		composite_height = max(heights)
		composite = Image.new("RGBA", (composite_width, composite_height), (0, 0, 0, 0))
		composite.paste(digit_imgs[0], (0, (composite_height - heights[0]) // 2), digit_imgs[0])
		composite.paste(
			digit_imgs[1],
			(widths[0] - overlap, (composite_height - heights[1]) // 2),
			digit_imgs[1],
		)
	else:
		composite_width = sum(widths)
		composite_height = max(heights)
		composite = Image.new("RGBA", (composite_width, composite_height), (0, 0, 0, 0))
		x = 0
		for img in digit_imgs:
			y = (composite_height - img.size[1]) // 2
			composite.paste(img, (x, y), img)
			x += img.size[0]

	x0, y0, x1, y1 = target_box
	box_width = int(round(x1 - x0))
	box_height = int(round(y1 - y0))
	stretched = composite.resize((box_width, box_height), Image.LANCZOS)

	def apply_single_border(img, border_cfg):
		if border_cfg and border_cfg.get("width", 0) > 0:
			final_size = min(box_width, box_height)
			border_width_factor = border_cfg.get("width", 10)
			proportional_border_width = max(1, int(final_size * border_width_factor / 200))
			border_color = hex_to_rgba(border_cfg.get("color", "#000000"))
			border_type = border_cfg.get("type", "solid")
			img = add_image_border_with_type(img, border_color, proportional_border_width, border_type)
		return img

	if isinstance(border_settings, list):
		for border_cfg in border_settings:
			stretched = apply_single_border(stretched, border_cfg)
	else:
		stretched = apply_single_border(stretched, border_settings)

	return stretched


def fit_text_to_box(text, font_path, box_width, box_height, spacing_factor, max_font_size=400, min_font_size=10):
	best_font = None
	best_size = None
	margin = int(box_height * 0.08)

	while min_font_size <= max_font_size:
		mid = (min_font_size + max_font_size) // 2
		font = ImageFont.truetype(font_path, mid)
		char_widths = [font.getbbox(char)[2] - font.getbbox(char)[0] for char in text]
		spacing = int(mid * spacing_factor)
		total_width = sum(char_widths) + spacing * (len(text) - 1)
		bbox = font.getbbox(text)
		h = bbox[3] - bbox[1]
		if total_width <= box_width and h <= (box_height - margin):
			best_font = font
			best_size = (total_width, h, bbox, spacing, char_widths)
			min_font_size = mid + 1
		else:
			max_font_size = mid - 1
	return best_font, best_size


def render_straight_text(draw, text, font, char_widths, spacing, box_width, box_height, fill_color, border_config):
	total_width = sum(char_widths) + spacing * (len(text) - 1)
	x_cursor = (box_width - total_width) // 2
	bbox = font.getbbox(text)
	h = bbox[3] - bbox[1]
	y_offset = (box_height - h) // 2 - bbox[1]

	for i, char in enumerate(text):
		if border_config:
			apply_text_border(draw, char, (x_cursor, y_offset), font, fill_color, border_config)
		draw.text((x_cursor, y_offset), char, font=font, fill=fill_color)
		x_cursor += char_widths[i] + spacing


def render_arc_text(draw, text, font, char_widths, spacing, box_width, box_height, fill_color, border_config, curve_config):
	import math as _math

	radius = curve_config.get("radius", 100)
	angle_degrees = curve_config.get("angle", 60)
	direction = curve_config.get("direction", "up")
	angle_radians = _math.radians(angle_degrees)
	total_width = sum(char_widths) + spacing * (len(text) - 1)
	arc_length = total_width * 1.2
	total_char_angle = arc_length / radius
	start_angle = -total_char_angle / 2

	char_angles = []
	for i, _char in enumerate(text):
		if i == 0:
			char_angle = start_angle
		else:
			prev_width = sum(char_widths[:i]) + spacing * i
			char_angle = start_angle + (prev_width / total_width) * total_char_angle
		char_angles.append(char_angle)

	center_x = box_width // 2
	if direction == "up":
		center_y = box_height // 2 + radius // 2
	else:
		center_y = box_height // 2 - radius // 2

	for i, char in enumerate(text):
		char_angle = char_angles[i]
		x = center_x + radius * _math.sin(char_angle)
		y = center_y - radius * _math.cos(char_angle)
		char_pos = (int(x - char_widths[i] // 2), int(y))
		if border_config:
			apply_text_border(draw, char, char_pos, font, fill_color, border_config)
		draw.text(char_pos, char, font=font, fill=fill_color)


def render_circular_text(draw, text, font, char_widths, spacing, box_width, box_height, fill_color, border_config, curve_config):
	import math as _math

	radius = curve_config.get("radius", 30)
	start_angle = curve_config.get("start_angle", 0)
	total_width = sum(char_widths) + spacing * (len(text) - 1)
	circumference_portion = total_width / (2 * _math.pi * radius)
	total_angle = circumference_portion * 360
	if total_angle > 300:
		radius = total_width / (2 * _math.pi * (300 / 360))
		total_angle = 300

	center_x = box_width // 2
	center_y = box_height // 2
	current_angle = start_angle - (total_angle / 2)

	for i, char in enumerate(text):
		char_width = char_widths[i]
		angle_rad = _math.radians(current_angle)
		char_x = center_x + radius * _math.cos(angle_rad)
		char_y = center_y + radius * _math.sin(angle_rad)
		char_rotation = current_angle + 90
		char_image = Image.new("RGBA", (char_width + 20, font.size + 20), (0, 0, 0, 0))
		char_draw = ImageDraw.Draw(char_image)
		if border_config and border_config.get("width", 0) > 0:
			border_color = tuple(border_config.get("color", [0, 0, 0]))
			border_width = border_config.get("width", 1)
			text_color = fill_color[:3] if len(fill_color) > 3 else fill_color
			border_color = border_color[:3] if len(border_color) > 3 else border_color
			add_simple_text_border(char_draw, char, (10, 10), font, text_color, border_color, border_width)
		else:
			text_color = fill_color[:3] if len(fill_color) > 3 else fill_color
			char_draw.text((10, 10), char, font=font, fill=text_color)
		rotated_char = char_image.rotate(-char_rotation, expand=True)
		paste_x = int(char_x - rotated_char.width // 2)
		paste_y = int(char_y - rotated_char.height // 2)
		draw._image.paste(rotated_char, (paste_x, paste_y), rotated_char)
		char_angle = (char_width + spacing) / (2 * _math.pi * radius) * 360
		current_angle += char_angle


def render_wave_text(draw, text, font, char_widths, spacing, box_width, box_height, fill_color, border_config, curve_config):
	import math as _math

	amplitude = curve_config.get("amplitude", 10)
	frequency = curve_config.get("frequency", 2)
	total_width = sum(char_widths) + spacing * (len(text) - 1)
	start_x = (box_width - total_width) // 2
	x_cursor = start_x

	for i, char in enumerate(text):
		char_center_x = x_cursor + char_widths[i] / 2
		normalized_x = (char_center_x - start_x) / total_width if total_width > 0 else 0
		wave_y = amplitude * _math.sin(2 * _math.pi * frequency * normalized_x)
		bbox = font.getbbox(text)
		h = bbox[3] - bbox[1]
		base_y = (box_height - h) // 2 - bbox[1]
		y_position = base_y + wave_y
		char_pos = (int(x_cursor), int(y_position))
		if border_config:
			apply_text_border(draw, char, char_pos, font, fill_color, border_config)
		draw.text(char_pos, char, font=font, fill=fill_color)
		x_cursor += char_widths[i] + spacing


def render_fan_text(draw, text, font, char_widths, spacing, box_width, box_height, fill_color, border_config, curve_config):
	import math as _math

	total_angle = curve_config.get("angle", 60)
	radius = curve_config.get("radius", 80)
	center_x = box_width // 2
	center_y = min(box_height - 5, box_height * 0.85)
	angle_step = total_angle / (len(text) - 1) if len(text) > 1 else 0
	start_angle = -total_angle / 2

	for i, char in enumerate(text):
		char_width = char_widths[i]
		current_angle = start_angle + (i * angle_step)
		angle_rad = _math.radians(current_angle)
		char_x = center_x + radius * _math.sin(angle_rad)
		char_y = center_y - radius * _math.cos(angle_rad)
		padding = 40
		char_image = Image.new("RGBA", (char_width + padding * 2, font.size + padding * 2), (0, 0, 0, 0))
		char_draw = ImageDraw.Draw(char_image)
		if border_config and border_config.get("width", 0) > 0:
			border_color_raw = border_config.get("color", [0, 0, 0])
			if isinstance(border_color_raw, str):
				border_color = hex_to_rgba(border_color_raw)[:3]
			else:
				border_color = tuple(border_color_raw)[:3]
			border_width = border_config.get("width", 1)
			text_color = fill_color[:3] if len(fill_color) > 3 else fill_color
			add_simple_text_border(char_draw, char, (padding, padding), font, text_color, border_color, border_width)
		else:
			text_color = fill_color[:3] if len(fill_color) > 3 else fill_color
			char_draw.text((padding, padding), char, font=font, fill=text_color)
		rotated_char = char_image.rotate(-current_angle, expand=True)
		paste_x = int(round(char_x - rotated_char.width // 2))
		paste_y = int(round(char_y - rotated_char.height // 2))
		draw._image.paste(rotated_char, (paste_x, paste_y), rotated_char)


def apply_curve_to_text(draw, text, font, char_widths, spacing, box_width, box_height, fill_color, border_config, curve_config):
	curve_type = curve_config.get("type", "none")
	if curve_type in {"none", "straight"}:
		return render_straight_text(draw, text, font, char_widths, spacing, box_width, box_height, fill_color, border_config)
	if curve_type == "arc" or curve_type == "arc_down":
		return render_arc_text(draw, text, font, char_widths, spacing, box_width, box_height, fill_color, border_config, curve_config)
	if curve_type == "circle":
		return render_circular_text(draw, text, font, char_widths, spacing, box_width, box_height, fill_color, border_config, curve_config)
	if curve_type == "wave":
		return render_wave_text(draw, text, font, char_widths, spacing, box_width, box_height, fill_color, border_config, curve_config)
	if curve_type == "fan":
		return render_fan_text(draw, text, font, char_widths, spacing, box_width, box_height, fill_color, border_config, curve_config)
	default_curve_config = {"angle": 70, "radius": 120}
	return render_fan_text(draw, text, font, char_widths, spacing, box_width, box_height, fill_color, border_config, default_curve_config)


def add_simple_text_border(draw, text, position, font, text_color, border_color, border_width):
	x, y = position
	border_width = int(round(border_width))
	for dx in range(-border_width, border_width + 1):
		for dy in range(-border_width, border_width + 1):
			if dx != 0 or dy != 0:
				draw.text((x + dx, y + dy), text, font=font, fill=border_color)
	draw.text(position, text, font=font, fill=text_color)


def hex_to_rgba(hex_color):
	hex_color = hex_color.lstrip("#")
	lv = len(hex_color)
	if lv == 6:
		return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4)) + (255,)
	if lv == 8:
		return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4, 6))
	raise ValueError("Invalid hex color")


def render_nameplate(text, font_path, nameplate_obj, rotation_angle=0, y_offset_extra=0):
	coords = nameplate_obj["coords"]
	color = nameplate_obj.get("color", "#FFFFFF")
	border_config = None
	if "border_color" in nameplate_obj and nameplate_obj.get("border_width", 0) > 0:
		border_config = {
			"color": nameplate_obj["border_color"],
			"width": nameplate_obj["border_width"],
			"type": nameplate_obj.get("border_type", "solid"),
		}
	elif "border" in nameplate_obj:
		border_config = nameplate_obj["border"]

	spacing_factor = nameplate_obj.get("spacing_factor", 0.06)
	x0, y0, x1, y1 = coords
	box_width = int(round(x1 - x0))
	box_height = int(round(y1 - y0))
	curve_config = nameplate_obj.get("curve", {"type": "none"}).copy()
	curve_type = curve_config.get("type", "none")
	render_scale = max(1, NAMEPLATE_SUPERSAMPLE)
	if render_scale != 1:
		for key in ("radius", "height", "amplitude"):
			value = curve_config.get(key)
			if isinstance(value, (int, float)):
				curve_config[key] = value * render_scale

	canvas_height = box_height
	canvas_width = box_width
	if curve_type in ["arc", "arc_down"]:
		curve_height = curve_config.get("height", 15)
		padding = int(30 * render_scale)
		extra_height = abs(curve_height) * 3 + padding
		canvas_height = box_height + extra_height
	elif curve_type == "circle":
		radius = curve_config.get("radius", 30)
		padding = int(50 * render_scale)
		extra_space = radius * 2 + padding
		canvas_height = box_height + extra_space
		canvas_width = box_width + extra_space
	elif curve_type == "fan":
		radius = curve_config.get("radius", 40)
		padding = int(150 * render_scale)
		extra_space = radius * 3 + padding
		canvas_height = box_height + extra_space
		canvas_width = box_width + extra_space
	elif curve_type == "wave":
		curve_height = curve_config.get("height", 15)
		padding = int(30 * render_scale)
		extra_height = abs(curve_height) * 3 + padding
		canvas_height = box_height + extra_height

	canvas_width = int(round(canvas_width))
	canvas_height = int(round(canvas_height))
	render_canvas_width = int(round(canvas_width * render_scale))
	render_canvas_height = int(round(canvas_height * render_scale))
	scaled_box_width = max(1, int(round(box_width * render_scale)))
	scaled_box_height = max(1, int(round(box_height * render_scale)))

	font, (total_width, h, bbox, spacing, char_widths) = fit_text_to_box(
		text,
		font_path,
		scaled_box_width,
		scaled_box_height,
		spacing_factor,
	)
	img = Image.new("RGBA", (render_canvas_width, render_canvas_height), (0, 0, 0, 0))
	draw = ImageDraw.Draw(img)
	fill_color = hex_to_rgba(color)
	apply_curve_to_text(
		draw,
		text,
		font,
		char_widths,
		spacing,
		render_canvas_width,
		render_canvas_height,
		fill_color,
		border_config,
		curve_config,
	)

	if curve_type == "fan":
		bbox = img.getbbox()
		if bbox:
			padding = int(20 * render_scale)
			crop_left = max(0, bbox[0] - padding)
			crop_top = max(0, bbox[1] - padding)
			crop_right = min(render_canvas_width, bbox[2] + padding)
			crop_bottom = min(render_canvas_height, bbox[3] + padding)
			img = img.crop((crop_left, crop_top, crop_right, crop_bottom))

	if render_scale > 1:
		target_width = max(1, int(round(img.width / render_scale)))
		target_height = max(1, int(round(img.height / render_scale)))
		img = img.resize((target_width, target_height), Image.LANCZOS)

	if "rotation" in nameplate_obj:
		rotation_angle = nameplate_obj["rotation"]
	if rotation_angle != 0:
		img = img.rotate(rotation_angle, expand=True, resample=Image.BICUBIC)
	return img


def add_shoulder_number(base_img, number_str, number_folder, shoulder_obj, border_settings=None):
	if not shoulder_obj or "coords" not in shoulder_obj:
		return

	coords = shoulder_obj["coords"]
	rotation = shoulder_obj.get("rotation", 0)
	x0, y0, x1, y1 = [int(round(c)) for c in coords]
	box_width = int(round(x1 - x0))
	box_height = int(round(y1 - y0))

	digits = list(str(number_str))
	digit_imgs = [Image.open(os.path.join(number_folder, f"{d}.png")).convert("RGBA") for d in digits]
	widths, heights = zip(*(img.size for img in digit_imgs))

	if len(digits) == 1:
		composite_width = widths[0] * 2
		composite_height = heights[0]
		composite = Image.new("RGBA", (composite_width, composite_height), (0, 0, 0, 0))
		offset_x = (composite_width - widths[0]) // 2
		composite.paste(digit_imgs[0], (offset_x, 0), digit_imgs[0])
	else:
		composite_width = sum(widths)
		composite_height = max(heights)
		composite = Image.new("RGBA", (composite_width, composite_height), (0, 0, 0, 0))
		x = 0
		for img in digit_imgs:
			y = (composite_height - img.size[1]) // 2
			composite.paste(img, (x, y), img)
			x += img.size[0]

	scale = box_height / composite_height
	shoulder_squish = 0.65
	new_width = int(composite_width * scale * shoulder_squish)
	new_height = box_height
	scaled = composite.resize((new_width, new_height), Image.LANCZOS)

	if border_settings and border_settings.get("width", 0) > 0:
		final_size = min(new_width, new_height)
		border_width_factor = border_settings.get("width", 5)
		proportional_border_width = max(1, int(final_size * border_width_factor / 200))
		border_color = hex_to_rgba(border_settings.get("color", "#000000"))
		border_type = border_settings.get("type", "solid")
		scaled = add_image_border_with_type(scaled, border_color, proportional_border_width, border_type)

	final = Image.new("RGBA", (box_width, box_height), (0, 0, 0, 0))
	offset_x = (box_width - scaled.size[0]) // 2
	final.paste(scaled, (offset_x, 0), scaled)
	rotated_number = final.rotate(rotation, expand=True, resample=Image.BICUBIC)
	base_img.paste(rotated_number, (x0, y0), rotated_number)


def apply_youth_overlay(image: Image.Image, overlay: Optional[Image.Image]) -> Image.Image:
	if overlay is None:
		return image
	if image.size != overlay.size:
		overlay_resized = overlay.resize(image.size, Image.LANCZOS)
	else:
		overlay_resized = overlay
	result = image.copy()
	result.paste(overlay_resized, (0, 0), overlay_resized)
	return result


def create_front_image(order: JerseyOrder, team_folder: str, coords: Dict) -> Image.Image:
	blanks_folder = os.path.join(team_folder, "blanks")
	number_folder = os.path.join(team_folder, "number_front")
	blank_front_path = os.path.join(blanks_folder, "front.png")
	if not os.path.exists(blank_front_path):
		raise FileNotFoundError(f"Missing front blank image: {blank_front_path}")
	blank_img = Image.open(blank_front_path).convert("RGBA")
	temp = blank_img.copy()

	if "FrontNumber" in coords:
		front_number_border = coords.get("FrontNumberBorder") or coords.get("NumberBorder")
		number_img = composite_numbers(order.jersey_number, number_folder, coords["FrontNumber"], front_number_border)
		x0, y0, *_ = [int(round(c)) for c in coords["FrontNumber"]]
		temp.paste(number_img, (x0, y0), number_img)

	add_shoulder_number(temp, order.jersey_number, number_folder, coords.get("FLShoulder"), coords.get("FrontShoulderBorder"))
	add_shoulder_number(temp, order.jersey_number, number_folder, coords.get("FRShoulder"), coords.get("FrontShoulderBorder"))

	alpha = blank_img.split()[-1]
	temp.putalpha(alpha)
	return temp


def create_back_image(order: JerseyOrder, team_folder: str, coords: Dict) -> Image.Image:
	blanks_folder = os.path.join(team_folder, "blanks")
	number_folder = os.path.join(team_folder, "number_back")
	fonts_folder = os.path.join(team_folder, "fonts")
	font_path = os.path.join(fonts_folder, "NamePlate.otf")
	blank_back_path = os.path.join(blanks_folder, "back.png")
	if not os.path.exists(blank_back_path):
		raise FileNotFoundError(f"Missing back blank image: {blank_back_path}")
	if not os.path.exists(font_path):
		raise FileNotFoundError(f"Missing nameplate font: {font_path}")

	blank_img = Image.open(blank_back_path).convert("RGBA")
	temp = blank_img.copy()

	nameplate_config = coords.get("NamePlate")
	if not nameplate_config:
		raise KeyError("NamePlate configuration missing from coords")

	rotation_angle = nameplate_config.get("rotation", 0)
	nameplate_coords = nameplate_config["coords"].copy()
	if len(order.jersey_name_text) >= 9:
		nameplate_coords = [
			nameplate_coords[0],
			nameplate_coords[1] + 20,
			nameplate_coords[2],
			nameplate_coords[3] + 20,
		]

	nameplate_obj = dict(nameplate_config)
	nameplate_obj["coords"] = nameplate_coords
	nameplate_img = render_nameplate(order.jersey_name_text.upper(), font_path, nameplate_obj, rotation_angle, 0)
	x0, y0, x1, y1 = [int(round(c)) for c in nameplate_coords]
	box_width = int(round(x1 - x0))
	box_height = int(round(y1 - y0))

	if rotation_angle != 0:
		np_w, np_h = nameplate_img.size
		paste_x = x0 + (box_width - np_w) // 2
		paste_y = y0 + (box_height - np_h) // 2
	else:
		paste_x, paste_y = x0, y0
	temp.paste(nameplate_img, (paste_x, paste_y), nameplate_img)

	back_number_border = coords.get("BackNumberBorder") or coords.get("NumberBorder")
	back_number_box = coords.get("BackNumber")
	if back_number_box:
		number_img = composite_numbers(order.jersey_number, number_folder, back_number_box, back_number_border)
		bx0, by0, *_ = [int(round(c)) for c in back_number_box]
		temp.paste(number_img, (bx0, by0), number_img)

	add_shoulder_number(temp, order.jersey_number, number_folder, coords.get("BLShoulder"), coords.get("BackShoulderBorder"))
	add_shoulder_number(temp, order.jersey_number, number_folder, coords.get("BRShoulder"), coords.get("BackShoulderBorder"))

	alpha = blank_img.split()[-1]
	temp.putalpha(alpha)
	return temp


def scale_image(img: Image.Image, factor: float) -> Image.Image:
	factor = max(0.01, factor)
	new_width = max(1, int(img.width * factor))
	new_height = max(1, int(img.height * factor))
	return img.resize((new_width, new_height), Image.LANCZOS)


def create_combined_image(front_img: Image.Image, back_img: Image.Image) -> Image.Image:
	canvas_width, canvas_height = COMBINED_CANVAS_SIZE
	margin = 30
	overlap_ratio = 0.35

	front_scaled = scale_image(front_img, COMBINED_SCALE)
	back_scaled = scale_image(back_img, COMBINED_SCALE)

	overlap_width = int(min(front_scaled.width, back_scaled.width) * overlap_ratio)
	required_width = front_scaled.width + back_scaled.width - overlap_width
	required_height = max(front_scaled.height, back_scaled.height)

	width_ratio = (canvas_width - margin * 2) / required_width if required_width else 1
	height_ratio = (canvas_height - margin * 2) / required_height if required_height else 1
	additional_scale = min(1.0, width_ratio, height_ratio)

	if additional_scale < 1.0:
		front_scaled = scale_image(front_scaled, additional_scale)
		back_scaled = scale_image(back_scaled, additional_scale)
		overlap_width = int(min(front_scaled.width, back_scaled.width) * overlap_ratio)

	combined = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))

	back_x = margin
	back_y = margin + (canvas_height - margin * 2 - back_scaled.height) // 2
	combined.paste(back_scaled, (back_x, back_y), back_scaled)

	front_x = back_x + back_scaled.width - overlap_width
	front_y = margin + (canvas_height - margin * 2 - front_scaled.height) // 2 - 10
	combined.paste(front_scaled, (front_x, max(margin, front_y)), front_scaled)

	return combined


def save_image(image: Image.Image, filename: str) -> str:
	os.makedirs(OUTPUT_DIR, exist_ok=True)
	path = os.path.join(OUTPUT_DIR, filename)
	image.save(path)
	return path


def process_order(order: JerseyOrder, youth_overlay: Optional[Image.Image]):
	try:
		team_folder = locate_team_folder(order)
	except FileNotFoundError as exc:
		print(f"✗ {order.name}: {exc}")
		return

	try:
		coords = load_coords_json(team_folder)
	except Exception as exc:
		print(f"✗ {order.name}: Unable to load coords.json - {exc}")
		return

	try:
		front_img = create_front_image(order, team_folder, coords)
		back_img = create_back_image(order, team_folder, coords)
	except Exception as exc:
		print(f"✗ {order.name}: Error generating jerseys - {exc}")
		traceback.print_exc()
		return

	front_output = apply_youth_overlay(front_img, youth_overlay) if order.is_youth else front_img
	back_output = apply_youth_overlay(back_img, youth_overlay) if order.is_youth else back_img

	front_filename = f"{order.file_stub}-{FRONT_SUFFIX}.png"
	back_filename = f"{order.file_stub}-{BACK_SUFFIX}.png"
	save_image(front_output, front_filename)
	save_image(back_output, back_filename)

	combined_img = create_combined_image(front_img, back_img)
	if order.is_youth:
		combined_img = apply_youth_overlay(combined_img, youth_overlay)
	combined_filename = f"{order.file_stub}-{COMBINED_SUFFIX}.png"
	save_image(combined_img, combined_filename)

	print(f"✓ {order.name}: generated {combined_filename}, {back_filename}, {front_filename}")


def read_csv(csv_path: str) -> pd.DataFrame:
	df = pd.read_csv(csv_path, encoding="utf-8")
	df = df.dropna(how="all")
	return df


def main(csv_path: Optional[str] = None):
	if csv_path:
		target_csv = csv_path
	else:
		target_csv = prompt_csv_via_dialog(BASE_DIR)
		if not target_csv:
			print("No CSV selected; exiting.")
			return

	if not os.path.exists(target_csv):
		raise FileNotFoundError(f"CSV file not found: {target_csv}")

	os.makedirs(OUTPUT_DIR, exist_ok=True)
	df = read_csv(target_csv)
	youth_overlay = load_youth_overlay()

	print(f"Processing {len(df)} rows from {target_csv} ...")
	for idx, row in df.iterrows():
		try:
			order = build_order(row)
		except ValueError as exc:
			print(f"Skipping row {idx}: {exc}")
			continue
		process_order(order, youth_overlay)

	print("Jersey generation complete!")


if __name__ == "__main__":
	import sys

	main(sys.argv[1] if len(sys.argv) > 1 else None)
