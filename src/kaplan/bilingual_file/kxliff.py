# Installed libraries
import lxml.etree as etree
import regex

# Standard Python libraries
from copy import deepcopy
from datetime import datetime
import html
import json
from pathlib import Path
import random
import string
import tempfile
import zipfile

# Internal Python files
from kaplan.parser import SourceTypeEnum, source_to_parser_map
from .xliff import XLIFF

nsmap = {
    "kaplan": "https://kaplan.pro",
    "xliff": "urn:oasis:names:tc:xliff:document:2.1",
    "xml": "http://www.w3.org/XML/1998/namespace",
}


class KXLIFF(XLIFF):
    """
    A slightly modified version of the XML Localisation File Format (http://docs.oasis-open.org/xliff/xliff-core/v2.1/xliff-core-v2.1.html).

    Class KXLIFF offers native support for .xliff and .sdlxliff files.

    Args:
        name: Name of the file
        xml_root: The xml root of the file
    """

    def __init__(self, name, xml_root):
        if not name.lower().endswith(".kxliff") or "kaplan" not in xml_root.nsmap:
            raise TypeError("This class may only handle .kxliff files.")
        super().__init__(name, xml_root)

    def add_comment(self, segment_i, comment, author):
        """
        Adds a segment-level comment.
        """
        segment = self.xml_root.xpath(
            './/xliff:segment[@id="{0}"]|segment[@id="{0}"]'.format(segment_i),
            namespaces=nsmap,
        )

        if segment != []:
            unit = segment[0].getparent()
            notes = unit.xpath("xliff:notes|notes", namespaces=nsmap)
            if notes != []:
                notes = notes[0]
            else:
                notes = etree.SubElement(unit, "{{{0}}}notes".format(nsmap["xliff"]))

            note = etree.SubElement(
                notes,
                "{{{0}}}note".format(nsmap["xliff"]),
                {
                    "id": str(len(notes.xpath("xliff:note", namespaces=nsmap)) + 1),
                    "segment": str(segment_i),
                    "state": "open",
                    "added_at": datetime.utcnow().isoformat(),
                    "added_by": author,
                },
            )

            note.text = comment

        else:
            raise ValueError("Segment not found.")

    def add_loc_quality_issue(
        self, tu_i, segment_i, issue_type, issue_comment, issue_severity, author
    ):
        """
        Adds a segment-level localization quality flag.
        """
        tu = self.xml_root.xpath(
            './/xliff:unit[@id="{0}"]|unit[@id="{0}"]'.format(tu_i), namespaces=nsmap
        )[0]
        tu_loc_quality_issues = tu.find("kaplan:locQualityIssues", namespaces=nsmap)
        if tu_loc_quality_issues is None:
            tu_loc_quality_issues = etree.SubElement(
                tu, "{{{0}}}locQualityIssues".format(nsmap["kaplan"])
            )
        etree.SubElement(
            tu_loc_quality_issues,
            "{{{0}}}locQualityIssue".format(nsmap["kaplan"]),
            {
                "id": str(len(tu_loc_quality_issues) + 1),
                "segment": str(segment_i) if segment_i else "N/A",
                "type": issue_type,
                "comment": issue_comment,
                "severity": str(issue_severity),
                "added_at": datetime.utcnow().isoformat(),
                "added_by": author,
            },
        )

    def generate_lqi_report(self, output_path):
        """
        Generates a localization quality issue report.
        """
        segments = []

        for tu in self.get_translation_units():
            for segment in tu:
                if segment.tag.split("}")[-1] == "ignorable":
                    continue
                segment_source = segment.find("source", self.nsmap)
                segment_target = segment.find("target", self.nsmap)
                segment_history = self.get_segment_history(segment.attrib.get("id"))
                if (
                    segment.attrib.get("state") == "reviewed"
                    and segment_history is not None
                ):
                    segment_history = segment_history.xpath('*[@state="translated"]')
                else:
                    segment_history = []
                segment_lqi = self.get_segment_lqi(segment.attrib.get("id"))

                segments.append(
                    [
                        segment.attrib.get("id", "N/A"),
                        segment_source if segment_source is not None else None,
                        segment_history[-1]
                        if len(segment_history) > 0
                        else segment_target,
                        segment_target if len(segment_history) > 0 else None,
                        segment_lqi,
                    ]
                )

        report = etree.Element("html")
        head = etree.SubElement(report, "head")
        etree.SubElement(head, "meta", {"charset": "UTF-8"})
        etree.SubElement(
            head,
            "meta",
            {"name": "viewport", "content": "width=device-width, initial-scale=1"},
        )

        title = etree.SubElement(head, "title")
        title.text = self.name

        style = etree.SubElement(report, "style")
        style.text = """
        table {
            border-collapse: collapse;
            overflow-wrap: break-word;
            table-layout: fixed;}\n
        td {
            border-bottom: 1px solid #c5c5c5;
            border-right: 1px solid #c5c5c5;
            width: 24vw;}\n
        td div span {
            display: block;
            font-size: 0.8rem;
        }\n
        th {
            border-bottom: 1px solid #c5c5c5;
            border-right: 1px solid #c5c5c5;
        }\n
        ec, sc, ph {background-color: orangered;
            color: #FFF;
            cursor: pointer;
            margin: 0 1px;
            padding: 0 8px;
            user-select: all;
        }\n
        sc {
            border-top-left-radius: 4px;
            border-bottom-left-radius: 4px;
            padding: 0 4px 0 8px;
        }\n
        ec {
            border-top-right-radius: 4px;
            border-bottom-right-radius: 4px;
            padding: 0 8px 0 4px;
        }\n
        ph {
            border-radius: 4px;
        }
        """

        body = etree.SubElement(report, "body", nsmap={None: nsmap["xliff"]})

        table = etree.SubElement(body, "table")

        tr = etree.SubElement(table, "tr")

        th = etree.SubElement(tr, "th")
        th.text = "#"

        th = etree.SubElement(tr, "th")
        th.text = "Source"

        th = etree.SubElement(tr, "th")
        th.text = "Translation"

        th = etree.SubElement(tr, "th")
        th.text = "Edited Translation"

        th = etree.SubElement(tr, "th")
        th.text = "Flagged LQI"

        for segment in segments:
            tr = etree.SubElement(table, "tr")

            th = etree.SubElement(tr, "th")
            th.text = segment[0]

            td = etree.SubElement(tr, "td")
            if segment[1] is not None:
                td.append(segment[1])
            else:
                td.text = ""

            td = etree.SubElement(tr, "td")
            if segment[2] is not None:
                td.append(segment[2])
            else:
                td.text = ""

            td = etree.SubElement(tr, "td")
            if segment[3] is not None:
                td.append(segment[3])
            else:
                td.text = ""

            td = etree.SubElement(tr, "td")
            if len(segment[4]) > 0:
                for issue in segment[4]:
                    issue.tag = "div"
                    etree.SubElement(issue, "span").text = (
                        datetime.fromisoformat(issue.attrib["added_at"]).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                        + " UTC"
                    )
                    etree.SubElement(issue, "span").text = (
                        "Flagged by: " + issue.attrib["added_by"]
                    )
                    etree.SubElement(issue, "span").text = (
                        "Error: " + issue.attrib["type"]
                    )
                    comment = issue.attrib.get("comment")
                    if comment:
                        etree.SubElement(issue, "span").text = "Comment: " + comment
                    td.append(issue)
                    if issue != segment[4][-1]:
                        etree.SubElement(td, "hr")
            else:
                td.text = ""

        report.getroottree().write(str(output_path))

    def generate_target_translation(
        self, output_directory, path_to_source_file=None, target_filename=None
    ):
        """
        Generates a "clean" target file.

        Args:
            output_directory: Path to target directory where the target file will be saved.
            path_to_source_file (optional): Path to source file (Defaults to the
                                            file path saved when creating the
                                            .kxliff file).
            target_filename (optional): Name for the target file (Defaults to the
                                        name of the source file).

        """
        if not self.name.endswith(".kxliff"):
            raise TypeError("Function only available for .kxliff files.")

        output_directory = Path(output_directory)

        source_file = self.xml_root.find("file", self.nsmap)

        if path_to_source_file is None:
            path_to_source_file = source_file.attrib["original"]
        path_to_source_file = Path(path_to_source_file)

        source_filename = path_to_source_file.name

        if target_filename is None:
            target_filename = source_filename

        if source_filename.lower().endswith(
            (".docx", ".odp", ".ods", ".odt", ".po", ".json", ".txt")
        ):
            source_suffix = Path(source_filename).suffix.lower().strip().lstrip(r"\.")
            parser = source_to_parser_map[SourceTypeEnum(source_suffix)](nsmap)
            parser.generate_target_file(
                self.xml_root, output_directory, path_to_source_file, target_filename
            )

        else:
            raise ValueError("Filetype incompatible for this task!")

    def get_segment_history(self, segment_i):
        """
        Returns the version history of a segment.
        """
        segment_history = self.xml_root.find(
            './/kaplan:history/kaplan:segment[@id="{0}"]'.format(segment_i), self.nsmap
        )
        if segment_history is not None:
            segment_history = deepcopy(segment_history)
            for any_child in segment_history.findall(".//"):
                any_child.tag = any_child.tag.split("}")[-1]
                if "equiv" in any_child.attrib:
                    any_child.text = any_child.attrib["equiv"]

        return segment_history

    def get_segment_lqi(self, segment_i, ignore_resolved=True):
        """
        Returns the localization quality issues (LQIs) for a segment.

        Args:
            segment_i: Segment ID
            ignore_resolved: Specified whether resolved LQIs will be ignored.
        """
        segment_lqi = []
        for segment_loc_quality_issue in self.xml_root.xpath(
            './/kaplan:locQualityIssue[@segment="{0}"]'.format(segment_i),
            namespaces=nsmap,
        ):
            if ignore_resolved and segment_loc_quality_issue.attrib.get("resolved"):
                continue
            segment_lqi.append(deepcopy(segment_loc_quality_issue))
        return segment_lqi

    def merge_segments(self, list_of_segments):
        """
        Merges two segments of the same translation unit.

        Args:
            list_of_segments: List containing segment IDs.
        """

        assert len(list_of_segments) > 1, (
            "list_of_segments contains less than 2 segments."
        )

        def transfer_children(source_parent, target_parent):
            if source_parent.text is not None:
                if len(target_parent) == 0:
                    if target_parent.text is None:
                        target_parent.text = source_parent.text
                    else:
                        target_parent.text += source_parent.text
                else:
                    if target_parent[-1].tail is None:
                        target_parent[-1].tail = source_parent.text
                    else:
                        target_parent[-1].tail += source_parent.text
            for child in source_parent:
                target_parent.append(deepcopy(child))

        translation_unit = None
        segments = []
        segment_ids = []
        for segment_id in list_of_segments:
            segment = self.xml_root.xpath(
                './/xliff:segment[@id="{0}"]'.format(str(segment_id)), namespaces=nsmap
            )

            if segment == []:
                raise ValueError("Segment #{} does not exist.".format(segment_id))

            segment = segment[0]

            assert "locked" not in segment.attrib.get("subState", ""), (
                "Segment #{} is locked".format(segment_id)
            )

            if translation_unit is None:
                translation_unit = segment.getparent()

            else:
                assert translation_unit == segment.getparent(), (
                    "Segments are not of the same translation unit."
                )

            segments.append(segment)
            segment_ids.append(translation_unit.index(segment))

        for segment in translation_unit[min(segment_ids) : max(segment_ids) + 1]:
            if etree.QName(segment).localname == "segment" and segment not in segments:
                raise ValueError("Segments are not consecutive.")

        segments = translation_unit[min(segment_ids) : max(segment_ids) + 1]
        first_source = segments[0][0]
        first_target = segments[0][1]

        for segment in segments[1:]:
            segment_source = segment[0]
            transfer_children(segment_source, first_source)

            if etree.QName(segment).localname == "segment":
                segment_target = segment[1]
            else:
                segment_target = segment[0]

            transfer_children(segment_target, first_target)

            translation_unit.remove(segment)

    @classmethod
    def new(cls, source_file, src, trgt, segmentation="default"):
        """
        Takes in a source file and returns a KXLIFF instance.

        Args:
            source_file: Path to a source file.
            src: ISO 639-1 code for the source language.
            trgt: ISO 639-1 code for the target language.
            segmentation: Sets whether kaplan should split translation units
                          into sentences. This should be either set to False or
                          left as is for .po files where segments are
                          already translated.
        """

        source_file_path = Path(source_file)

        name = source_file_path.name

        if name.lower().endswith((".kxliff", ".sdlxliff", ".xliff")):
            raise TypeError(
                "This function cannot handle .xliff variants. "
                "Call either kaplan.open_bilingual_file, "
                "kaplan.kxliff.KXLIFF.open_bilingual_file, "
                "kaplan.xliff.XLIFF.open_bilingual_file, or "
                "kaplan.sdlxliff.SDLXLIFF.open_bilingual_file instead."
            )

        _segment_counter = 1
        _tu_counter = 1

        xml_root = etree.Element(
            "{{{0}}}xliff".format(nsmap["xliff"]),
            attrib={"version": "2.1", "srcLang": src, "trgLang": trgt},
            nsmap={None: nsmap["xliff"], "kaplan": nsmap["kaplan"]},
        )

        source_file_reference = etree.SubElement(
            xml_root, "{{{0}}}file".format(nsmap["xliff"])
        )
        source_file_reference.attrib["id"] = "1"
        source_file_reference.attrib["original"] = str(source_file_path)

        _tu_template = etree.Element("{{{0}}}unit".format(nsmap["xliff"]))
        _segment = etree.SubElement(
            _tu_template, "{{{0}}}segment".format(nsmap["xliff"])
        )
        etree.SubElement(_segment, "{{{0}}}source".format(nsmap["xliff"]))
        etree.SubElement(_segment, "{{{0}}}target".format(nsmap["xliff"]))

        _placeholder_template = etree.Element(
            "{{{0}}}placeholder".format(nsmap["kaplan"])
        )

        if name.lower().endswith(
            (".docx", ".odp", ".ods", ".odt", ".po", ".json", ".txt")
        ):
            source_suffix = Path(source_file_path).suffix.lower().strip().lstrip(r"\.")

            parser = source_to_parser_map[SourceTypeEnum(source_suffix)](nsmap)
            internal_files, translation_units = parser.parse(
                source_file_path, segmentation=segmentation
            )

            if internal_files is not None:
                if isinstance(internal_files, list):
                    source_file_reference.extend(internal_files)
                else:
                    source_file_reference.insert(0, internal_files)

            source_file_reference.extend(translation_units)

            if source_suffix == "po" and segmentation == "default":
                segmentation = False

        if not segmentation:
            for tu in source_file_reference.findall("xliff:unit", nsmap):
                segment = tu.find("xliff:segment", nsmap)
                if segment is not None:
                    segment.attrib["id"] = tu.attrib["id"]
            return cls(name + ".kxliff", xml_root)

        _regex = (
            regex.compile(
                r"(\s+|^)"
                r"(\p{Lu}\p{L}{0,3})"
                r"(\.+)"
                r"(\s+|$)"
            ),
            regex.compile(
                r"(\s+|^)"
                r"([\p{Lu}\p{L}]+)"
                r"([\.\!\?\:]+)"
                r"(\s+|$)"
            ),
        )

        for segment in source_file_reference.findall(".//xliff:segment", nsmap):
            source = segment.find("xliff:source", nsmap)
            source_text = ""

            source_text += source.text if source.text is not None else ""
            for child in source:
                source_text += child.tail if child.tail is not None else ""

            if len(source_text.split()) <= 1:
                continue

            placeholders = [
                "placeholder_to_keep_segment_going",
                "placeholder_to_end_segment",
            ]
            while placeholders[0] in source_text:
                placeholders[0] += random.choice(string.ascii_letters)
            while placeholders[1] in source_text:
                placeholders[1] += random.choice(string.ascii_letters)

            for hit in regex.findall(_regex[0], source_text):
                if hit is not None:
                    source_text = regex.sub(
                        regex.escape("".join(hit)),
                        "".join((hit[0], hit[1], hit[2], placeholders[0], hit[3])),
                        source_text,
                        1,
                    )

            for hit in regex.findall(_regex[1], source_text):
                if hit is not None and hit[-1] != "":
                    source_text = regex.sub(
                        regex.escape("".join(hit)),
                        "".join((hit[0], hit[1], hit[2], placeholders[1], hit[3])),
                        source_text,
                        1,
                    )

            source_text = regex.sub(placeholders[0], "", source_text)
            len_sentences = []
            for sentence in source_text.split(placeholders[1]):
                if sentence is not None and sentence != "":
                    len_sentences.append(len(sentence))

            new_segments = etree.Element("{{{0}}}segments".format(nsmap["xliff"]))
            new_segment = etree.SubElement(
                new_segments, "{{{0}}}segment".format(nsmap["xliff"])
            )
            new_source = etree.SubElement(
                new_segment, "{{{0}}}source".format(nsmap["xliff"])
            )
            if not name.lower().endswith(".po"):
                etree.SubElement(new_segment, "{{{0}}}target".format(nsmap["xliff"]))
            else:
                new_segment.append(segment.find("xliff:target", nsmap))

            def create_segments(
                text_element,
                len_sentences,
                new_segment,
                new_source,
                new_segments=new_segments,
            ):
                while text_element is not None and len(text_element) > 0:
                    if len(text_element) >= len_sentences[0]:
                        if len(new_source) == 0:
                            if new_source.text is None:
                                new_source.text = ""
                            new_source.text += text_element[: len_sentences[0]]
                        else:
                            if new_source[-1].tail is None:
                                new_source[-1].tail = ""
                            new_source[-1].tail += text_element[: len_sentences[0]]
                        text_element = text_element[len_sentences[0] :]

                        len_sentences = len_sentences[1:]
                        new_segment = etree.SubElement(
                            new_segments, "{{{0}}}segment".format(nsmap["xliff"])
                        )
                        new_source = etree.SubElement(
                            new_segment, "{{{0}}}source".format(nsmap["xliff"])
                        )
                        etree.SubElement(
                            new_segment, "{{{0}}}target".format(nsmap["xliff"])
                        )
                    else:
                        if len(new_source) == 0:
                            if new_source.text is None:
                                new_source.text = ""
                            new_source.text += text_element
                        else:
                            if new_source[-1].tail is None:
                                new_source[-1].tail = ""
                            new_source[-1].tail += text_element

                        len_sentences[0] -= len(text_element)
                        text_element = None

                return len_sentences, new_segment, new_source

            source_text = source.text
            if source_text is not None:
                source.text = None
                len_sentences, new_segment, new_source = create_segments(
                    source_text, len_sentences, new_segment, new_source
                )

            for child in source:
                child_tail = child.tail
                new_source.append(child)
                if child.tail is not None:
                    child.tail = None
                    len_sentences, new_segment, new_source = create_segments(
                        child_tail, len_sentences, new_segment, new_source
                    )

            if (
                len(new_source) == 1
                and etree.QName(new_source[0]).localname == "ec"
                and new_source.text is None
            ):
                new_child = new_source[0]
                new_segment.getprevious().find("xliff:source", nsmap).append(new_child)
                if new_child.tail:
                    new_source.text = new_child.tail
                else:
                    new_segments.remove(new_segment)

            segment_parent = segment.getparent()
            segment_i = segment_parent.index(segment)
            segment_parent.remove(segment)

            for new_segment in new_segments:
                segment_parent.insert(segment_i, new_segment)
                segment_i += 1

        def set_up_ignorable(segment, prev_or_next):
            ignorable_sibling = (
                segment.getprevious() if prev_or_next == "prev" else segment.getnext()
            )
            if (
                ignorable_sibling is None
                or etree.QName(ignorable_sibling).localname != "ignorable"
            ):
                segment_parent = segment.getparent()
                ignorable_i = segment_parent.index(segment)
                if prev_or_next == "next":
                    ignorable_i += 1

                ignorable_sibling = etree.Element(
                    "{{{0}}}ignorable".format(nsmap["xliff"])
                )
                etree.SubElement(
                    ignorable_sibling, "{{{0}}}source".format(nsmap["xliff"])
                )
                segment_parent.insert(ignorable_i, ignorable_sibling)

            return ignorable_sibling

        segment_counter = 1

        for segment in source_file_reference.findall(".//xliff:segment", nsmap):
            source = segment.find("xliff:source", nsmap)

            for ec in source.findall("xliff:ec", nsmap):
                if (
                    (ec.tail is not None and ec.tail != "")
                    or ec.attrib.get("dataRef") is None
                    or ec.getnext() is None
                ):
                    continue
                next_sibling = ec.getnext()

                if (
                    next_sibling.tag.split("}")[-1] == "sc"
                    and next_sibling.attrib.get("dataRef") is not None
                    and ec.attrib["dataRef"] == next_sibling.attrib["dataRef"]
                ):
                    if next_sibling.tail is not None and next_sibling.tail != "":
                        prev_sibling = ec.getprevious()
                        if prev_sibling is not None:
                            if prev_sibling.tail is None:
                                prev_sibling.tail = ""
                            prev_sibling.tail += next_sibling.tail
                        else:
                            if source.text is None:
                                source.text = ""
                            source.text += next_sibling.tail
                    source.remove(ec)
                    source.remove(next_sibling)

            prev_ignorable = None
            prev_ignorable_complete = False

            while not prev_ignorable_complete:
                if source.text is not None:
                    lstripped_source_text = source.text.lstrip()
                    if lstripped_source_text != source.text:
                        if lstripped_source_text != "":
                            text_to_ignore = source.text[: -len(lstripped_source_text)]
                            source.text = lstripped_source_text
                            prev_ignorable_complete = True
                        else:
                            text_to_ignore = source.text
                            source.text = None
                        if prev_ignorable is None:
                            prev_ignorable = set_up_ignorable(segment, "prev")
                        if len(prev_ignorable[0]) > 0:
                            if prev_ignorable[0][-1].tail is None:
                                prev_ignorable[0][-1].tail = text_to_ignore
                            else:
                                prev_ignorable[0][-1].tail += text_to_ignore
                        elif prev_ignorable[0].text is None:
                            prev_ignorable[0].text = text_to_ignore
                        else:
                            prev_ignorable[0].text += text_to_ignore
                    else:
                        prev_ignorable_complete = True
                elif len(source) == 1 and source[0].tail is None:
                    if prev_ignorable is not None:
                        prev_ignorable[0].append(source[0])
                        segment.getparent().remove(segment)

                    segment.tag = "{{{0}}}ignorable".format(nsmap["xliff"])
                    prev_ignorable_complete = True

                elif len(source) > 0:
                    first_child = source[0]
                    first_child_localname = etree.QName(first_child).localname
                    if first_child_localname == "ec":
                        pass
                    elif first_child_localname == "sc":
                        ph_pairs = source.xpath("xliff:sc|xliff:ec", namespaces=nsmap)
                        if len(ph_pairs) == 1 or (
                            len(ph_pairs) == 2
                            and source[-1].tail is None
                            and ph_pairs[1] == source[-1]
                        ):
                            pass
                        else:
                            prev_ignorable_complete = True
                    else:
                        if "&lt;tab" not in first_child.attrib.get(
                            "equiv", ""
                        ) and "&lt;br" not in first_child.attrib.get("equiv", ""):
                            prev_ignorable_complete = True

                    if not prev_ignorable_complete:
                        if prev_ignorable is None:
                            prev_ignorable = set_up_ignorable(segment, "prev")
                        source.text = first_child.tail
                        first_child.tail = None
                        prev_ignorable[0].append(first_child)
                else:
                    segment.getparent().remove(segment)
                    prev_ignorable_complete = True

            if (
                etree.QName(segment).localname == "ignorable"
                or segment.getparent() is None
            ):
                continue

            next_ignorable = None
            next_ignorable_complete = False

            while not next_ignorable_complete:
                if len(source) > 0 and source[-1].tail is not None:
                    last_child = source[-1]
                    rstripped_last_child_tail = last_child.tail.rstrip()
                    if rstripped_last_child_tail != last_child.tail:
                        if rstripped_last_child_tail != "":
                            text_to_ignore = last_child.tail[
                                len(rstripped_last_child_tail) :
                            ]
                            last_child.tail = rstripped_last_child_tail
                            next_ignorable_complete = True
                        else:
                            text_to_ignore = last_child.tail
                            last_child.tail = None

                        if next_ignorable is None:
                            next_ignorable = set_up_ignorable(segment, "next")

                        if next_ignorable[0].text is None:
                            next_ignorable[0].text = text_to_ignore
                        else:
                            next_ignorable[0].text = (
                                text_to_ignore + next_ignorable[0].text
                            )

                    else:
                        next_ignorable_complete = True
                elif len(source) > 0:
                    last_child = source[-1]
                    last_child_localname = etree.QName(last_child).localname
                    if last_child_localname == "sc":
                        pass
                    elif (
                        last_child_localname == "ec"
                        and len(source.xpath("xliff:sc|xliff:ec", namespaces=nsmap))
                        == 1
                    ):
                        pass
                    elif last_child_localname == "ph" and last_child.attrib.get(
                        "equiv", ""
                    ).startswith(("&lt;br", "&lt;tab")):
                        pass
                    else:
                        next_ignorable_complete = True

                    if not next_ignorable_complete:
                        if next_ignorable is None:
                            next_ignorable = set_up_ignorable(segment, "next")
                        next_ignorable[0].insert(0, last_child)
                        last_child.tail = next_ignorable[0].text
                        next_ignorable[0].text = None
                elif source.text is not None:
                    rstripped_source_text = source.text.rstrip()
                    if rstripped_source_text != source.text:
                        if rstripped_source_text != "":
                            text_to_ignore = source.text[len(rstripped_source_text) :]
                            source.text = rstripped_source_text
                            next_ignorable_complete = True
                        else:
                            text_to_ignore = source.text
                            source.text = None

                        if next_ignorable is None:
                            next_ignorable = set_up_ignorable(segment, "next")

                        if next_ignorable[0].text is None:
                            next_ignorable[0].text = text_to_ignore
                        else:
                            next_ignorable[0].text = (
                                text_to_ignore + next_ignorable[0].text
                            )

                    else:
                        next_ignorable_complete = True
                else:
                    segment.getparent().remove(segment)
                    next_ignorable_complete = True

            for sc_child in source.findall("xliff:sc", nsmap):
                next_sibling = sc_child.getnext()
                if (
                    sc_child.tail is None
                    and next_sibling is not None
                    and etree.QName(next_sibling).localname == "ec"
                    and sc_child.attrib["id"] == next_sibling.attrib["id"]
                ):
                    source.remove(sc_child)
                    if next_sibling.tail is not None:
                        target_child = next_sibling.getprevious()
                        if target_child is not None:
                            if target_child.tail is None:
                                target_child.tail = next_sibling.tail
                            else:
                                target_child.tail += next_sibling.tail
                        else:
                            if source.text is None:
                                source.text = next_sibling.tail
                            else:
                                source.text += next_sibling.tail
                    source.remove(next_sibling)

            segment.attrib["id"] = str(segment_counter)
            segment_counter += 1

        return cls(name + ".kxliff", xml_root)

    def resolve_comment(self, segment_i, comment_i, author):
        """
        Marks a comment resolved.
        """
        comment = self.xml_root.xpath(
            './/xliff:note[@segment="{0}" and @id="{1}"]'.format(segment_i, comment_i),
            namespaces=nsmap,
        )
        if comment != []:
            comment = comment[0]
            comment.attrib["resolved_at"] = datetime.utcnow().isoformat()
            comment.attrib["resolved_by"] = author
            comment.attrib["state"] = "resolved"
        else:
            raise ValueError("Comment not found.")

    def resolve_loc_quality_issue(self, segment_i, issue_i, author):
        """
        Marks a localization quality issue (LQI) resolved.

        Args:
            segment_i: Segment ID
            issue_i: LQI ID
            author: Username or name of the individual resolving the LQI
        """
        loc_quality_issue = self.xml_root.xpath(
            './/kaplan:locQualityIssue[@segment="{0}" and @id="{1}"]'.format(
                segment_i, issue_i
            ),
            namespaces=nsmap,
        )
        if loc_quality_issue != []:
            loc_quality_issue = loc_quality_issue[0]
            if loc_quality_issue.attrib.get("resolved"):
                raise ValueError("LQI already resolved.")
            loc_quality_issue.attrib["resolved_at"] = datetime.utcnow().isoformat()
            loc_quality_issue.attrib["resolved_by"] = author
            loc_quality_issue.attrib["resolved"] = "true"
        else:
            raise ValueError("LQI not found.")

    def update_segment(
        self,
        target_segment,
        tu_i,
        segment_i,
        segment_state=None,
        submitted_by=None,
        save_history=True,
    ):
        """
        Updates a target segment.
        """
        if save_history and (
            segment_state == "translated" or segment_state == "reviewed"
        ):
            tu = self.xml_root.xpath(
                './/xliff:unit[@id="{0}"]|unit[@id="{0}"]'.format(tu_i),
                namespaces=nsmap,
            )[0]
            segment = tu.find(
                'xliff:segment[@id="{0}"]'.format(segment_i), namespaces=nsmap
            )
            target = segment.find("xliff:target", namespaces=nsmap)
            if target is not None and (len(target) > 0 or target.text is not None):
                tu_history = tu.find("kaplan:history", namespaces=nsmap)
                if tu_history is None:
                    tu_history = etree.SubElement(
                        tu, "{{{0}}}history".format(nsmap["kaplan"])
                    )
                segment_history = tu_history.find(
                    'kaplan:segment[@id="{0}"]'.format(segment_i), namespaces=nsmap
                )
                if segment_history is None:
                    segment_history = etree.SubElement(
                        tu_history,
                        "{{{0}}}segment".format(nsmap["kaplan"]),
                        {"id": str(segment_i)},
                    )
                if len(segment_history) == 0 or etree.tostring(
                    segment_history[-1], encoding="UTF-8"
                ) != etree.tostring(target, encoding="UTF-8"):
                    copy_target = deepcopy(target)
                    copy_target.attrib["state"] = segment.attrib.get("state", "N/A")
                    copy_target.attrib["modified_on"] = segment.attrib.get(
                        "modified_on", "N/A"
                    )
                    copy_target.attrib["modified_by"] = segment.attrib.get(
                        "modified_by", "N/A"
                    )

                    segment_history.append(copy_target)

        super().update_segment(
            target_segment, tu_i, segment_i, segment_state, submitted_by
        )
