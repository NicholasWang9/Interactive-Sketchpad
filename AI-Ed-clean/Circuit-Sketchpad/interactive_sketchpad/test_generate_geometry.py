import io
from PIL import Image

from geometry_components import generate


def main():
    topology = """
    Vertex A:(sqrt(3),0) right
    Vertex B:(sqrt(3)/2,3/2) above right
    Vertex C:(-sqrt(3)/2,3/2) above left
    Vertex D:(-sqrt(3),0) left
    Vertex E:(-sqrt(3)/2,-3/2) below left
    Vertex F:(sqrt(3)/2,-3/2) below right
    Segment A-B
    Segment B-C
    Segment C-D
    Segment D-E
    Segment E-F
    Segment F-A

    Vertex A:(sqrt(3)/2,0) right
    Vertex B:(sqrt(3)/2,1) above right
    Vertex C:(-sqrt(3)/2,1) above left
    Vertex D:(-sqrt(3),0) left
    Vertex E:(-sqrt(3)/2,-1) below left
    Vertex F:(sqrt(3)/2,-1) below right
    Segment A-B
    Segment B-C
    Segment C-D
    Segment D-E
    Segment E-F
    Segment F-A
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

