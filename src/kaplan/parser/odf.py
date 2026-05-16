from copy import deepcopy
import html
from pathlib import Path
import tempfile
import zipfile

import lxml.etree as etree


class ODFParser:
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

            last_parent = target_unit
            last_span = target_unit

            for segment in trans_unit.xpath(
                ".//xliff:segment|.//xliff:ignorable",
                namespaces=self.nsmap,
            ):
                target = segment.find("xliff:target", self.nsmap)
                if target is None or (target.text is None and len(target) == 0):
                    target = segment.find("xliff:source", self.nsmap)

                if target.text is not None:
                    self._add_text_to_span(last_span, target.text)

                for child in target:
                    child_localname = etree.QName(child).localname

                    if child_localname == "sc":
                        last_parent_localname = etree.QName(last_parent).localname
                        active_tags.append(child.attrib["dataRef"])
                        new_child = etree.fromstring(
                            original_data.find(
                                'xliff:data[@id="{0}"]'.format(child.attrib["dataRef"]),
                                self.nsmap,
                            ).text
                        )
                        new_child_localname = etree.QName(new_child).localname
                        if len(active_tags) == 1:
                            new_child_span = new_child.find("text:span", source_nsmap)
                            target_unit.append(new_child)
                            if new_child_span is not None:
                                last_parent = new_child
                                last_span = new_child_span
                            else:
                                last_parent = last_span = new_child

                        elif len(active_tags) == 2:
                            if (
                                last_parent_localname == "a"
                                and new_child_localname == "span"
                            ):
                                last_parent.append(new_child)
                                last_span = new_child

                    elif child_localname == "ec":
                        last_parent_localname = etree.QName(last_parent).localname
                        if active_tags.index(child.attrib["dataRef"]) == 0:
                            last_parent = target_unit
                            last_span = target_unit
                        elif (
                            active_tags.index(child.attrib["dataRef"]) == 1
                            and last_parent_localname == "a"
                        ):
                            last_span = last_parent

                        active_tags.remove(child.attrib["dataRef"])

                        if len(active_tags) > 1:
                            new_child = etree.fromstring(
                                original_data.find(
                                    'xliff:data[@id="{0}"]'.format(active_tags[1]),
                                    self.nsmap,
                                ).text
                            )
                            new_child_localname = etree.QName(new_child).localname
                            if (
                                last_parent_localname == "a"
                                and new_child_localname == "span"
                            ):
                                last_parent.append(new_child)
                                last_span = new_child
                        elif len(active_tags) == 1:
                            if last_parent == target_unit:
                                new_child = etree.fromstring(
                                    original_data.find(
                                        'xliff:data[@id="{0}"]'.format(active_tags[0]),
                                        self.nsmap,
                                    ).text
                                )
                                new_child_span = new_child.find(
                                    "text:span", source_nsmap
                                )
                                target_unit.append(new_child)
                                if new_child_span is not None:
                                    last_parent = new_child
                                    last_span = new_child_span
                                else:
                                    last_parent = last_span = new_child
                    else:
                        last_span.append(
                            etree.fromstring(
                                original_data.find(
                                    'xliff:data[@id="{0}"]'.format(
                                        child.attrib["dataRef"]
                                    ),
                                    self.nsmap,
                                ).text
                            )
                        )

                    if child.tail is not None:
                        self._add_text_to_span(last_span, child.tail)

        for target_unit in target_units:
            placeholder = xml_root.find(
                './/kaplan:placeholder[@id="{0}"]'.format(target_unit.attrib["id"]),
                self.nsmap,
            )
            placeholder_parent = placeholder.getparent()
            placeholder_i = placeholder_parent.index(placeholder)
            placeholder_parent.remove(placeholder)

            if target_unit.text is not None:
                if placeholder_i == 0:
                    placeholder_parent.text = target_unit.text
                else:
                    placeholder_parent[-1].tail = target_unit.text

            for child in target_unit:
                placeholder_parent.insert(placeholder_i, child)
                placeholder_i += 1

        if target_filename is None:
            if path_to_source_file is None:
                path_to_source_file = parsed_source_file.attrib.get("original")

            if path_to_source_file is None:
                raise ValueError("Could not determine target filename.")

            target_filename = Path(path_to_source_file).name

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_dir_path = Path(tmp_dir)

            if path_to_source_file is None:
                path_to_source_file = parsed_source_file.attrib["original"]

            if path_to_source_file is None:
                raise ValueError("Could not determine source file path.")

            with zipfile.ZipFile(path_to_source_file) as source_zip:
                source_zip.extractall(tmp_dir_path)

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
    ) -> tuple[list[etree.Element], list[etree.Element]]:
        source_file_path = Path(source_file_path)

        internal_files = []
        with zipfile.ZipFile(source_file_path) as source_zip:
            for zip_child in source_zip.namelist():
                if zip_child.lower().endswith("content.xml"):
                    internal_file = etree.Element(
                        "{{{0}}}internal-file".format(self.nsmap["kaplan"]),
                        {"rel": zip_child},
                    )
                    internal_file.append(
                        etree.parse(source_zip.open(zip_child)).getroot()
                    )
                    internal_files.append(internal_file)

        source_nsmap = internal_files[0][0].nsmap
        translation_units = []
        tu_counter = 1

        for internal_file in internal_files:
            for paragraph in internal_file.xpath(
                ".//text:p|.//text:h", namespaces={"text": source_nsmap["text"]}
            ):
                if paragraph.text is None and (
                    len(paragraph) == 0
                    or (
                        all(child.text is None for child in paragraph)
                        and all(child.tail is None for child in paragraph)
                    )
                ):
                    continue
                tu = deepcopy(self.tu_template)
                tu.attrib["id"] = str(tu_counter)
                tu_counter += 1

                translation_units.append(tu)
                source = tu[0][0]

                self._extract_or_pass(paragraph, tu, source, source_nsmap)

                placeholder = deepcopy(self.placeholder_template)
                placeholder.attrib["id"] = tu.attrib["id"]

                paragraph.text = None
                for child in paragraph:
                    if child.find("draw:text-box", source_nsmap) is None:
                        paragraph.remove(child)
                    else:
                        child.tail = None

                paragraph.append(placeholder)

        return internal_files, translation_units

    def _add_text_to_span(self, last_span, text):
        if len(last_span) == 0:
            if last_span.text is None:
                last_span.text = text
            else:
                last_span.text += text
        else:
            if last_span[-1].tail is None:
                last_span[-1].tail = text
            else:
                last_span[-1].tail += text

    def _extract_or_pass(self, current_element, tu, source, source_nsmap):
        def add_text(source, text):
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
            data_id=None,
        ):
            original_data = tu.find("{{{0}}}originalData".format(self.nsmap["xliff"]))
            if original_data is None:
                original_data = etree.Element(
                    "{{{0}}}originalData".format(self.nsmap["xliff"])
                )
                tu.insert(0, original_data)

            tag = "{{{0}}}{1}".format(self.nsmap["xliff"], tag)

            _data = original_data.find(
                'xliff:data[@id="{0}"]'.format(data_id), self.nsmap
            )
            if _data is None:
                _data = etree.SubElement(
                    original_data, "{{{0}}}data".format(self.nsmap["xliff"])
                )
                _data_id = data_id if data_id is not None else str(len(original_data))
                _data.attrib["id"] = _data_id
                _data.text = etree.tostring(data, encoding="UTF-8").decode()
            else:
                _data_id = _data.attrib["id"]

            _tag = etree.SubElement(source, tag)
            _tag_id = str(len(source.findall(tag)))
            _tag.attrib["id"] = _tag_id
            _tag.attrib["dataRef"] = _data_id

            if equiv is None:
                equiv = data.tag.split("}")[-1]
                if equiv_with_no:
                    equiv = "<{0}-{1}{2}>".format(
                        equiv, _tag_id, "/" if standalone else ""
                    )
                else:
                    equiv = "<{0}{1}>".format(
                        data.tag.split("}")[-1], "/" if standalone else ""
                    )

            _tag.attrib["equiv"] = html.escape(equiv)

            return _tag_id, _data_id

        def add_ending_tag(tu, source, tag, equiv, starting_tag_i, data_id):
            tag = "{{{0}}}{1}".format(self.nsmap["xliff"], tag)

            tag_attrib = {
                "id": starting_tag_i,
                "dataRef": data_id,
                "equiv": html.escape(equiv),
            }
            etree.SubElement(source, tag, tag_attrib)

        if current_element.text is not None:
            add_text(source, current_element.text)
            current_element.text = None

        for child in current_element:
            child_localname = etree.QName(child).localname

            if child_localname == "span":
                child_copy = etree.Element(child.tag, child.attrib)
                style_name = child.attrib[
                    "{{{0}}}style-name".format(source_nsmap["text"])
                ]

                tag_id, data_id = add_placeholder(
                    tu,
                    source,
                    child_copy,
                    "sc",
                    "<{0}>".format(style_name),
                    False,
                    False,
                    style_name,
                )

                self._extract_or_pass(child, tu, source, source_nsmap)

                add_ending_tag(
                    tu,
                    source,
                    "ec",
                    "</{0}>".format(style_name),
                    tag_id,
                    data_id,
                )

            elif child_localname == "a":
                child_copy = etree.Element(child.tag, child.attrib)
                if len(child) == 1 and child[0].tail is None and child.text is None:
                    tag_id, data_id = add_placeholder(
                        tu, source, child_copy, "sc", None, False, True
                    )

                    add_text(source, child[0].text)

                    add_ending_tag(
                        tu,
                        source,
                        "ec",
                        "</a-{0}>".format(data_id),
                        tag_id,
                        data_id,
                    )

                else:
                    tag_id, data_id = add_placeholder(
                        tu, source, child_copy, "sc", None, False, True
                    )

                    self._extract_or_pass(child, tu, source, source_nsmap)

                    add_ending_tag(
                        tu,
                        source,
                        "ec",
                        "</a-{0}>".format(data_id),
                        tag_id,
                        data_id,
                    )

            elif (
                child_localname == "frame"
                and child.find("draw:text-box", source_nsmap) is None
            ):
                add_placeholder(tu, source, child, "ph", None, True, True)

            elif child_localname == "line-break":
                add_placeholder(
                    tu,
                    source,
                    etree.Element(child.tag),
                    "ph",
                    "<line-break/>",
                )

            if child.tail is not None:
                add_text(source, child.tail)
                child.tail = None
