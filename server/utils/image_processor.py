import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont


def add_text_overlay(
    image_path: str,
    text: str,
    output_path: str,
    position: str = "bottom",
    text_color: tuple = (255, 255, 255),
    bg_color: tuple = (0, 0, 0, 128),
    font_path: str = None,
) -> str:
    img = Image.open(image_path).convert("RGBA")

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_size = max(16, img.width // 25)
    if font_path and os.path.exists(font_path):
        font = ImageFont.truetype(font_path, font_size)
    else:
        try:
            font = ImageFont.truetype("simhei.ttf", font_size)
        except OSError:
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except OSError:
                font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    padding = 10

    if position == "bottom":
        x = (img.width - text_width) // 2
        y = img.height - text_height - padding * 3
    elif position == "top":
        x = (img.width - text_width) // 2
        y = padding
    else:
        x = (img.width - text_width) // 2
        y = (img.height - text_height) // 2

    bg_x0 = x - padding
    bg_y0 = y - padding
    bg_x1 = x + text_width + padding
    bg_y1 = y + text_height + padding
    draw.rectangle([bg_x0, bg_y0, bg_x1, bg_y1], fill=bg_color)

    draw.text((x, y), text, fill=text_color, font=font)

    result = Image.alpha_composite(img, overlay)
    result = result.convert("RGB")
    result.save(output_path, "JPEG", quality=90)

    return output_path


def build_timestamp_text(custom_text: str = "") -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if custom_text:
        return f"{custom_text}  |  {now}"
    return now
