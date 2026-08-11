import io
from PIL import Image

from geometry_components import generate


def main():
    topology = """
    Vertex A:(0,0) left
    Vertex B:(6,0) right
    Vertex C:(3,3*sqrt(3)) above
    Vertex D:(3,-3*sqrt(3)) below
    Circle A Center A Radius 6
    Circle B Center B Radius 6
    Segment A-C
    Segment B-C
    Arc DAC
    Arc DBC
    Shade DAC CBD
    Shade DBC CAD
    """

    # Call your in-memory generator
    png_bytes = generate(topology, dpi=300, pretty=True)

    # Sanity check
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n"), "Not a PNG!"

    # Display the image with white background
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")

    white_bg = Image.new("RGBA", img.size, "WHITE")
    white_bg.paste(img, (0, 0), img)

    white_bg.convert("RGB").show() # opens system image viewer


if __name__ == "__main__":
    main()

