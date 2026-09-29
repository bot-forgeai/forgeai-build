"""Rendering a CHIP-8 display buffer to something a human (or a test) can inspect."""

ON_CHAR = "█"
OFF_CHAR = " "


def to_ascii(display):
    """Render a 64x32 monochrome display buffer as a block of text, two chars per pixel wide."""
    return "\n".join("".join(ON_CHAR * 2 if pixel else OFF_CHAR * 2 for pixel in row) for row in display)


def to_image(display, scale=4, on_color=(0, 255, 0), off_color=(0, 0, 0)):
    """Render the display buffer as a Pillow Image, scaled up, for real screens (e.g. the Pi's LCD)."""
    from PIL import Image

    height = len(display)
    width = len(display[0]) if height else 0
    img = Image.new("RGB", (width * scale, height * scale), off_color)
    pixels = img.load()
    for y, row in enumerate(display):
        for x, pixel in enumerate(row):
            if not pixel:
                continue
            color = on_color
            for dy in range(scale):
                for dx in range(scale):
                    pixels[x * scale + dx, y * scale + dy] = color
    return img
