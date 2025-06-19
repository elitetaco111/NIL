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
    total_width = sum(widths)
    max_height = max(heights)
    x0, y0, x1, y1 = target_box
    box_width = x1 - x0
    box_height = y1 - y0
    scale = min(box_width / total_width, box_height / max_height)
    scaled_imgs = [img.resize((int(w*scale), int(h*scale)), Image.LANCZOS) for img, w, h in zip(digit_imgs, widths, heights)]
    new_width = sum(img.size[0] for img in scaled_imgs)
    new_height = max(img.size[1] for img in scaled_imgs)
    composite = Image.new("RGBA", (new_width, new_height), (0,0,0,0))
    x = 0
    for img in scaled_imgs:
        composite.paste(img, (x, (new_height - img.size[1]) // 2), img)
        x += img.size[0]
    final = Image.new("RGBA", (int(box_width), int(box_height)), (0,0,0,0))
    offset_x = (box_width - new_width) // 2
    offset_y = (box_height - new_height) // 2
    final.paste(composite, (int(offset_x), int(offset_y)), composite)
    return final

def fit_text_to_box(text, font_path, box_width, box_height, max_font_size=200, min_font_size=10):
    # Binary search for best font size
    font_size = max_font_size
    best_font = None
    best_size = None
    while min_font_size <= max_font_size:
        mid = (min_font_size + max_font_size) // 2
        font = ImageFont.truetype(font_path, mid)
        bbox = font.getbbox(text)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if w <= box_width and h <= box_height:
            best_font = font
            best_size = (w, h)
            min_font_size = mid + 1
        else:
            max_font_size = mid - 1
    return best_font, best_size

def render_nameplate(text, font_path, target_box):
    x0, y0, x1, y1 = target_box
    box_width = int(x1 - x0)
    box_height = int(y1 - y0)
    font, (w, h) = fit_text_to_box(text, font_path, box_width, box_height)
    img = Image.new("RGBA", (box_width, box_height), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    # Center text
    draw.text(((box_width - w)//2, (box_height - h)//2), text, font=font, fill=(255,255,255,255))
    return img

def process_front(row, team_folder, coords):
    player_name = row["Preferred Name"]
    player_number = str(row["Player Number"])
    blanks_folder = os.path.join(team_folder, "blanks")
    number_folder = os.path.join(team_folder, "number_front")
    blank_front_path = os.path.join(blanks_folder, "front.png")
    blank_img = Image.open(blank_front_path).convert("RGBA")
    number_img = composite_numbers(player_number, number_folder, coords["FrontNumber"])
    x0, y0, _, _ = [int(round(c)) for c in coords["FrontNumber"]]
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
    nameplate_img = render_nameplate(player_name.upper(), font_path, coords["NamePlate"])
    x0, y0, _, _ = [int(round(c)) for c in coords["NamePlate"]]
    temp = blank_img.copy()
    temp.paste(nameplate_img, (x0, y0), nameplate_img)
    # Back number
    number_img = composite_numbers(player_number, number_folder, coords["BackNumber"])
    x0, y0, _, _ = [int(round(c)) for c in coords["BackNumber"]]
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