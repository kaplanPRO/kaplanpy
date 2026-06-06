import pytest
from pathlib import Path
from kaplan.parser.json import JSONParser
import lxml.etree as etree


@pytest.fixture
def nsmap():
    return {
        "kaplan": "https://kaplan.pro",
        "xliff": "urn:oasis:names:tc:xliff:document:2.1",
    }


def test_json_parser_parse(nsmap):
    parser = JSONParser(nsmap)
    test_file = Path("tests/data/test.json")

    if not test_file.exists():
        pytest.skip("Test file tests/data/test.json not found.")

    internal_file, tus = parser.parse(test_file)

    assert internal_file is None
    assert isinstance(tus, list)
    assert len(tus) == 2

    for tu in tus:
        assert isinstance(tu, etree._Element)
        assert tu.tag == f"{{{nsmap['xliff']}}}unit"
        assert "id" in tu.attrib
        assert f"{{{nsmap['kaplan']}}}key" in tu.attrib
