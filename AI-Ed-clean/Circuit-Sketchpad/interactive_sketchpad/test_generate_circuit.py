import io
from PIL import Image

from circuit_generation import generate


def main():
    topology = "(R//(R+(R//R)))"

    # Call your in-memory generator
    png_bytes = generate(topology, dpi=300, pretty=True)

    # Sanity check
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n"), "Not a PNG!"

    # Display the image
    img = Image.open(io.BytesIO(png_bytes))
    img.show()  # opens system image viewer


if __name__ == "__main__":
    main()


# thingy = """
# Vertex A:(0,0)
# Vertex B:(1,0)
# Vertex C:(1,1)
# Vertex D:(0,1)

# Segment A-B
# Segment B-C
# Segment C-D
# Segment D-A

# Circle E Center A Radius 0.5
# """
# generate(thingy, dpi = 300, pretty = True)