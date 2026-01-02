"""Base NFO parser with XML utilities."""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Generic, Type, TypeVar
from xml.dom import minidom

import structlog
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class NFOParser(Generic[T]):
    """
    Base class for NFO file parsing and writing.

    Provides XML parsing, validation, pretty-printing, and CRUD operations.
    """

    def __init__(self, model_class: Type[T], root_element: str):
        """
        Initialize parser.

        Args:
            model_class: Pydantic model class for validation
            root_element: Root XML element name (e.g., "artist", "musicvideo")
        """
        self.model_class = model_class
        self.root_element = root_element
        self.logger = logger.bind(parser=self.__class__.__name__)

    def parse_file(self, file_path: Path) -> T:
        """
        Parse NFO file and return validated model.

        Args:
            file_path: Path to NFO file

        Returns:
            Validated Pydantic model instance

        Raises:
            FileNotFoundError: If file doesn't exist
            ET.ParseError: If XML is malformed
            ValueError: If root element doesn't match expected
            ValidationError: If data fails Pydantic validation
        """
        self.logger.info("parsing_nfo_file", file_path=str(file_path))

        # Parse XML
        tree = ET.parse(file_path)
        root = tree.getroot()

        # Validate root element
        if root.tag != self.root_element:
            raise ValueError(f"Expected root element '{self.root_element}', got '{root.tag}'")

        # Convert XML to dict
        data = self._xml_to_dict(root)

        # Validate with Pydantic
        model = self.model_class.model_validate(data)

        self.logger.info("nfo_file_parsed", file_path=str(file_path))
        return model

    def parse_string(self, xml_string: str) -> T:
        """
        Parse NFO from XML string.

        Args:
            xml_string: XML content as string

        Returns:
            Validated Pydantic model instance

        Raises:
            ET.ParseError: If XML is malformed
            ValueError: If root element doesn't match expected
            ValidationError: If data fails Pydantic validation
        """
        root = ET.fromstring(xml_string)

        if root.tag != self.root_element:
            raise ValueError(f"Expected root element '{self.root_element}', got '{root.tag}'")

        data = self._xml_to_dict(root)
        return self.model_class.model_validate(data)

    def write_file(self, model: T, file_path: Path, create_dirs: bool = True) -> None:
        """
        Write model to NFO file with pretty-printing.

        Args:
            model: Pydantic model instance
            file_path: Output file path
            create_dirs: Create parent directories if they don't exist
        """
        self.logger.info("writing_nfo_file", file_path=str(file_path))

        if create_dirs:
            file_path.parent.mkdir(parents=True, exist_ok=True)

        xml_string = self.to_xml_string(model)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(xml_string)

        self.logger.info("nfo_file_written", file_path=str(file_path))

    def to_xml_string(self, model: T, pretty: bool = True) -> str:
        """
        Convert model to XML string.

        Args:
            model: Pydantic model instance
            pretty: Enable pretty-printing (default: True)

        Returns:
            XML string with declaration
        """
        # Convert model to dict (exclude None values and empty lists)
        data = model.model_dump(exclude_none=True)

        # Build XML tree
        root = ET.Element(self.root_element)
        self._dict_to_xml(root, data)

        # Convert to string
        xml_string = ET.tostring(root, encoding="unicode")

        if pretty:
            # Use minidom for pretty-printing
            dom = minidom.parseString(xml_string)
            # Get pretty XML without extra blank lines
            if dom.documentElement is None:
                raise ValueError("Failed to parse XML: no document element")
            pretty_lines = []
            for line in dom.documentElement.toprettyxml(indent="    ").split("\n"):
                if line.strip():  # Skip empty lines
                    pretty_lines.append(line)
            pretty_xml = "\n".join(pretty_lines)
            # Add proper XML declaration
            xml_string = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + pretty_xml + "\n"
            )
        else:
            xml_string = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + xml_string + "\n"
            )

        return xml_string

    def update_field(self, model: T, field_name: str, value: Any) -> T:
        """
        Update a single field and return new validated model.

        Args:
            model: Current model instance
            field_name: Field name to update
            value: New value

        Returns:
            New model instance with updated field

        Raises:
            ValidationError: If update fails validation
        """
        self.logger.info("updating_field", field=field_name, value=value)

        # Get current data
        data = model.model_dump()

        # Update field
        data[field_name] = value

        # Re-validate
        return self.model_class.model_validate(data)

    def _xml_to_dict(self, element: ET.Element) -> dict:
        """
        Convert XML element to dictionary.

        Handles multiple elements with same tag (like <tag> in musicvideo).
        Subclasses must override for custom behavior.
        """
        raise NotImplementedError("Subclasses must implement _xml_to_dict")

    def _dict_to_xml(self, parent: ET.Element, data: dict) -> None:
        """
        Convert dictionary to XML elements.

        Handles lists (like tags) by creating multiple elements.
        Subclasses must override for custom behavior.
        """
        raise NotImplementedError("Subclasses must implement _dict_to_xml")
