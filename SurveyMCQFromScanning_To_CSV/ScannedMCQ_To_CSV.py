"""
OMR scan for an image size(618x886) MCQ sheet with 10 questions (Q1 has 11 choices, others 5).
Uses tkinter for image loading (no external dependencies).  
Place PNGs in ./scans and template.json next to this script.
Writes results.csv and (when debug enabled) scores_debug.csv.
Q1 supports choices_q1 (11 items); other questions use choices (5 items).
"""

from pathlib import Path
import json, csv, math, sys

try:
    import tkinter as tk
except Exception:
    raise SystemExit("tkinter is required")

# --- Config (toggle debug/calibrate here) ---
IMAGE_FOLDER = Path("scans")
TEMPLATE_JSON = Path("template.json")
OUTPUT_CSV = Path("results.csv")
SCORES_DEBUG_CSV = Path("scores_debug.csv")
DEBUG = True        # print per-question scores and write scores_debug.csv
CALIBRATE = False   # not used in compact version; left for compatibility

# --- Minimal image loader using tkinter.PhotoImage ---
_root = None
def ensure_tk():
    global _root
    if _root is None:
        _root = tk.Tk(); _root.withdraw()

def load_image_getter(path):
    ensure_tk()
    img = tk.PhotoImage(file=str(path))
    w, h = img.width(), img.height()
    def get_pixel(x, y):
        v = img.get(x, y)
        if isinstance(v, tuple):
            return int(v[0]), int(v[1]), int(v[2])
        if isinstance(v, str) and v.startswith("#"):
            return int(v[1:3],16), int(v[3:5],16), int(v[5:7],16)
        parts = str(v).split()
        if len(parts) >= 3:
            return int(parts[0]), int(parts[1]), int(parts[2])
        return 255,255,255
    return w, h, get_pixel

# --- Template helpers ---
def load_template(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def scale_coords(img_w, img_h, template):
    tw, th = template["sheet_size"]
    sx, sy = img_w / tw, img_h / th
    scaled = []
    for q in template["questions"]:
        bubbles = [[int(round(x * sx)), int(round(y * sy))] for x,y in q["bubbles"]]
        scaled.append({"id": q["id"], "bubbles": bubbles})
    r = int(round(template.get("bubble_radius", 6) * ((sx+sy)/2.0)))
    return scaled, r

# --- Pixel -> luminance and circular mask ---
def lum(rgb):
    r,g,b = rgb
    return (0.2126*r + 0.7152*g + 0.0722*b) / 255.0

def circular_mask(pw, ph, cx, cy, r):
    rows = []
    r2 = r*r
    for yy in range(ph):
        dy = yy - cy
        rem = r2 - dy*dy
        if rem < 0: continue
        dx = int(math.sqrt(rem))
        rows.append((yy, max(0, cx-dx), min(pw-1, cx+dx)))
    return rows

def filled_fraction(get_pixel, center, r, img_w, img_h):
    x,y = center
    x0, x1 = max(0, x-r), min(img_w-1, x+r)
    y0, y1 = max(0, y-r), min(img_h-1, y+r)
    pw, ph = x1-x0+1, y1-y0+1
    cx, cy = x-x0, y-y0
    mask = circular_mask(pw, ph, cx, cy, r)
    if not mask: return 0.0
    vals = []
    for yy in range(ph):
        for xx in range(pw):
            px, py = x0+xx, y0+yy
            vals.append(lum(get_pixel(px, py)))
    if not vals: return 0.0
    median = sorted(vals)[len(vals)//2]
    total = dark = 0
    for yy, xs, xe in mask:
        for xx in range(xs, xe+1):
            px, py = x0+xx, y0+yy
            if lum(get_pixel(px, py)) < median:
                dark += 1
            total += 1
    return dark / (total + 1e-9)

# --- Single-file processing ---
def process_file(path, template):
    w,h,get_pixel = load_image_getter(path)
    scaled_questions, r = scale_coords(w,h,template)
    threshold = float(template.get("fill_threshold", 0.12))
    choices = template["choices"]
    choices_q1 = template.get("choices_q1", [])
    result = {"file": path.name}
    debug_rows = []
    for q in scaled_questions:
        scores = [filled_fraction(get_pixel, tuple(c), r, w, h) for c in q["bubbles"]]
        if DEBUG:
            print(q["id"], "coords:", q["bubbles"], "scores:", [f"{s:.3f}" for s in scores])
        debug_rows.append({"file": path.name, "qid": q["id"], "coords": str(q["bubbles"]), "scores": ",".join(f"{s:.3f}" for s in scores)})
        if not scores:
            result[q["id"]] = ""
            continue
        best = max(range(len(scores)), key=lambda i: scores[i])
        result[q["id"]] = ""
        if scores[best] > threshold:
            if q["id"] == "Q1" and choices_q1:
                result[q["id"]] = choices_q1[best] if best < len(choices_q1) else ""
            else:
                result[q["id"]] = choices[best] if best < len(choices) else ""
    return result, debug_rows

# --- Main ---
def main():
    if not TEMPLATE_JSON.exists():
        print("template.json not found"); sys.exit(1)
    template = load_template(TEMPLATE_JSON)
    IMAGE_FOLDER.mkdir(exist_ok=True)
    files = sorted(IMAGE_FOLDER.glob("*.png"))
    if not files:
        print("No PNG files in scans/"); sys.exit(1)

    all_debug = []
    rows = []
    for p in files:
        try:
            row, dbg = process_file(p, template)
            rows.append(row); all_debug.extend(dbg)
            print("Processed", p.name)
        except Exception as e:
            rows.append({"file": p.name, "error": str(e)})
            print("Error", p.name, e)

    qids = [q["id"] for q in template["questions"]]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["file"]+qids)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k,"") for k in ["file"]+qids})
    print("Saved", OUTPUT_CSV)

    if DEBUG and all_debug:
        with open(SCORES_DEBUG_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["file","qid","coords","scores"])
            writer.writeheader()
            for d in all_debug: writer.writerow(d)
        print("Saved", SCORES_DEBUG_CSV)

if __name__ == "__main__":
    main()