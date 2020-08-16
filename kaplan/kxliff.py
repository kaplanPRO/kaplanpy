# Installed libraries
from lxml import etree
import regex

# Standard Python libraries
import html
from io import BytesIO
import os
from zipfile import ZipFile

# Internal Python files
from .utils import get_current_time_in_utc, nsmap


class KXLIFF:
    '''
    A slightly modified version of the XML Localisation File Format http://docs.oasis-open.org/xliff/v1.2/os/xliff-core.html).

    Class KXLIFF offers native support for .xliff and .sdlxliff files.

    Args:
        args[0]: Either the path to a kxliff file or a kxliff file as a BytesIO instance.
    '''

    def __init__(self, *args):
        self.name = os.path.basename(args[0]) if type(args[0]) == str else args[0].name
        self.nsmap = {}
        self.translation_units = etree.Element('translation-units')
        self.xliff_variant = ''
        self.xml_root = etree.parse(args[0]).getroot()

        self.nsmap = self.xml_root.nsmap

        if self.name.lower().endswith('.kxliff'):
            self.xliff_variant = 'kaplan'
        elif self.name.lower().endswith('.sdlxliff'):
            self.xliff_variant = 'sdl'
        elif self.name.lower().endswith('.xliff'):
            self.xliff_variant = 'vanilla'
        else:
            raise ValueError('File is incompatible!')

        source_files = self.xml_root.findall('file', self.nsmap)

        def extract_segment(source_or_target, segment):
            if source_or_target.text is not None:
                if len(segment) > 0:
                    if segment[-1].tail is None:
                        segment[-1].tail = ''
                    segment[-1].tail += source_or_target.text
                else:
                    if segment.text is None:
                        segment.text = ''
                    segment.text += source_or_target.text
            for subsegment in source_or_target:
                if subsegment.tag == '{{{0}}}g'.format(self.nsmap[None]):
                    segment.append(etree.fromstring('<g id="{0}" type="start">{0}</g>'.format(subsegment.attrib['id'])))
                    extract_segment(subsegment, segment)
                    segment.append(etree.fromstring('<g id="{0}" type="end">{0}</g>'.format(subsegment.attrib['id'])))
                else:
                    segment.append(etree.fromstring('<{0} id="{1}" type="full">placeholder-{1}</{0}>'.format(subsegment.tag.split('}')[-1],
                                                                                                             subsegment.attrib['id'])))
                if subsegment.tail is not None:
                    if len(segment) > 0:
                        if segment[-1].tail is None:
                            segment[-1].tail = ''
                        segment[-1].tail += subsegment.text
                    else:
                        if segment.text is None:
                            segment.text = ''
                        segment.text += subsegment.text

        for source_file in source_files:
            source_file_no = str(source_files.index(source_file) + 1)
            translation_units = source_file.findall('.//trans-unit', self.nsmap)
            for translation_unit in translation_units:
                _trans_unit = etree.Element('trans-unit')
                _trans_unit.attrib['file-id'] = source_file_no
                _trans_unit.attrib['id'] = translation_unit.attrib['id']

                tu_seg_source = translation_unit.find('seg-source', self.nsmap)
                tu_target = translation_unit.find('target', self.nsmap)
                if tu_seg_source is not None:
                    for source_segment in tu_seg_source.findall('.//mrk[@mtype="seg"]', self.nsmap):
                        _segment = etree.Element('segment')
                        etree.SubElement(_segment, 'source')
                        etree.SubElement(_segment, 'target')
                        segment_no = _segment.attrib['no'] = source_segment.attrib['mid']
                        extract_segment(source_segment, _segment[0])

                        target_segment = tu_target.find('.//mrk[@mid="{0}"]'.format(segment_no), self.nsmap) if tu_target is not None else None
                        if target_segment is not None:
                            extract_segment(target_segment, _segment[1])
                            if self.xliff_variant == 'kaplan':
                                _segment.attrib['state'] = target_segment.attrib['state']
                            elif self.xliff_variant == 'sdl':
                                _segment.attrib['state'] = translation_unit.find('sdl:seg-defs/sdl:seg[@id="{0}"]'.format(segment_no), self.nsmap).attrib['conf'].lower()

                        _trans_unit.append(_segment)

                else:
                    _segment = etree.Element('segment')
                    etree.SubElement(_segment, 'source')
                    etree.SubElement(_segment, 'target')
                    extract_segment(translation_unit.find('source', self.nsmap), _segment[0])

                    target_segment = translation_unit.find('target', self.nsmap)
                    if target_segment is not None:
                        extract_segment(target_segment, _segment[1])

                    _trans_unit.append(_segment)

                self.translation_units.append(_trans_unit)

    def generate_target_translations(self, target_directory, source_file=None):
        '''
        Generates a "clean" target file.

        Args:
            target_directory: Path to target directory where the target file will be saved.
            source_file (optional): Path to source file (Required for file types such as .docx, .odt, etc.).

        '''
        source_filename = self.xml_root.findall('file', self.nsmap)[0].attrib['original']

        if source_filename.lower().endswith('.txt'):
            with open(os.path.join(target_directory, source_filename), 'w') as outfile:
                for trans_unit in self.xml_root.find('.//body', self.nsmap):
                    if trans_unit[2].text is not None:
                        outfile.write(trans_unit[2].text)

                    for segment in trans_unit[2]:
                        if segment.text is not None:
                            outfile.write(segment.text)
                        else:
                            outfile.write(trans_unit[1].find('mrk[@mid="{0}"]'.format(segment.attrib['mid']), self.nsmap).text)

                        outfile.write(segment.tail)

        else:
            raise ValueError('Filetype incompatible for this task!')

    @classmethod
    def new(cls, source_file, source_language):
        '''
        Takes in a source file and returns a KXLIFF instance.

        Args:
            source_file: Path to a source file.
            source_language: ISO 639-1 code of the source language.
        '''

        name = os.path.basename(source_file)

        if name.lower().endswith(('.kxliff', '.sdlxliff', '.xliff')):
            return cls(source_file)

        _segment_counter = 1
        _tu_counter = 1

        xml_root = etree.Element('{{{0}}}xliff'.format(nsmap[None]), nsmap=nsmap)

        _tu_template = etree.Element('{{{0}}}trans-unit'.format(nsmap[None]))
        etree.SubElement(_tu_template, '{{{0}}}source'.format(nsmap[None]))
        _tu_template[0].text = ''
        etree.SubElement(_tu_template, '{{{0}}}seg-source'.format(nsmap[None]))
        _tu_template[1].text = ''
        etree.SubElement(_tu_template, '{{{0}}}target'.format(nsmap[None]))

        if name.lower().endswith('.txt'):

            etree.SubElement(xml_root, '{{{0}}}file'.format(nsmap[None]))
            xml_root[-1].attrib['source_language'] = source_language
            xml_root[-1].attrib['original'] = source_file
            translation_units = etree.SubElement(xml_root[-1], '{{{0}}}body'.format(nsmap[None]))

            xml_root[0]
            with open(source_file, encoding='UTF-8') as source_file:
                _tu = _tu_template.__copy__()
                _tu.attrib['id'] = str(_tu_counter)
                translation_units.append(_tu)
                _tu_counter += 1
                for line in source_file:
                    line = line.strip()

                    if line == '':
                        if len(_tu[1]) == 0:
                            _tu[1].text += line + '\n'
                            _tu[2].text += line + '\n'
                        else:
                            _tu[1][0].tail += line + '\n'
                            _tu[2][0].tail += line + '\n'

                    else:
                        _source = etree.Element('{{{0}}}mrk'.format(nsmap[None]))
                        _source.attrib['mtype'] = 'seg'
                        _source.attrib['mid'] = str(_segment_counter)
                        _source.text = line
                        _source.tail = '\n'

                        _target = etree.Element('{{{0}}}mrk'.format(nsmap[None]))
                        _target.attrib['mtype'] = 'seg'
                        _target.attrib['mid'] = str(_segment_counter)
                        _target.attrib['state'] = 'blank'

                        _segment_counter += 1

                        if len(_tu[1]) == 1:
                            _tu = _tu_template.__copy__()
                            _tu.attrib['id'] = str(_tu_counter)
                            translation_units.append(_tu)
                            _tu_counter += 1

                        _tu[1].append(_source)
                        _tu[1][0].tail = '\n'
                        _tu[2].append(_target)
                        _tu[2][0].tail = '\n'

                    _tu[0].text += line + '\n'

        kxliff = BytesIO(etree.tostring(xml_root))
        kxliff.name = name + '.kxliff'

        return cls(kxliff)

    def save(self, output_directory):
        self.xml_root.getroottree().write(os.path.join(output_directory, self.name),
                                          encoding='UTF-8',
                                          xml_declaration=True)

    def update_segment(self, segment_state, target_segment, tu_no, segment_no=None):
        '''
        Updates a given segment.

        Args:
            segment_state (str): The state of the segment (ie. translated, signed-off, etc.).
            target_segment (str): Target segment in HTML.
            tu_no (str or int): The number of the translation unit .
            segment_no (str or int) (optional): The number of the segment. Segments
                                                that make up the entire tu do not have numbers.
        '''

        translation_unit = self.xml_root.findall('.//trans-unit', self.nsmap)[int(tu_no) - 1]
        target = translation_unit.find('target', self.nsmap)
        _trans_unit = self.translation_units.find('trans-unit[@no="{0}"]'.format(tu_no))
        if translation_unit.find('seg-source', self.nsmap) is not None:
            if segment_no is None:
                raise ValueError('Parameter "segment_no" is missing.')
            target = target.find('mrk[@mid="{0}"]'.format(segment_no), self.nsmap)
            _target = _trans_unit.find('segment[@no="{0}"]'.format(segment_no))[1]
        else:
            _target = _trans_unit[0][1]

        target.text = ''
        for child in target:
            target.remove(child)
        target.text = target_segment

        _target.clear()
        _target.text = target_segment
