from importlib.metadata import version

from .bilingual_file import open_bilingual_file
from .utils import can_process

__version__ = version("kaplan")


__all__ = ["can_process", "open_bilingual_file", "__version__"]
