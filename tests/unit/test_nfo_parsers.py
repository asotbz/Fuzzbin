"""Unit tests for NFO parsers."""

import pytest
from pathlib import Path
from pydantic import ValidationError

from fuzzbin.parsers import (
    ArtistNFO,
    MusicVideoNFO,
    ArtistNFOParser,
    MusicVideoNFOParser,
)


class TestArtistNFO:
    """Tests for ArtistNFO model."""

    def test_default_values(self):
        """Test default values for missing elements."""
        nfo = ArtistNFO()
        assert nfo.name is None

    def test_with_name(self):
        """Test creating with name."""
        nfo = ArtistNFO(name="Nirvana")
        assert nfo.name == "Nirvana"

    def test_ignores_unknown_fields(self):
        """Test that unknown fields are ignored."""
        nfo = ArtistNFO(name="Nirvana", unknown_field="value")
        assert nfo.name == "Nirvana"
        assert not hasattr(nfo, "unknown_field")


class TestMusicVideoNFO:
    """Tests for MusicVideoNFO model."""

    def test_default_values(self):
        """Test default values for all fields."""
        nfo = MusicVideoNFO()
        assert nfo.title is None
        assert nfo.album is None
        assert nfo.tags == []

    def test_with_all_fields(self):
        """Test creating with all fields."""
        nfo = MusicVideoNFO(
            title="Smells Like Teen Spirit",
            album="Nevermind",
            studio="DGC",
            year=1991,
            director="Samuel Bayer",
            genre="Rock",
            artist="Nirvana",
            tags=["90s", "grunge"],
        )
        assert nfo.title == "Smells Like Teen Spirit"
        assert nfo.year == 1991
        assert len(nfo.tags) == 2

    def test_year_validation(self):
        """Test year validation bounds."""
        with pytest.raises(ValidationError):
            MusicVideoNFO(year=1800)  # Too old

        with pytest.raises(ValidationError):
            MusicVideoNFO(year=2200)  # Too far in future

        # Valid years should work
        nfo = MusicVideoNFO(year=2020)
        assert nfo.year == 2020


class TestArtistNFOParser:
    """Tests for ArtistNFOParser."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return ArtistNFOParser()

    @pytest.fixture
    def sample_xml(self):
        """Sample artist.nfo XML."""
        return """<?xml version="1.0" encoding="utf-8"?>
<artist>
  <name>Nirvana</name>
</artist>"""

    def test_parse_string(self, parser, sample_xml):
        """Test parsing from XML string."""
        nfo = parser.parse_string(sample_xml)
        assert nfo.name == "Nirvana"

    def test_parse_file(self, parser, tmp_path):
        """Test parsing from file."""
        nfo_file = tmp_path / "artist.nfo"
        nfo_file.write_text(
            """<?xml version="1.0" encoding="utf-8"?>
<artist>
  <name>Pearl Jam</name>
</artist>"""
        )

        nfo = parser.parse_file(nfo_file)
        assert nfo.name == "Pearl Jam"

    def test_write_file(self, parser, tmp_path):
        """Test writing to file with pretty-printing."""
        nfo = ArtistNFO(name="Soundgarden")
        nfo_file = tmp_path / "artist.nfo"

        parser.write_file(nfo, nfo_file)

        assert nfo_file.exists()
        content = nfo_file.read_text()
        assert '<?xml version="1.0"' in content
        assert "<name>Soundgarden</name>" in content
        assert "<artist>" in content

    def test_to_xml_string(self, parser):
        """Test XML string generation."""
        nfo = ArtistNFO(name="Alice in Chains")
        xml = parser.to_xml_string(nfo)

        assert '<?xml version="1.0"' in xml
        assert "<artist>" in xml
        assert "<name>Alice in Chains</name>" in xml

    def test_update_field(self, parser):
        """Test field update."""
        nfo = ArtistNFO(name="Original")
        updated = parser.update_field(nfo, "name", "Updated")

        assert updated.name == "Updated"
        assert nfo.name == "Original"  # Original unchanged

    def test_missing_name_element(self, parser):
        """Test parsing with missing name element."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<artist>
</artist>"""
        nfo = parser.parse_string(xml)
        assert nfo.name is None

    def test_unknown_elements_ignored(self, parser):
        """Test that unknown elements are ignored."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<artist>
  <name>Test</name>
  <unknown_element>Should be ignored</unknown_element>
</artist>"""
        nfo = parser.parse_string(xml)
        assert nfo.name == "Test"

    def test_wrong_root_element_raises_error(self, parser):
        """Test that wrong root element raises error."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<musicvideo>
  <title>Wrong</title>
</musicvideo>"""
        with pytest.raises(ValueError):
            parser.parse_string(xml)

    def test_roundtrip(self, parser, tmp_path):
        """Test parse -> write -> parse roundtrip."""
        # Create original
        nfo1 = ArtistNFO(name="Stone Temple Pilots")

        # Write to file
        nfo_file = tmp_path / "artist.nfo"
        parser.write_file(nfo1, nfo_file)

        # Parse again
        nfo2 = parser.parse_file(nfo_file)

        # Should be equal
        assert nfo1.model_dump() == nfo2.model_dump()


class TestMusicVideoNFOParser:
    """Tests for MusicVideoNFOParser."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return MusicVideoNFOParser()

    @pytest.fixture
    def sample_xml(self):
        """Sample musicvideo.nfo XML."""
        return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<musicvideo>
    <title>Smells Like Teen Spirit</title>
    <album>Nevermind</album>
    <studio>DGC</studio>
    <year>1991</year>
    <director>Samuel Bayer</director>
    <genre>Rock</genre>
    <artist>Nirvana</artist>
    <tag>90s</tag>
    <tag>grunge</tag>
</musicvideo>"""

    def test_parse_string(self, parser, sample_xml):
        """Test parsing from XML string."""
        nfo = parser.parse_string(sample_xml)

        assert nfo.title == "Smells Like Teen Spirit"
        assert nfo.album == "Nevermind"
        assert nfo.studio == "DGC"
        assert nfo.year == 1991
        assert nfo.director == "Samuel Bayer"
        assert nfo.genre == "Rock"
        assert nfo.artist == "Nirvana"
        assert nfo.tags == ["90s", "grunge"]

    def test_parse_file(self, parser, tmp_path, sample_xml):
        """Test parsing from file."""
        nfo_file = tmp_path / "musicvideo.nfo"
        nfo_file.write_text(sample_xml)

        nfo = parser.parse_file(nfo_file)
        assert nfo.title == "Smells Like Teen Spirit"
        assert len(nfo.tags) == 2

    def test_write_file(self, parser, tmp_path):
        """Test writing to file."""
        nfo = MusicVideoNFO(
            title="Test Video",
            artist="Test Artist",
            year=2020,
            tags=["tag1", "tag2"],
        )
        nfo_file = tmp_path / "musicvideo.nfo"

        parser.write_file(nfo, nfo_file)

        assert nfo_file.exists()
        content = nfo_file.read_text()
        assert "<title>Test Video</title>" in content
        assert "<tag>tag1</tag>" in content
        assert "<tag>tag2</tag>" in content

    def test_roundtrip(self, parser, tmp_path, sample_xml):
        """Test parse -> write -> parse roundtrip."""
        # Parse original
        nfo1 = parser.parse_string(sample_xml)

        # Write to file
        nfo_file = tmp_path / "musicvideo.nfo"
        parser.write_file(nfo1, nfo_file)

        # Parse again
        nfo2 = parser.parse_file(nfo_file)

        # Should be equal
        assert nfo1.model_dump() == nfo2.model_dump()

    def test_add_tag(self, parser):
        """Test adding a tag."""
        nfo = MusicVideoNFO(title="Test", tags=["existing"])
        updated = parser.add_tag(nfo, "new_tag")

        assert updated.tags == ["existing", "new_tag"]
        assert nfo.tags == ["existing"]  # Original unchanged

    def test_remove_tag_first_occurrence(self, parser):
        """Test removing first occurrence of tag."""
        nfo = MusicVideoNFO(tags=["tag1", "tag2", "tag1"])
        updated = parser.remove_tag(nfo, "tag1", all_occurrences=False)

        assert updated.tags == ["tag2", "tag1"]

    def test_remove_tag_all_occurrences(self, parser):
        """Test removing all occurrences of tag."""
        nfo = MusicVideoNFO(tags=["tag1", "tag2", "tag1"])
        updated = parser.remove_tag(nfo, "tag1", all_occurrences=True)

        assert updated.tags == ["tag2"]

    def test_set_tags(self, parser):
        """Test replacing all tags."""
        nfo = MusicVideoNFO(tags=["old1", "old2"])
        updated = parser.set_tags(nfo, ["new1", "new2", "new3"])

        assert updated.tags == ["new1", "new2", "new3"]
        assert nfo.tags == ["old1", "old2"]  # Original unchanged

    def test_missing_optional_fields(self, parser):
        """Test parsing with many missing fields."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<musicvideo>
    <title>Minimal</title>
</musicvideo>"""
        nfo = parser.parse_string(xml)

        assert nfo.title == "Minimal"
        assert nfo.album is None
        assert nfo.year is None
        assert nfo.tags == []

    def test_no_tags(self, parser):
        """Test parsing with no tags."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<musicvideo>
    <title>No Tags</title>
    <artist>Artist</artist>
</musicvideo>"""
        nfo = parser.parse_string(xml)

        assert nfo.tags == []

    def test_invalid_year_skipped(self, parser):
        """Test that invalid year is skipped during parsing."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<musicvideo>
    <title>Test</title>
    <year>not_a_number</year>
</musicvideo>"""
        nfo = parser.parse_string(xml)

        assert nfo.title == "Test"
        assert nfo.year is None  # Invalid year skipped

    def test_update_field(self, parser):
        """Test field update."""
        nfo = MusicVideoNFO(title="Original Title", year=2020)
        updated = parser.update_field(nfo, "title", "New Title")

        assert updated.title == "New Title"
        assert updated.year == 2020
        assert nfo.title == "Original Title"  # Original unchanged

    def test_to_xml_string(self, parser):
        """Test XML string generation."""
        nfo = MusicVideoNFO(
            title="Test",
            artist="Artist",
            year=2020,
            tags=["tag1", "tag2"],
        )
        xml = parser.to_xml_string(nfo)

        assert '<?xml version="1.0"' in xml
        assert "<musicvideo>" in xml
        assert "<title>Test</title>" in xml
        assert "<tag>tag1</tag>" in xml
        assert "<tag>tag2</tag>" in xml

    def test_remove_nonexistent_tag(self, parser):
        """Test removing a tag that doesn't exist."""
        nfo = MusicVideoNFO(tags=["tag1", "tag2"])
        updated = parser.remove_tag(nfo, "nonexistent")

        assert updated.tags == ["tag1", "tag2"]  # Unchanged

    def test_duplicate_tags_preserved(self, parser):
        """Test that duplicate tags are preserved."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<musicvideo>
    <title>Test</title>
    <tag>rock</tag>
    <tag>rock</tag>
    <tag>alternative</tag>
</musicvideo>"""
        nfo = parser.parse_string(xml)

        assert nfo.tags == ["rock", "rock", "alternative"]
