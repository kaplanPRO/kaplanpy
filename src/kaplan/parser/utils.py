from enum import Enum

from .docx import DOCXParser

class SourceTypeEnum(Enum):
    DOCX = 'docx'

source_to_parser_map = {
    SourceTypeEnum.DOCX : DOCXParser
}