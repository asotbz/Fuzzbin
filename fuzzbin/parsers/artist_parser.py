"""Parser for artist.nfo files."""

import xml.etree.ElementTree as ET

from .models import ArtistNFO
from .nfo_parser import NFOParser


class ArtistNFOParser(NFOParser[ArtistNFO]):
    """Parser for artist.nfo files."""

    def __init__(self) -> None:
        """Initialize artist NFO parser."""
        super().__init__(model_class=ArtistNFO, root_element="artist")

    def _xml_to_dict(self, element: ET.Element) -> dict:
        """Convert artist XML to dictionary."""
        data = {}

        # Simple mapping: element tag -> field name
        field_map = {
            "name": "name",
        }

        for child in element:
            if child.tag in field_map:
                field_name = field_map[child.tag]
                # Get text content, strip whitespace
                text = child.text
                if text is not None:
                    data[field_name] = text.strip()

        return data

    def _dict_to_xml(self, parent: ET.Element, data: dict) -> None:
        """Convert artist dictionary to XML elements."""
        # Order of elements (for consistent output)
        field_order = ["name"]

        for field in field_order:
            if field in data:
                elem = ET.SubElement(parent, field)
                elem.text = str(data[field])
