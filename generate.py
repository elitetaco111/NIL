import os
import pandas as pd
from PIL import Image

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "jerseystocreate.csv")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

def parse_coords(coord_str):
    return [float(x) for x in coord_str.strip().split(",")]

def load_coords(team_folder):
    coords_path = os.path.join(team_folder, "image_coords.txt")
    coords = {}
    with open(coords_path, "r") as f:
        lines = [line.strip() for line in f if line.strip() and not line.startswith("//")]
    for i in range(0, len(lines), 2):
        key = lines[i]
        coords[key] = parse_coords(lines[i+1])
    return coords

def composite_numbers(number_str, number_folder, target_box):
    digits = list(str(number_str))
    digit_imgs = [Image.open(os.path.join(number_folder, f"{d}.png")).convert("RGBA") for d in digits]
    # Calculate total width and max height
    widths, heights = zip(*(img.size for img in digit_imgs))
    total_width = sum(widths)
    max_height = max(heights)
    # Scale to fit target_box
    x0, y0, x1, y1 = target_box
    box_width = x1 - x0
    box_height = y1 - y0
    scale = min(box_width / total_width, box_height / max_height)
    scaled_imgs = [img.resize((int(w*scale), int(h*scale)), Image.LANCZOS) for img, w, h in zip(digit_imgs, widths, heights)]
    # Composite digits side by side
    new_width = sum(img.size[0] for img in scaled_imgs)
    new_height = max(img.size[1] for img in scaled_imgs)
    composite = Image.new("RGBA", (new_width, new_height), (0,0,0,0))
    x = 0
    for img in scaled_imgs:
        composite.paste(img, (x, (new_height - img.size[1]) // 2), img)
        x += img.size[0]
    # Center in target box
    final = Image.new("RGBA", (int(box_width), int(box_height)), (0,0,0,0))
    offset_x = (box_width - new_width) // 2
    offset_y = (box_height - new_height) // 2
    final.paste(composite, (int(offset_x), int(offset_y)), composite)
    return final

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    df = pd.read_csv(CSV_PATH)
    for idx, row in df.iterrows():
        team = row["Team"]
        player_name = row["Preferred Name"]
        player_number = str(row["Player Number"])
        team_folder = os.path.join(BASE_DIR, team)
        blanks_folder = os.path.join(team_folder, "blanks")
        number_folder = os.path.join(team_folder, "number_front")
        coords = load_coords(team_folder)
        # Load blank front
        blank_front_path = os.path.join(blanks_folder, "front.png")
        blank_img = Image.open(blank_front_path).convert("RGBA")
        # Load and composite numbers
        number_img = composite_numbers(player_number, number_folder, coords["FrontNumber"])
        # Paste number onto blank
        x0, y0, x1, y1 = [int(round(c)) for c in coords["FrontNumber"]]
        temp = blank_img.copy()
        temp.paste(number_img, (x0, y0), number_img)
        # Apply alpha mask from blank
        alpha = blank_img.split()[-1]
        temp.putalpha(alpha)
        # Save output
        out_name = f"{team}_{player_name}_{player_number}_front.png".replace(" ", "_")
        out_path = os.path.join(OUTPUT_DIR, out_name)
        temp.save(out_path)
        print(f"Saved {out_path}")

if __name__ == "__main__":
    main()