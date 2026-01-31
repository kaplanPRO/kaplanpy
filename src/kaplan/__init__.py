from importlib.metadata import version

from .bilingual_file import open_bilingual_file

__version__ = version("kaplan")


__all__ = ["open_bilingual_file", "__version__"]


def can_process(input_file):
    """
    Determines whether kaplan can handle input_file.

    Args:
        input_file: Path to a file.
    """
    if input_file.lower().endswith(
        (
            ".docx",
            ".json",
            ".kxliff",
            ".odp",
            ".ods",
            ".odt",
            ".po",
            ".sdlxliff",
            ".txt",
            ".xliff",
        )
    ):
        return True
    else:
        return False
