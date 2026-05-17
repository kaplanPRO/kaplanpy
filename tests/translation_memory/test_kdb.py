import pytest
from kaplan.translation_memory.kdb import KDB


@pytest.fixture
def kdb_path(tmp_path):
    return tmp_path / "test.kdb"


def test_kdb_creation(kdb_path):
    kdb = KDB.new(str(kdb_path), "en", "tr")
    assert kdb_path.exists()
    assert kdb.src == "en"
    assert kdb.trgt == "tr"
    assert kdb.conn is not None


def test_kdb_submit_and_query(kdb_path):
    kdb = KDB.new(str(kdb_path), "en", "tr")

    source = "Hello World"
    target = "Merhaba Dünya"
    kdb.submit_entry(source, target)

    # Check if entry is in the database
    cursor = kdb.conn.execute("SELECT source, target FROM main")
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == source
    assert row[1] == target


def test_kdb_get_all_source_entries(kdb_path):
    kdb = KDB.new(str(kdb_path), "en", "tr")
    kdb.submit_entry("Source 1", "Target 1")
    kdb.submit_entry("Source 2", "Target 2")

    # We need to find the method name for getting all source entries.
    # From project.py, it was get_all_source_entries()
    sources = kdb.get_all_source_entries()
    assert "Source 1" in sources
    assert "Source 2" in sources
