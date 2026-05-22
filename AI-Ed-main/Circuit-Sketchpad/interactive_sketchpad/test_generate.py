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