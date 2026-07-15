import io
from PIL import Image

from geometry_components import generate


def main():
    topology = """
    Vertex A:(-1,1) above left
    Vertex B:(1,1) above right
    Vertex C:(-sqrt(2),0) below left
    Vertex D:(sqrt(2),0) below right
    Vertex O:(0,0) below
    Vertex P:(0,1) above

    Segment A-B
    Segment O-C
    Segment O-D
    Segment O-A
    Segment O-B

    Angle AOB=80

    Circle O center O radius sqrt(2)

    Arc APB

    Shade APB BA
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

