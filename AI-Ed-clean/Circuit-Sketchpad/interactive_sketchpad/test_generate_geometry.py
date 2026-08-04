import io
from PIL import Image

from geometry_components import generate


def main():
    topology = """
    Vertex O:(0,0) below
    Vertex A:(-3*sqrt(2),0) left
    Vertex B:(0,3*sqrt(2)) above
    Vertex C:(3*sqrt(2),0) right
    Vertex D:(3*sqrt(2)/2,-3*sqrt(6)/2) below

    Segment A-B
    Segment B-C
    Segment C-D
    Segment D-A

    Angle CBA=90

    Circle O Center O Radius 3*sqrt(2)
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

