import os
import pandas as pd
import json
from PIL import Image, ImageDraw, ImageFont

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "jerseystocreate.csv")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

def load_coords_json(team_folder):
    coords_path = os.path.join(team_folder, "coords.json")
    with open(coords_path, "r") as f:
        coords = json.load(f)
    return coords

def composite_numbers(number_str, number_folder, target_box):
    digits = list(str(number_str))
    digit_imgs = [Image.open(os.path.join(number_folder, f"{d}.png")).convert("RGBA") for d in digits]
    widths, heights = zip(*(img.size for img in digit_imgs))

    # For single digit, treat as if it's two digits for scaling, but only render one
    if len(digits) == 1:
        composite_width = widths[0] * 2
        composite_height = heights[0]
        composite = Image.new("RGBA", (composite_width, composite_height), (0,0,0,0))
        offset_x = (composite_width - widths[0]) // 2
        composite.paste(digit_imgs[0], (offset_x, 0), digit_imgs[0])
    elif len(digits) == 2 and digits[0] == '1' and digits[1] == '1':
        # Special overlap for "11"
        overlap = int(widths[0] * 0.15)
        composite_width = widths[0] + widths[1] - overlap
        composite_height = max(heights)
        composite = Image.new("RGBA", (composite_width, composite_height), (0,0,0,0))
        # Paste first "1"
        composite.paste(digit_imgs[0], (0, (composite_height - heights[0]) // 2), digit_imgs[0])
        # Paste second "1" with overlap
        composite.paste(digit_imgs[1], (widths[0] - overlap, (composite_height - heights[1]) // 2), digit_imgs[1])
    else:
        composite_width = sum(widths)
        composite_height = max(heights)
        composite = Image.new("RGBA", (composite_width, composite_height), (0,0,0,0))
        x = 0
        for img in digit_imgs:
            y = (composite_height - img.size[1]) // 2
            composite.paste(img, (x, y), img)
            x += img.size[0]

    # Stretch the composite image to exactly fit the bounding box (ignore aspect ratio)
    x0, y0, x1, y1 = target_box
    box_width = int(round(x1 - x0))
    box_height = int(round(y1 - y0))
    stretched = composite.resize((box_width, box_height), Image.LANCZOS)
    return stretched

def fit_text_to_box(text, font_path, box_width, box_height, max_font_size=400, min_font_size=10):
    # Binary search for best font size to fill the box, with a little margin for descenders
    best_font = None
    best_size = None
    margin = int(box_height * 0.08)  # 8% margin at the bottom
    spacing_factor = 0.06  # Must match the spacing in render_nameplate

    while min_font_size <= max_font_size:
        mid = (min_font_size + max_font_size) // 2
        font = ImageFont.truetype(font_path, mid)
        # Calculate total width with spacing
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

def hex_to_rgba(hex_color):
    hex_color = hex_color.lstrip('#')
    lv = len(hex_color)
    if lv == 6:
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4)) + (255,)
    elif lv == 8:
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4, 6))
    else:
        raise ValueError("Invalid hex color")

def render_nameplate(text, font_path, nameplate_obj, rotation_angle=0, y_offset_extra=0):
    coords = nameplate_obj["coords"]
    color = nameplate_obj.get("color", "#FFFFFF")
    x0, y0, x1, y1 = coords
    box_width = int(round(x1 - x0))
    box_height = int(round(y1 - y0))
    font, (total_width, h, bbox, spacing, char_widths) = fit_text_to_box(
        text, font_path, box_width, box_height
    )
    img = Image.new("RGBA", (box_width, box_height), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    fill_color = hex_to_rgba(color)

    # Center the text horizontally
    x_cursor = (box_width - total_width) // 2
    y_offset = (box_height - h) // 2 - bbox[1] + y_offset_extra

    for i, char in enumerate(text):
        draw.text((x_cursor, y_offset), char, font=font, fill=fill_color)
        x_cursor += char_widths[i] + spacing

    # Rotate the nameplate image if needed
    if "rotation" in nameplate_obj:
        rotation_angle = nameplate_obj["rotation"]
    if rotation_angle != 0:
        img = img.rotate(rotation_angle, expand=True, resample=Image.BICUBIC)
    return img

def process_front(row, team_folder, coords):
    player_name = row["Preferred Name"]
    player_number = str(row["Player Number"])
    blanks_folder = os.path.join(team_folder, "blanks")
    number_folder = os.path.join(team_folder, "number_front")
    blank_front_path = os.path.join(blanks_folder, "front.png")
    blank_img = Image.open(blank_front_path).convert("RGBA")
    number_img = composite_numbers(player_number, number_folder, coords["FrontNumber"])
    x0, y0, x1, y1 = [int(round(c)) for c in coords["FrontNumber"]]
    temp = blank_img.copy()
    temp.paste(number_img, (x0, y0), number_img)
    # Add shoulder numbers
    add_shoulder_number(temp, player_number, number_folder, coords["LShoulder"])
    add_shoulder_number(temp, player_number, number_folder, coords["RShoulder"])
    alpha = blank_img.split()[-1]
    temp.putalpha(alpha)
    out_name = f"{row['Team']}_{player_name}_{player_number}_front.png".replace(" ", "_")
    out_path = os.path.join(OUTPUT_DIR, out_name)
    temp.save(out_path)
    print(f"Saved {out_path}")

def process_back(row, team_folder, coords):
    player_name = row["Preferred Name"]
    player_number = str(row["Player Number"])
    blanks_folder = os.path.join(team_folder, "blanks")
    number_folder = os.path.join(team_folder, "number_back")
    fonts_folder = os.path.join(team_folder, "fonts")
    font_path = os.path.join(fonts_folder, "NamePlate.otf")
    blank_back_path = os.path.join(blanks_folder, "back.png")
    blank_img = Image.open(blank_back_path).convert("RGBA")
    # Nameplate
    rotation_angle = coords["NamePlate"].get("rotation", 0)
    y_offset_extra = 20 if len(player_name) >= 14 else 0

    # Shift the bounding box down by y_offset_extra
    nameplate_coords = coords["NamePlate"]["coords"].copy()
    if y_offset_extra:
        nameplate_coords = [
            nameplate_coords[0],
            nameplate_coords[1] + y_offset_extra,
            nameplate_coords[2],
            nameplate_coords[3] + y_offset_extra
        ]
    # Create a temporary NamePlate object with shifted coords
    nameplate_obj = dict(coords["NamePlate"])
    nameplate_obj["coords"] = nameplate_coords

    nameplate_img = render_nameplate(player_name.upper(), font_path, nameplate_obj, rotation_angle, 0)
    x0, y0, x1, y1 = [int(round(c)) for c in nameplate_coords]
    box_width = int(round(x1 - x0))
    box_height = int(round(y1 - y0))
    if rotation_angle != 0:
        np_w, np_h = nameplate_img.size
        paste_x = x0 + (box_width - np_w) // 2
        paste_y = y0 + (box_height - np_h) // 2
    else:
        paste_x, paste_y = x0, y0
    temp = blank_img.copy()
    temp.paste(nameplate_img, (paste_x, paste_y), nameplate_img)
    # Back number
    number_img = composite_numbers(player_number, number_folder, coords["BackNumber"])
    x0, y0, x1, y1 = [int(round(c)) for c in coords["BackNumber"]]
    temp.paste(number_img, (x0, y0), number_img)
    # Add shoulder numbers
    add_shoulder_number(temp, player_number, number_folder, coords["LShoulder"])
    add_shoulder_number(temp, player_number, number_folder, coords["RShoulder"])
    # Alpha mask
    alpha = blank_img.split()[-1]
    temp.putalpha(alpha)
    out_name = f"{row['Team']}_{player_name}_{player_number}_back.png".replace(" ", "_")
    out_path = os.path.join(OUTPUT_DIR, out_name)
    temp.save(out_path)
    print(f"Saved {out_path}")

def add_shoulder_number(base_img, number_str, number_folder, shoulder_obj):
    coords = shoulder_obj["coords"]
    rotation = shoulder_obj.get("rotation", 0)
    x0, y0, x1, y1 = [int(round(c)) for c in coords]
    box_width = int(round(x1 - x0))
    box_height = int(round(y1 - y0))

    # Prepare digit images
    digits = list(str(number_str))
    digit_imgs = [Image.open(os.path.join(number_folder, f"{d}.png")).convert("RGBA") for d in digits]
    widths, heights = zip(*(img.size for img in digit_imgs))

    # For single digit, treat as if it's two digits for scaling, but only render one
    if len(digits) == 1:
        composite_width = widths[0] * 2
        composite_height = heights[0]
        composite = Image.new("RGBA", (composite_width, composite_height), (0,0,0,0))
        offset_x = (composite_width - widths[0]) // 2
        composite.paste(digit_imgs[0], (offset_x, 0), digit_imgs[0])
    else:
        composite_width = sum(widths)
        composite_height = max(heights)
        composite = Image.new("RGBA", (composite_width, composite_height), (0,0,0,0))
        x = 0
        for img in digit_imgs:
            y = (composite_height - img.size[1]) // 2
            composite.paste(img, (x, y), img)
            x += img.size[0]

    # Scale so the composite fills the bounding box vertically, then squish horizontally
    scale = box_height / composite_height
    shoulder_squish = 0.65  # 65% of the normal width
    new_width = int(composite_width * scale * shoulder_squish)
    new_height = box_height
    scaled = composite.resize((new_width, new_height), Image.LANCZOS)

    # Center horizontally in the bounding box
    final = Image.new("RGBA", (box_width, box_height), (0,0,0,0))
    offset_x = (box_width - new_width) // 2
    final.paste(scaled, (offset_x, 0), scaled)

    # Rotate the number image
    rotated_number = final.rotate(rotation, expand=True, resample=Image.BICUBIC)
    # Paste the rotated number at the top-left of the bounding box
    base_img.paste(rotated_number, (x0, y0), rotated_number)

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    df = pd.read_csv(CSV_PATH)
    for idx, row in df.iterrows():
        team = row["Team"]
        team_folder = os.path.join(BASE_DIR, team)
        coords = load_coords_json(team_folder)
        process_front(row, team_folder, coords)
        process_back(row, team_folder, coords)

if __name__ == "__main__":
    main()