from pathlib import Path

from .kxliff import KXLIFF
from .sdlxliff import SDLXLIFF
from .xliff import XLIFF

from enum import Enum


class BilingualFileHandlerEnum(Enum):
    KXLIFF = "kxliff"
    SDLXLIFF = "sdlxliff"
    XLIFF = "xliff"


bilingual_file_map = {
    BilingualFileHandlerEnum.KXLIFF: KXLIFF,
    BilingualFileHandlerEnum.SDLXLIFF: SDLXLIFF,
    BilingualFileHandlerEnum.XLIFF: XLIFF,
}


def open_bilingual_file(bilingual_file: str | Path) -> KXLIFF | SDLXLIFF | XLIFF:
    """
    Opens a compatible xliff variant.

    Args:
        bilingual_file: Path to a .kxliff, .xliff, or .sdlxliff file.
    """

    bilingual_file = Path(bilingual_file)

    if not bilingual_file.exists():
        raise FileNotFoundError(f"{bilingual_file} does not exist.")

    bilingual_file_handler = BilingualFileHandlerEnum(bilingual_file.suffix.lstrip("."))

    return bilingual_file_map[bilingual_file_handler].open_bilingual_file(
        bilingual_file
    )
