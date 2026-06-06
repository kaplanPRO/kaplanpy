import pytest
from pathlib import Path
from kaplan.parser.docx import DOCXParser
import lxml.etree as etree


@pytest.fixture
def nsmap():
    return {
        "kaplan": "https://kaplan.pro",
        "xliff": "urn:oasis:names:tc:xliff:document:2.1",
        "xml": "http://www.w3.org/XML/1998/namespace",
    }


def test_docx_parser_initialization(nsmap):
    parser = DOCXParser(nsmap)
    assert parser.nsmap == nsmap
    assert parser.tu_template is not None
    assert parser.placeholder_template is not None


def test_docx_parser_parse(nsmap):
    parser = DOCXParser(nsmap)
    test_file = Path("tests/data/readme.docx")

    if not test_file.exists():
        pytest.skip("Test file tests/data/readme.docx not found.")

    internal_file, tus = parser.parse(test_file)

    assert isinstance(internal_file, etree._Element)
    assert isinstance(tus, list)
    assert len(tus) > 0

    for tu in tus:
        assert isinstance(tu, etree._Element)
        assert tu.tag == f"{{{nsmap['xliff']}}}unit"
        assert "id" in tu.attrib

        segment = tu.find("xliff:segment", nsmap)
        assert segment is not None

        source = segment.find("xliff:source", nsmap)
        assert source is not None

        target = segment.find("xliff:target", nsmap)
        assert target is not None
