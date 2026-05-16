from copy import deepcopy
import html
from pathlib import Path
import tempfile
import zipfile

import lxml.etree as etree


class DOCXParser:
    def __init__(self, nsmap: dict[str, str]):
        self.nsmap = nsmap

        self.tu_template = etree.Element("{{{0}}}unit".format(self.nsmap["xliff"]))
        tu_template_segment = etree.SubElement(
            self.tu_template, "{{{0}}}segment".format(self.nsmap["xliff"])
        )
        etree.SubElement(
            tu_template_segment, "{{{0}}}source".format(self.nsmap["xliff"])
        )
        etree.SubElement(
            tu_template_segment, "{{{0}}}target".format(self.nsmap["xliff"])
        )

        self.placeholder_template = etree.Element(
            "{{{0}}}placeholder".format(nsmap["kaplan"])
        )

    def generate_target_file(
        self,
        xml_root: etree.Element,
        output_directory: Path | str,
        path_to_source_file: Path | str | None,
        target_filename: str | None,
    ):
        parsed_source_file = xml_root.find("xliff:file", self.nsmap)
        if parsed_source_file is None:
            raise ValueError("No source file reference found in XLIFF.")

        source_nsmap = parsed_source_file[0][0].nsmap
        target_units = etree.Element("target-units")
        for trans_unit in parsed_source_file.findall(".//xliff:unit", self.nsmap):
            target_unit = etree.SubElement(
                target_units, "target-unit", trans_unit.attrib
            )

            original_data = trans_unit.find("xliff:originalData", self.nsmap)
            active_tags = []

            last_parent = None
            last_run = None

            for segment in trans_unit.xpath(
                ".//xliff:segment|.//xliff:ignorable",
                namespaces=self.nsmap,
            ):
                target = segment.find("xliff:target", self.nsmap)
                if target is None or (target.text is None and len(target) == 0):
                    target = segment.find("xliff:source", self.nsmap)

                if target.text is not None:
                    if last_parent is None:
                        last_parent = last_run = etree.SubElement(
                            target_unit, "{{{0}}}r".format(source_nsmap["w"])
                        )
                    elif last_run is None:
                        last_run = etree.SubElement(
                            target_unit, "{{{0}}}r".format(source_nsmap["w"])
                        )
                    w_t = etree.SubElement(
                        last_run, "{{{0}}}t".format(source_nsmap["w"])
                    )
                    if target.text != target.text.strip():
                        w_t.attrib["{{{0}}}space".format(self.nsmap["xml"])] = (
                            "preserve"
                        )
                    w_t.text = target.text

                for target_child in target:
                    target_child_localname = etree.QName(target_child).localname
                    if target_child_localname == "sc":
                        active_tags.append(
                            (target_child.attrib["id"], target_child.attrib["dataRef"])
                        )

                        new_element = etree.fromstring(
                            original_data.find(
                                'xliff:data[@id="{0}"]'.format(active_tags[0][1]),
                                self.nsmap,
                            ).text
                        )

                        new_element_localname = etree.QName(new_element).localname

                        if len(active_tags) == 1:
                            target_unit.append(new_element)
                            last_parent = new_element
                            if (
                                new_element_localname == "hyperlink"
                                and len(last_parent) == 1
                            ):
                                last_run = last_parent[0]
                            elif (
                                new_element_localname == "hyperlink"
                                and len(last_parent) == 0
                            ):
                                last_run = None
                            else:
                                last_run = last_parent
                        else:
                            if new_element_localname == "r":
                                if last_parent and last_run and last_parent != last_run:
                                    last_parent.append(new_element)
                                    last_run = new_element
                    elif target_child_localname == "ec":
                        for active_tag in active_tags:
                            if active_tag[0] == target_child.attrib["id"]:
                                removed_element = etree.fromstring(
                                    original_data.find(
                                        'xliff:data[@id="{0}"]'.format(active_tag[1]),
                                        self.nsmap,
                                    ).text
                                )
                                if (
                                    last_parent is not None
                                    and removed_element.tag == last_parent.tag
                                ):
                                    last_parent = None
                                if (
                                    last_run is not None
                                    and removed_element.tag == last_run.tag
                                ):
                                    last_run = None
                                active_tags.remove(active_tag)
                                break
                        if len(active_tags) > 0:
                            if last_parent is None:
                                new_element = etree.fromstring(
                                    original_data.find(
                                        'xliff:data[@id="{0}"]'.format(
                                            active_tags[0][1]
                                        ),
                                        self.nsmap,
                                    ).text
                                )
                                new_element_localname = etree.QName(
                                    new_element
                                ).localname

                                target_unit.append(new_element)
                                last_parent = new_element
                                if (
                                    new_element_localname == "hyperlink"
                                    and len(last_parent) == 1
                                ):
                                    last_run = last_parent[0]
                                elif (
                                    new_element_localname == "hyperlink"
                                    and len(last_parent) == 0
                                ):
                                    last_run = None
                                else:
                                    last_run = last_parent

                            elif last_run is None:
                                if len(active_tags) > 1:
                                    for active_tag in active_tags[1:]:
                                        new_element = etree.fromstring(
                                            original_data.find(
                                                'xliff:data[@id="{0}"]'.format(
                                                    active_tag[1]
                                                ),
                                                self.nsmap,
                                            ).text
                                        )
                                        new_element_localname = etree.QName(
                                            new_element
                                        ).localname

                                        if new_element_localname == "r":
                                            last_parent.append(new_element)
                                            last_run = new_element

                    elif target_child_localname == "ph":
                        new_element = etree.fromstring(
                            original_data.find(
                                'xliff:data[@id="{0}"]'.format(
                                    target_child.attrib["dataRef"]
                                ),
                                self.nsmap,
                            ).text
                        )

                        if last_parent is None:
                            last_parent = last_run = etree.SubElement(
                                target_unit, "{{{0}}}r".format(source_nsmap["w"])
                            )
                        elif last_run is None:
                            last_run = etree.SubElement(
                                last_parent, "{{{0}}}r".format(source_nsmap["w"])
                            )

                        last_run.append(new_element)

                    if target_child.tail is not None:
                        if last_parent is None:
                            last_parent = last_run = etree.SubElement(
                                target_unit, "{{{0}}}r".format(source_nsmap["w"])
                            )
                        elif last_run is None:
                            last_run = etree.SubElement(
                                last_parent, "{{{0}}}r".format(source_nsmap["w"])
                            )

                        w_t = etree.SubElement(
                            last_run, "{{{0}}}t".format(source_nsmap["w"])
                        )
                        if target_child.tail != target_child.tail.strip():
                            w_t.attrib["{{{0}}}space".format(self.nsmap["xml"])] = (
                                "preserve"
                            )
                        w_t.text = target_child.tail

        for target_unit in target_units:
            placeholder = xml_root.find(
                './/kaplan:placeholder[@id="{0}"]'.format(target_unit.attrib["id"]),
                self.nsmap,
            )
            paragraph_parent = placeholder.getparent()
            child_i = paragraph_parent.index(placeholder)
            paragraph_parent.remove(placeholder)
            for target_child in target_unit:
                paragraph_parent.insert(child_i, target_child)
                child_i += 1

        path_to_source_file = Path(
            path_to_source_file
            if path_to_source_file
            else parsed_source_file.attrib["original"]
        )
        target_filename = (
            target_filename if target_filename else path_to_source_file.name
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_dir_path = Path(tmp_dir)
            with zipfile.ZipFile(path_to_source_file) as source_zip:
                source_zip.extractall(tmp_dir)

            internal_file = xml_root.find(".//kaplan:internal-file", self.nsmap)
            etree.ElementTree(internal_file[0]).write(
                str(tmp_dir_path / internal_file.attrib["rel"]),
                encoding="UTF-8",
                xml_declaration=True,
            )

            with zipfile.ZipFile(
                (Path(output_directory) / target_filename), "w"
            ) as target_zip:
                for path_to_file in tmp_dir_path.rglob("*"):
                    target_zip.write(
                        path_to_file, path_to_file.relative_to(tmp_dir_path)
                    )

    def parse(
        self, source_file_path: Path | str, **kwargs
    ) -> tuple[etree.Element, list[etree.Element]]:
        source_file_path = Path(source_file_path)

        with zipfile.ZipFile(source_file_path) as source_zip:
            source_file_xml = etree.parse(
                source_zip.open("word/document.xml")
            ).getroot()

        source_nsmap = source_file_xml.nsmap

        internal_file = etree.Element(
            "{{{0}}}internal-file".format(self.nsmap["kaplan"]),
            {"rel": "word/document.xml"},
        )

        internal_file.append(source_file_xml)

        # TODO: Think this one over
        # source_file_reference.insert(0, internal_file)
        translation_units = []

        tu_counter = 1
        for paragraph_element in source_file_xml.xpath(
            "w:body/w:p|w:body/w:tbl/w:tr/w:tc//w:p",
            namespaces={"w": source_nsmap["w"]},
        ):
            if paragraph_element.find(".//w:t", source_nsmap) is None:
                continue
            placeholder_placed = False
            tu = deepcopy(self.tu_template)
            tu.attrib["id"] = str(tu_counter)
            tu_counter += 1

            translation_units.append(tu)
            source = tu[0][0]

            for paragraph_child in paragraph_element:
                if paragraph_child.tag.endswith("}pPr"):
                    continue

                textbox_paragraphs = paragraph_child.findall(".//w:p", source_nsmap)
                # TODO: Address repeating TUs of text box content for mc:Choice and mc:Fallback.
                for textbox_paragraph in textbox_paragraphs:
                    if textbox_paragraph.find(".//w:t", source_nsmap) is None:
                        continue
                    placeholder_placed = False
                    if len(source) >= 0 or source.text is not None:
                        tu = deepcopy(self.tu_template)
                        tu.attrib["id"] = str(tu_counter)
                        tu_counter += 1

                        translation_units.append(tu)
                        source = tu[0][0]

                    for textbox_child in textbox_paragraph:
                        if textbox_child.tag.endswith("}pPr"):
                            continue
                        if not placeholder_placed:
                            placeholder = deepcopy(self.placeholder_template)
                            placeholder.attrib["id"] = tu.attrib["id"]
                            textbox_paragraph.insert(
                                textbox_paragraph.index(textbox_child), placeholder
                            )
                            placeholder_placed = True

                        self.__extract_or_pass(textbox_child, tu, source, source_nsmap)
                        textbox_paragraph.remove(textbox_child)

                if not placeholder_placed:
                    placeholder = deepcopy(self.placeholder_template)
                    placeholder.attrib["id"] = tu.attrib["id"]
                    paragraph_element.insert(
                        paragraph_element.index(paragraph_child), placeholder
                    )
                    placeholder_placed = True
                self.__extract_or_pass(paragraph_child, tu, source, source_nsmap)
                paragraph_element.remove(paragraph_child)

        return internal_file, translation_units

    def __extract_or_pass(
        self,
        paragraph_child: etree.Element,
        tu: etree.Element,
        source: etree.Element,
        source_nsmap: dict[str, str],
    ):
        def add_text(source: etree.Element, text: str):
            if len(source) == 0:
                if source.text is None:
                    source.text = ""
                source.text += text
            else:
                if source[-1].tail is None:
                    source[-1].tail = ""
                source[-1].tail += text

        def add_placeholder(
            tu,
            source,
            data,
            tag,
            equiv=None,
            standalone=True,
            equiv_with_no=False,
        ):
            original_data = tu.find("{{{0}}}originalData".format(self.nsmap["xliff"]))
            if original_data is None:
                original_data = etree.Element(
                    "{{{0}}}originalData".format(self.nsmap["xliff"])
                )
                tu.insert(0, original_data)

            tag = "{{{0}}}{1}".format(self.nsmap["xliff"], tag)

            _data_text = etree.tostring(data, encoding="UTF-8").decode()

            for child in original_data:
                if child.text == _data_text:
                    _data = child
                    _data_id = child.attrib["id"]
                    break
            else:
                _data = etree.SubElement(
                    original_data, "{{{0}}}data".format(self.nsmap["xliff"])
                )
                _data_id = str(len(original_data))
                _data.attrib["id"] = _data_id
                _data.text = _data_text

            _tag = etree.SubElement(source, tag)
            _tag.attrib["id"] = _data_id
            _tag.attrib["dataRef"] = _data_id

            if equiv is None:
                equiv = data.tag.split("}")[-1]
            if equiv_with_no:
                equiv = "<{0}-{1}{2}>".format(
                    equiv, _data_id, "/" if standalone else ""
                )
            else:
                equiv = "<{0}{1}>".format(
                    data.tag.split("}")[-1], "/" if standalone else ""
                )

            _tag.attrib["equiv"] = html.escape(equiv)

            return _data_id

        def add_ending_tag(source, tag, equiv, starting_tag_i):
            tag = "{{{0}}}{1}".format(self.nsmap["xliff"], tag)

            _tag = etree.SubElement(
                source,
                tag,
                {"id": starting_tag_i, "dataRef": starting_tag_i},
            )
            _tag.attrib["equiv"] = html.escape(
                "</{0}-{1}>".format(equiv, starting_tag_i)
            )

        if paragraph_child.tag.endswith("}r"):
            run_properties = paragraph_child.find("w:rPr", source_nsmap)
            _tag_i = None
            if run_properties is not None and len(run_properties) > 0:
                run_w_properties = etree.Element(
                    "{{{0}}}r".format(source_nsmap["w"]),
                    paragraph_child.getparent().attrib,
                )
                run_w_properties.append(run_properties)

                _tag_i = add_placeholder(
                    tu, source, run_w_properties, "sc", "tag", False, True
                )

            for paragraph_grandchild in paragraph_child:
                self.__extract_or_pass(paragraph_grandchild, tu, source, source_nsmap)

            if run_properties is not None and len(run_properties) > 0 and _tag_i:
                add_ending_tag(source, "ec", "tag", _tag_i)

        elif paragraph_child.tag.endswith("}hyperlink"):
            hyperlink = etree.Element(
                "{{{0}}}hyperlink".format(source_nsmap["w"]),
                paragraph_child.attrib,
            )

            run_properties = paragraph_child[0].find("w:rPr", source_nsmap)
            if len(paragraph_child) == 1:
                if run_properties is not None and len(run_properties) > 0:
                    run_w_properties = etree.SubElement(
                        hyperlink,
                        "{{{0}}}r".format(source_nsmap["w"]),
                        paragraph_child[0].attrib,
                    )
                    run_w_properties.append(run_properties)
                    paragraph_child = paragraph_child[0]

            _tag_i = add_placeholder(tu, source, hyperlink, "sc", "link", False, True)

            for paragraph_grandchild in paragraph_child:
                self.__extract_or_pass(paragraph_grandchild, tu, source, source_nsmap)

            add_ending_tag(source, "ec", "link", _tag_i)

        elif paragraph_child.tag.endswith("}t"):
            add_text(source, paragraph_child.text)

        elif paragraph_child.tag.endswith(("}tab", "}br")):
            add_placeholder(tu, source, paragraph_child, "ph")

        elif paragraph_child.tag.endswith("}drawing"):
            add_placeholder(tu, source, paragraph_child, "ph", True, True)
