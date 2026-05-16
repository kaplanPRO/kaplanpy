from copy import deepcopy
from pathlib import Path

import lxml.etree as etree
import regex


class POParser:
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
        po_entries = {}

        for trans_unit in parsed_source_file.findall(".//xliff:unit", self.nsmap):
            po_id = int(trans_unit.attrib.get("rid", trans_unit.attrib["id"]))
            keys = trans_unit.attrib["keys"].split(";")
            if po_id not in po_entries:
                po_entries[po_id] = [trans_unit.attrib["metadata"], [], []]

            segment = ["", ""]
            for xml_segment in trans_unit.xpath(
                ".//xliff:segment|.//xliff:ignorable",
                namespaces={"xliff": self.nsmap["xliff"]},
            ):
                segment[0] += xml_segment.find("xliff:source", self.nsmap).text
                target = xml_segment.find("xliff:target", self.nsmap)
                if target is not None and target.text is not None:
                    segment[1] += target.text
            else:
                for s_i in range(len(segment)):
                    source_or_target_segment = [""]
                    for regex_hit in regex.findall(r"([^\s]+)?([\s]+)?", segment[s_i]):
                        for text_or_space in regex_hit:
                            if text_or_space != "" and (
                                len(source_or_target_segment[-1]) >= 80
                                or len(source_or_target_segment[-1] + text_or_space)
                                >= 80
                            ):
                                source_or_target_segment.append(text_or_space)
                            else:
                                source_or_target_segment[-1] += text_or_space
                    else:
                        if (
                            len(source_or_target_segment) > 1
                            and source_or_target_segment[0] != ""
                        ):
                            source_or_target_segment.insert(0, "")

                        for i in range(len(source_or_target_segment)):
                            source_or_target_segment[i] = (
                                '"' + source_or_target_segment[i] + '"'
                            )

                        segment[s_i] = source_or_target_segment

                po_entries[po_id][1].append(
                    "{0} {1}".format(keys[0], "\n".join(segment[0]))
                )
                po_entries[po_id][2].append(
                    "{0} {1}".format(keys[1], "\n".join(segment[1]))
                )

        with open((Path(output_directory) / target_filename), "w") as outfile:
            outfile.write(
                parsed_source_file.find("kaplan:internal-file", self.nsmap).text + "\n"
            )

            for po_entry_i in sorted(po_entries):
                po_entry = po_entries[po_entry_i]
                outfile.write(po_entry[0] + "\n")
                for line in po_entry[1] + po_entry[2]:
                    outfile.write(line + "\n")
                else:
                    outfile.write("\n")

    def parse(
        self, source_file: Path | str, segmentation: str | bool = "default"
    ) -> tuple[etree.Element, list[etree.Element]]:
        source_file_path = Path(source_file)

        def entry_checkpoint(entry, entry_metadata, entries):
            if entry.get("msgid", None) is not None:
                entry["metadata"] = "\n".join(entry_metadata)
                entries.append(entry)

            return entries

        entries = []

        regex_compile = regex.compile(r'([a-z0-9\[\]_]+)?\s?"(.*?)"$')

        with open(source_file_path, encoding="UTF-8") as po_file:
            entry = {}
            entry_metadata = []
            last_element = ""

            for line in po_file:
                line = line.strip()

                if line.startswith("#"):
                    entry_metadata.append(line)
                    continue

                if line == "":
                    entries = entry_checkpoint(entry, entry_metadata, entries)
                    entry, entry_metadata, last_element = {}, [], ""
                    continue

                regex_match = regex_compile.search(line)

                if regex_match is None:
                    continue

                if regex_match.group(1):
                    last_element = regex_match.group(1)
                    entry[last_element] = ""

                if regex_match.group(2):
                    entry[last_element] += regex_match.group(2)
            else:
                entries = entry_checkpoint(entry, entry_metadata, entries)

        po_metadata = '{0}\nmsgid ""\nmsgstr ""\n{1}\n'.format(
            entries[0]["metadata"],
            "\n".join(
                '"' + line + '\\n"'
                for line in entries[0]["msgstr"].split("\\n")
                if line
            ),
        )

        source_file_content = etree.Element(
            "{{{0}}}internal-file".format(self.nsmap["kaplan"]),
            nsmap={None: self.nsmap["kaplan"]},
        )
        source_file_content.attrib["{{{0}}}rel".format(self.nsmap["kaplan"])] = "self"
        source_file_content.text = po_metadata

        entries = entries[1:]

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

        for entry in entries:
            tu = deepcopy(tu_template)
            tu.attrib["id"] = str(tu_counter)
            tu.attrib["metadata"] = entry.get("metadata", "")
            translation_units.append(tu)
            tu_counter += 1
            source = tu.find(".//xliff:source", self.nsmap)
            target = tu.find(".//xliff:target", self.nsmap)
            source.text = entry["msgid"]
            target_key = "msgstr" if "msgstr" in entry else "msgstr[0]"
            target.text = entry[target_key]

            tu.attrib["keys"] = ";".join(("msgid", target_key))

            if "msgid_plural" in entry or "plural" in entry:
                tu.attrib["rid"] = tu.attrib["id"]
                source_key = "msgid_plural" if "msgid_plural" in entry else "plural"
                tu = deepcopy(tu)
                tu.attrib["id"] = str(tu_counter)
                translation_units.append(tu)
                tu_counter += 1
                source = tu.find(".//xliff:source", self.nsmap)
                target = tu.find(".//xliff:target", self.nsmap)
                source.text = entry[source_key]
                target.text = entry.get("msgstr[1]", "")

                tu.attrib["keys"] = ";".join((source_key, "msgstr[1]"))

        return source_file_content, translation_units
