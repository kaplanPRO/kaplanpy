from copy import deepcopy
from pathlib import Path

import lxml.etree as etree


class TXTParser:
    def __init__(self, nsmap: dict[str, str]):
        self.nsmap = nsmap

    def generate_target_file(
        self,
        xml_root: etree.Element,
        output_directory: Path | str,
        path_to_source_file: Path | str | None,
        target_filename: str | None,
    ):
        parsed_source_file = xml_root.find("xliff:file", self.nsmap)

        with open((Path(output_directory) / target_filename), "w") as outfile:
            for trans_unit in parsed_source_file.findall(".//xliff:unit", self.nsmap):
                for segment in trans_unit.xpath(
                    ".//xliff:segment|.//xliff:ignorable",
                    namespaces={"xliff": self.nsmap["xliff"]},
                ):
                    target = segment.find("xliff:target", self.nsmap)
                    if target is not None and target.text is not None:
                        outfile.write(target.text)

                    else:
                        outfile.write(segment.find("xliff:source", self.nsmap).text)

    def parse(
        self, source_file: Path | str, **kwargs
    ) -> tuple[None, list[etree.Element]]:
        source_file_path = Path(source_file)

        translation_units = []
        tu_counter = 1

        tu_template = etree.Element("{{{0}}}unit".format(self.nsmap["xliff"]))
        tu_template_segment = etree.SubElement(
            tu_template, "{{{0}}}segment".format(self.nsmap["xliff"])
        )
        etree.SubElement(
            tu_template_segment, "{{{0}}}source".format(self.nsmap["xliff"])
        )
        etree.SubElement(
            tu_template_segment, "{{{0}}}target".format(self.nsmap["xliff"])
        )

        with open(source_file_path, encoding="UTF-8") as source_file:
            for line in source_file:
                tu = deepcopy(tu_template)
                tu.attrib["id"] = str(tu_counter)
                translation_units.append(tu)
                tu_counter += 1
                source_element = tu.find(".//xliff:source", self.nsmap)
                target_element = tu.find(".//xliff:target", self.nsmap)

                if line.strip() == "":
                    tu[0].tag = "{{{0}}}ignorable".format(self.nsmap["xliff"])
                    tu[0].remove(target_element)

                source_element.text = line

        return None, translation_units
