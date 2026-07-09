import io
from PIL import Image

from geometry_components import generate


def main():
    topology = """
    Vertex A:(3*cos(5*pi/18)-4,3*sin(5*pi/18))
    Vertex B:(3*cos(5*pi/18),3*sin(5*pi/18))
    Vertex C:(3*cos(5*pi/18)+4,3*sin(5*pi/18))
    Vertex D:(0,0)
    Vertex E:(5*cos(pi/9),-5*sin(pi/9))
    Vertex F:(5*cos(pi/9)-3,-5*sin(pi/9))
    Vertex G:(5*cos(pi/9)+3,-5*sin(pi/9))

    Segment A-B
    Segment B-C
    Segment B-D
    Segment D-E
    Segment F-E
    Segment E-G

    angles CBD=130 BDE=70 DEG=160
    """

    # Call your in-memory generator
    png_bytes = generate(topology, dpi=300, pretty=True)

    # Sanity check
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n"), "Not a PNG!"

    # Display the image
    img = Image.open(io.BytesIO(png_bytes))
    img.show()  # opens system image viewer


if __name__ == "__main__":
    main()

