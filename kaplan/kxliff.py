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

kxliff_version = '0.0.1'


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
        self.translation_units = []
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
            source_file_no = source_files.index(source_file) + 1
            translation_units = source_file.findall('.//trans-unit', self.nsmap)
            for translation_unit in translation_units:
                translation_unit_no = translation_units.index(translation_unit) + 1
                self.translation_units.append({
                    'source_file_no': source_file_no,
                    'segments': []
                })
                tu_seg_source = translation_unit.find('seg-source', self.nsmap)
                tu_target = translation_unit.find('target', self.nsmap)
                if tu_seg_source is not None:
                    for source_segment in tu_seg_source.findall('.//mrk[@mtype="seg"]', self.nsmap):
                        _segment = etree.Element('segment')
                        etree.SubElement(_segment, 'source')
                        etree.SubElement(_segment, 'target')
                        extract_segment(source_segment, _segment[0])
                        segment_no = _segment.attrib['no'] = source_segment.attrib['mid']
                        target_segment = tu_target.find('.//mrk[@mid="{0}"]'.format(segment_no), self.nsmap)
                        if target_segment is not None:
                            extract_segment(target_segment, _segment[1])
                            if self.xliff_variant == 'kaplan':
                                _segment.attrib['state'] = target_segment.attrib['state']
                            elif self.xliff_variant == 'sdl':
                                _segment.attrib['state'] = translation_unit.find('sdl:seg-defs/sdl:seg[@id="{0}"]'.format(segment_no), self.nsmap).attrib['conf'].lower()

                        self.translation_units[-1]['segments'].append(_segment)

                else:
                    pass

    @classmethod
    def new(cls, *args):
        '''
        Takes in a source file and returns a KXLIFF instance.

        Args:
            args[0]: Either the path to a source file or a source file as a BytesIO
                     instance. The BytesIO instance must have its name attribute
                     set to the name of the file.
            args[1] (optional): An output directory to save the returned kxliff file.
        '''

        pass

    def save(self, output_directory):
        self.xml_root.getroottree().write(os.path.join(output_directory, self.name),
                                          encoding='UTF-8',
                                          xml_declaration=True)

    def update_segment(self, segment_state, target_segment, tu_no, segment_no):
        '''
        Updates a given segment.

        Args:
            segment_state (str): The state of the segment (ie. translated, signed-off, etc.).
            target_segment (str): Target segment in HTML.
            tu_no (str or int): Index no of the translation unit.
            segment_no (str or int): ID of the segment.
        '''

        translation_unit = self.xml_root.findall('.//trans-unit', self.nsmap)[tu_no]
        target = translation_unit.find('target', self.nsmap)
        if translation_unit.find('seg-source', self.nsmap) is not None:
            target.find('mrk[@mid="{0}"]'.format(segment_no), self.nsmap).text = target_segment
        else:
            target.text = target_segment
