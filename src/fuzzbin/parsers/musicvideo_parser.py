"""Parser for musicvideo.nfo files."""

import xml.etree.ElementTree as ET
from typing import List

from .models import MusicVideoNFO
from .nfo_parser import NFOParser


class MusicVideoNFOParser(NFOParser[MusicVideoNFO]):
    """Parser for musicvideo.nfo files with tag management."""

    def __init__(self):
        """Initialize music video NFO parser."""
        super().__init__(model_class=MusicVideoNFO, root_element="musicvideo")

    def _xml_to_dict(self, element: ET.Element) -> dict:
        """Convert musicvideo XML to dictionary."""
        data = {}
        tags = []

        # Field mapping (all single-occurrence except 'tag')
        field_map = {
            "title": "title",
            "album": "album",
            "studio": "studio",
            "year": "year",
            "director": "director",
            "genre": "genre",
            "artist": "artist",
        }

        for child in element:
            if child.tag == "tag":
                # Collect multiple tag elements
                if child.text:
                    tags.append(child.text.strip())
            elif child.tag in field_map:
                field_name = field_map[child.tag]
                text = child.text
                if text is not None:
                    value = text.strip()
                    # Convert year to int
                    if field_name == "year":
                        try:
                            value = int(value)
                        except ValueError:
                            # Skip invalid year values
                            self.logger.warning("invalid_year_value", value=value)
                            continue
                    data[field_name] = value

        # Add tags if any were found
        if tags:
            data["tags"] = tags

        return data

    def _dict_to_xml(self, parent: ET.Element, data: dict) -> None:
        """Convert musicvideo dictionary to XML elements."""
        # Element order (matching typical NFO structure)
        field_order = ["title", "album", "studio", "year", "director", "genre", "artist"]

        for field in field_order:
            if field in data:
                elem = ET.SubElement(parent, field)
                elem.text = str(data[field])

        # Add tag elements (multiple)
        if "tags" in data:
            for tag in data["tags"]:
                elem = ET.SubElement(parent, "tag")
                elem.text = tag

    def add_tag(self, model: MusicVideoNFO, tag: str) -> MusicVideoNFO:
        """
        Add a tag to the music video.

        Args:
            model: Current model instance
            tag: Tag to add

        Returns:
            New model instance with tag added

        Note:
            Duplicates are allowed (no deduplication).
        """
        self.logger.info("adding_tag", tag=tag)

        data = model.model_dump()
        tags = data.get("tags", [])
        tags.append(tag)
        data["tags"] = tags

        return self.model_class.model_validate(data)

    def remove_tag(
        self, model: MusicVideoNFO, tag: str, all_occurrences: bool = False
    ) -> MusicVideoNFO:
        """
        Remove tag(s) from the music video.

        Args:
            model: Current model instance
            tag: Tag to remove
            all_occurrences: Remove all matching tags (default: False, removes first only)

        Returns:
            New model instance with tag(s) removed
        """
        self.logger.info("removing_tag", tag=tag, all_occurrences=all_occurrences)

        data = model.model_dump()
        tags = data.get("tags", [])

        if tag in tags:
            if all_occurrences:
                tags = [t for t in tags if t != tag]
            else:
                tags.remove(tag)  # Remove first occurrence

        data["tags"] = tags

        return self.model_class.model_validate(data)

    def set_tags(self, model: MusicVideoNFO, tags: List[str]) -> MusicVideoNFO:
        """
        Replace all tags with new list.

        Args:
            model: Current model instance
            tags: New list of tags

        Returns:
            New model instance with tags replaced
        """
        self.logger.info("setting_tags", tag_count=len(tags))

        data = model.model_dump()
        data["tags"] = tags

        return self.model_class.model_validate(data)
