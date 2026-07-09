import io
from PIL import Image

from geometry_components import generate


def main():
    topology = """
    Vertex A:(-6,0)
    Vertex B:(6,0)
    Vertex C:(0,6)
    Vertex O:(0,0)

    Segment A-B
    Segment A-C
    Segment C-B

    Circle O Center O Radius 6

    Angle ACB=90

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

