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
        # Create a composite image as if there are two digits (side by side)
        composite_width = widths[0] * 2
        composite_height = heights[0]
        composite = Image.new("RGBA", (composite_width, composite_height), (0,0,0,0))
        # Center the single digit in the "two digit" space
        offset_x = (composite_width - widths[0]) // 2
        composite.paste(digit_imgs[0], (offset_x, 0), digit_imgs[0])
    else:
        # Multiple digits: composite side by side
        composite_width = sum(widths)
        composite_height = max(heights)
        composite = Image.new("RGBA", (composite_width, composite_height), (0,0,0,0))
        x = 0
        for img in digit_imgs:
            y = (composite_height - img.size[1]) // 2
            composite.paste(img, (x, y), img)
            x += img.size[0]

    # Now scale the composite image to fit the bounding box
    x0, y0, x1, y1 = target_box
    box_width = int(round(x1 - x0))
    box_height = int(round(y1 - y0))
    scale = min(box_width / composite_width, box_height / composite_height)
    new_width = int(composite_width * scale)
    new_height = int(composite_height * scale)
    scaled = composite.resize((new_width, new_height), Image.LANCZOS)

    # Center the scaled image in the bounding box
    final = Image.new("RGBA", (box_width, box_height), (0,0,0,0))
    offset_x = (box_width - new_width) // 2
    offset_y = (box_height - new_height) // 2
    final.paste(scaled, (offset_x, offset_y), scaled)
    return final

def fit_text_to_box(text, font_path, box_width, box_height, max_font_size=400, min_font_size=10):
    # Binary search for best font size to fill the box, with a little margin for descenders
    best_font = None
    best_size = None
    margin = int(box_height * 0.08)  # 8% margin at the bottom
    while min_font_size <= max_font_size:
        mid = (min_font_size + max_font_size) // 2
        font = ImageFont.truetype(font_path, mid)
        bbox = font.getbbox(text)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if w <= box_width and h <= (box_height - margin):
            best_font = font
            best_size = (w, h, bbox)
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

def render_nameplate(text, font_path, nameplate_obj, rotation_angle=0):
    coords = nameplate_obj["coords"]
    color = nameplate_obj.get("color", "#FFFFFF")
    x0, y0, x1, y1 = coords
    box_width = int(round(x1 - x0))
    box_height = int(round(y1 - y0))
    font, (w, h, bbox) = fit_text_to_box(text, font_path, box_width, box_height)
    img = Image.new("RGBA", (box_width, box_height), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    fill_color = hex_to_rgba(color)

    # Add extra spacing between letters
    spacing = int(font.size * 0.06)  # 12% of font size as spacing
    total_width = -spacing  # start negative to remove last extra space
    char_sizes = []
    for char in text:
        char_bbox = font.getbbox(char)
        char_width = char_bbox[2] - char_bbox[0]
        char_sizes.append(char_width)
        total_width += char_width + spacing

    # Center the text horizontally
    x_cursor = (box_width - total_width) // 2
    y_offset = (box_height - h) // 2 - bbox[1]

    for i, char in enumerate(text):
        draw.text((x_cursor, y_offset), char, font=font, fill=fill_color)
        x_cursor += char_sizes[i] + spacing

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
    nameplate_img = render_nameplate(player_name.upper(), font_path, coords["NamePlate"], rotation_angle)
    # Calculate where to paste the rotated nameplate
    x0, y0, x1, y1 = [int(round(c)) for c in coords["NamePlate"]["coords"]]
    box_width = int(round(x1 - x0))
    box_height = int(round(y1 - y0))
    # If rotated, center the rotated image over the bounding box
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
    # Alpha mask
    alpha = blank_img.split()[-1]
    temp.putalpha(alpha)
    out_name = f"{row['Team']}_{player_name}_{player_number}_back.png".replace(" ", "_")
    out_path = os.path.join(OUTPUT_DIR, out_name)
    temp.save(out_path)
    print(f"Saved {out_path}")

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