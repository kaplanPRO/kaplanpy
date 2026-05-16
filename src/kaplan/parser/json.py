from copy import deepcopy
import json
from pathlib import Path

import lxml.etree as etree


class JSONParser:
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
        target_list = []

        for trans_unit in parsed_source_file.findall(".//xliff:unit", self.nsmap):
            target_segment = ""
            for segment in trans_unit.xpath(
                ".//xliff:segment|.//xliff:ignorable",
                namespaces={"xliff": self.nsmap["xliff"]},
            ):
                target = segment.find("xliff:target", self.nsmap)
                if target is not None and target.text is not None:
                    target_segment += target.text

                else:
                    target_segment += segment.find("xliff:source", self.nsmap).text

            key = trans_unit.attrib["{{{0}}}key".format(self.nsmap["kaplan"])]
            target_list.append([key, target_segment])

        for i in range(1, len(target_list)):
            p_i = i - 1
            while target_list[i][0] == target_list[p_i][0]:
                if target_list[p_i][1] is None:
                    p_i -= 1
                    continue
                if isinstance(target_list[p_i][1], list):
                    target_list[p_i][1].append(target_list[i][1])
                else:
                    target_list[p_i][1] = [target_list[p_i][1], target_list[i][1]]
                target_list[i][1] = None
                break

        target_list = list(filter(lambda x: x[1] is not None, target_list))

        for i, segment in enumerate(target_list):
            segment_keys = segment[0].split(".")
            segment_keys.reverse()
            segment_new = {segment_keys[0]: segment[1]}
            for segment_key in segment_keys[1:]:
                segment_new = {segment_key: segment_new}
            target_list[i] = segment_new

        def _mergedict(to_dict, from_dict):
            for k, v in from_dict.items():
                if k not in to_dict:
                    to_dict[k] = v
                else:
                    to_dict[k] = _mergedict(to_dict[k], from_dict[k])
            return to_dict

        target_dict = {}
        for segment in target_list:
            target_dict = _mergedict(target_dict, segment)

        with open((Path(output_directory) / target_filename), "w") as outfile:
            json.dump(target_dict, outfile, indent=4)

    def parse(
        self, source_file: Path | str, **kwargs
    ) -> tuple[None, list[etree.Element]]:
        source_file_path = Path(source_file)

        translation_units = []

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

        def _create_unit(source, key):
            tu = deepcopy(tu_template)
            tu.attrib["{{{0}}}key".format(self.nsmap["kaplan"])] = ".".join(key)
            translation_units.append(tu)

            source_element = tu.find(".//xliff:source", self.nsmap)
            target_element = tu.find(".//xliff:target", self.nsmap)

            if source.strip() == "":
                tu[0].tag = "{{{0}}}ignorable".format(self.nsmap["xliff"])
                tu[0].remove(target_element)
            else:
                tu.attrib["id"] = str(len(translation_units))

            source_element.text = source

        def _extract_json(kaynak, keys=[]):
            for k, v in kaynak.items():
                if isinstance(v, dict):
                    _extract_json(v, (keys + [k]))
                elif isinstance(v, list):
                    for child_v in v:
                        _create_unit(child_v, (keys + [k]))
                else:
                    _create_unit(v, (keys + [k]))

        with open(source_file_path, "rb") as source_file:
            _extract_json(json.load(source_file))

        return None, translation_units
