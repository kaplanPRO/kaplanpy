from enum import Enum

from .docx import DOCXParser
from .odf import ODFParser
from .po import POParser


class SourceTypeEnum(Enum):
    DOCX = "docx"
    ODT = "odt"
    ODS = "ods"
    ODP = "odp"
    PO = "po"


source_to_parser_map = {
    SourceTypeEnum.DOCX: DOCXParser,
    SourceTypeEnum.ODT: ODFParser,
    SourceTypeEnum.ODS: ODFParser,
    SourceTypeEnum.ODP: ODFParser,
    SourceTypeEnum.PO: POParser,
}
