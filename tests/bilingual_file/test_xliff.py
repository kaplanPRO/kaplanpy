import pytest
from pathlib import Path
import lxml.etree as etree
from kaplan.bilingual_file.xliff import XLIFF


@pytest.fixture
def xliff_file():
    return Path("tests/data/deneme.xliff")


def test_xliff_initialization(xliff_file):
    if not xliff_file.exists():
        pytest.skip("Test file tests/data/deneme.xliff not found.")

    xml_root = etree.parse(str(xliff_file)).getroot()
    xliff = XLIFF(xliff_file.name, xml_root)

    assert xliff.name == xliff_file.name
    assert xliff.xml_root == xml_root
    assert xliff.xliff_version == 1.2
    assert (
        "xliff" in xliff.nsmap.values()
        or None in xliff.nsmap.values()
        or "urn:oasis:names:tc:xliff:document:1.2" in xliff.nsmap.values()
    )


def test_xliff_gen_translation_units(xliff_file):
    if not xliff_file.exists():
        pytest.skip("Test file tests/data/deneme.xliff not found.")

    xml_root = etree.parse(str(xliff_file)).getroot()
    xliff = XLIFF(xliff_file.name, xml_root)

    tus = list(xliff.gen_translation_units())
    assert len(tus) > 0
    for tu in tus:
        assert tu.tag == "translation-unit"
        assert "id" in tu.attrib
        for child in tu:
            assert child.tag in ("segment", "ignorable")
