from enum import Enum

from .docx import DOCXParser
from .json import JSONParser
from .odf import ODFParser
from .po import POParser
from .txt import TXTParser


class SourceTypeEnum(Enum):
    DOCX = "docx"
    ODT = "odt"
    ODS = "ods"
    ODP = "odp"
    PO = "po"
    JSON = "json"
    TXT = "txt"


source_to_parser_map = {
    SourceTypeEnum.DOCX: DOCXParser,
    SourceTypeEnum.ODT: ODFParser,
    SourceTypeEnum.ODS: ODFParser,
    SourceTypeEnum.ODP: ODFParser,
    SourceTypeEnum.PO: POParser,
    SourceTypeEnum.JSON: JSONParser,
    SourceTypeEnum.TXT: TXTParser,
}
