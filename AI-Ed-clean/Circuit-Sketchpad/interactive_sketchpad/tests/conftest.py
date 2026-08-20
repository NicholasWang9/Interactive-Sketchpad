import os
import sys

# geometry_components.py and friends import each other with flat names
# (e.g. "import geometry_components_utilities as utilities"), not as a
# package -- so the interactive_sketchpad/ directory itself must be on
# sys.path, regardless of where pytest is invoked from.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
