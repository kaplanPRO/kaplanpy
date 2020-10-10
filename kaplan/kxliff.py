# Installed libraries
from lxml import etree
import regex

# Standard Python libraries
from copy import deepcopy
import html
from io import BytesIO
import os
import random
import string
import zipfile

# Internal Python files
from .utils import get_current_time_in_utc, remove_dir

nsmap = {
    'kaplan': 'https://kaplan.pro',
    'xliff': 'urn:oasis:names:tc:xliff:document:2.1',
    'xml': 'http://www.w3.org/XML/1998/namespace'
}

class KXLIFF:
    '''
    A slightly modified version of the XML Localisation File Format (http://docs.oasis-open.org/xliff/xliff-core/v2.1/xliff-core-v2.1.html).

    Class KXLIFF offers native support for .xliff and .sdlxliff files.

    Args:
        bilingual_file: Either the path to a bilingual file or a bilingual file as a BytesIO instance.
        src (optional): ISO 639-1 code for the source language.
        trgt (optional): ISO 639-1 code for the target language.
    '''

    def __init__(self, bilingual_file, src=None, trgt=None):
        self.name = os.path.basename(bilingual_file) if type(bilingual_file) == str else bilingual_file.name
        self.nsmap = {}
        self.translation_units = etree.Element('translation-units')
        self.xliff_variant = ''
        self.xml_root = etree.parse(bilingual_file).getroot()

        self.xliff_version = float(self.xml_root.attrib['version'])
        self.nsmap = self.xml_root.nsmap

        if self.name.lower().endswith('.kxliff'):
            self.xliff_variant = 'kaplan'
        elif self.name.lower().endswith('.sdlxliff'):
            self.xliff_variant = 'sdl'
        elif self.name.lower().endswith('.xliff'):
            self.xliff_variant = 'vanilla'
        else:
            raise ValueError('File is incompatible!')

        if self.xliff_version >= 2.0:
            for translation_unit in self.xml_root.findall('.//unit', self.nsmap):
                _translation_unit = deepcopy(translation_unit)
                _translation_unit.tag = 'translation-unit'
                for _child in _translation_unit:
                    if not _child.tag.endswith(('}segment', '}ignorable')):
                        _translation_unit.remove(_child)
                for _any_child in _translation_unit.findall('.//'):
                    if 'equiv' in _any_child.attrib:
                        _any_child.text = html.unescape(_any_child.attrib['equiv'])

                self.translation_units.append(_translation_unit)
        else:
            for translation_unit in self.xml_root.findall('.//trans-unit', self.nsmap):
                segments = []
                _g_counter = {}
                _translation_unit = etree.Element('translation-unit', translation_unit.attrib)
                if translation_unit.find('seg-source', self.nsmap) is not None:
                    for source_segment in translation_unit.findall('seg-source//mrk', self.nsmap):
                        target_segment = translation_unit.find('target//mrk[@mid="{0}"]'.format(source_segment.attrib['mid']), self.nsmap)

                        segments.append([source_segment, target_segment])

                else:
                    segments.append([translation_unit.find('source', self.nsmap), translation_unit.find('target', self.nsmap)])

                for segment in segments:
                    _segment = etree.SubElement(_translation_unit, 'segment', {'id': segment[0].attrib.get('mid', 'N/A')})

                    _source = deepcopy(segment[0])
                    _source.tag = 'source'
                    _source.tail = None

                    if segment[1] is not None:
                        _target = deepcopy(segment[1])
                    else:
                        _target = etree.Element('mrk', _source.attrib)
                    _target.tag = 'target'
                    _target.tail = None

                    _segment.append(_source)
                    _segment.append(_target)

                    for _child in _segment:
                        for _any_child in _child.findall('.//'):

                            if _any_child.tag.startswith('b'):
                                _any_child.text = '<{0}-{1}>'.format(etree.QName(_any_child).localname[1:], _any_child.attrib.get('id', 'N/A'))
                            elif _any_child.tag.startswith('e'):
                                _any_child.text = '</{0}-{1}>'.format(etree.QName(_any_child).localname[1:], _any_child.attrib.get('id', 'N/A'))
                            elif _any_child.tag.endswith('g'):
                                if _any_child.attrib['id'] not in _g_counter:
                                    _g_counter[_any_child.attrib['id']] = str(len(_g_counter) + 1)
                                _b_g_tag = etree.Element('g', _any_child.attrib)
                                _b_g_tag.attrib['no'] = _g_counter[_any_child.attrib['id']]
                                _e_g_tag = deepcopy(_b_g_tag)

                                _b_g_tag.text = '<g-{0}>'.format(_g_counter[_any_child.attrib['id']])
                                _e_g_tag.text = '</g-{0}>'.format(_g_counter[_any_child.attrib['id']])

                                _parent = _any_child.getparent()
                                _parent.replace(_any_child, _b_g_tag)
                                _b_g_tag.tail = _any_child.text
                                next_i = _parent.index(_b_g_tag) + 1
                                for _g_child in _any_child:
                                    _parent.insert(next_i, _g_child)
                                    next_i += 1
                                _parent.insert(next_i, _e_g_tag)
                                _e_g_tag.tail = _any_child.tail
                            else:
                                _any_child.text = '<{0}-{1}/>'.format(etree.QName(_any_child).localname, _any_child.attrib.get('id', 'N/A'))

                self.translation_units.append(_translation_unit)

    @staticmethod
    def can_process(source_file):
        '''
        Static method that determines whether the source_file is compatible.

        Args:
            source_file: Path to a source file.
        '''
        if source_file.lower().endswith(('.docx', '.kxliff', '.odp', '.ods', '.odt', '.po', '.sdlxliff', '.txt', '.xliff')):
            return True
        else:
            return False

    def generate_target_translation(self, output_directory, path_to_source_file=None):
        '''
        Generates a "clean" target file.

        Args:
            output_directory: Path to target directory where the target file will be saved.
            source_file (optional): Path to source file (Required for file types such as .docx, .odt, etc.).

        '''
        if not self.name.endswith('.kxliff'):
            raise TypeError('Function only available for .kxliff files.')

        source_file = self.xml_root.find('file', self.nsmap)
        source_filename = os.path.basename(source_file.attrib['original'])

        if source_filename.lower().endswith('.docx'):
            source_nsmap = source_file[0][0].nsmap
            target_units = etree.Element('target-units')

            for trans_unit in source_file.findall('.//unit', self.nsmap):
                target_unit = etree.SubElement(target_units, 'target-unit', trans_unit.attrib)

                original_data = trans_unit.find('originalData', self.nsmap)
                active_tags = []

                last_parent = None
                last_run = None

                for segment in trans_unit.xpath('.//xliff:segment|.//xliff:ignorable', namespaces={'xliff':self.nsmap[None]}):
                    target = segment.find('target', self.nsmap)
                    if target is None or (target.text is None and len(target) == 0):
                        target = segment.find('source', self.nsmap)

                    if target.text is not None:
                        if last_parent is None:
                            last_parent = last_run = etree.SubElement(target_unit, '{{{0}}}r'.format(source_nsmap['w']))
                        elif last_run is None:
                            last_run = etree.SubElement(last_parent, '{{{0}}}r'.format(source_nsmap['w']))


                        w_t = etree.SubElement(last_run, '{{{0}}}t'.format(source_nsmap['w']))
                        if target.text != target.text.strip():
                            w_t.attrib['{{{0}}}space'.format(nsmap['xml'])] = 'preserve'
                        w_t.text = target.text

                    for target_child in target:
                        target_child_localname = etree.QName(target_child).localname
                        if target_child_localname == 'sc':
                            active_tags.append((target_child.attrib['id'], target_child.attrib['dataRef']))

                            new_element = etree.fromstring(original_data.find('data[@id="{0}"]'.format(active_tags[0][1]), self.nsmap).text)
                            new_element_localname = etree.QName(new_element).localname

                            if len(active_tags) == 1:
                                target_unit.append(new_element)
                                last_parent = new_element
                                if new_element_localname == 'hyperlink' and len(last_parent) == 1:
                                    last_run = last_parent[0]
                                elif new_element_localname == 'hyperlink' and len(last_parent) == 0:
                                    last_run = None
                                else:
                                    last_run = last_parent
                            else:
                                if new_element_localname == 'r':
                                    if last_parent != last_run:
                                        last_parent.append(new_element)
                                        last_run = new_element

                        elif target_child_localname == 'ec':
                            for active_tag in active_tags:
                                if active_tag[0] == target_child.attrib['id']:
                                    removed_element = etree.fromstring(original_data.find('data[@id="{0}"]'.format(active_tag[1]), self.nsmap).text)
                                    if removed_element.tag == last_parent.tag:
                                        last_parent = None
                                    if removed_element.tag == last_run.tag:
                                        last_run = None
                                    active_tags.remove(active_tag)
                                    break
                            if len(active_tags) > 0:
                                if last_parent is None:
                                    new_element = etree.fromstring(original_data.find('data[@id="{0}"]'.format(active_tags[0][1]), self.nsmap).text)
                                    new_element_localname = etree.QName(new_element).localname

                                    target_unit.append(new_element)
                                    last_parent = new_element
                                    if new_element_localname == 'hyperlink' and len(last_parent) == 1:
                                        last_run = last_parent[0]
                                    elif new_element_localname == 'hyperlink' and len(last_parent) == 0:
                                        last_run = None
                                    else:
                                        last_run = last_parent

                                elif last_run is None:
                                    if len(active_tags) > 1:
                                        for active_tag in active_tags[1:]:
                                            new_element = etree.fromstring(original_data.find('data[@id="{0}"]'.format(active_tag[1]), self.nsmap).text)
                                            new_element_localname = etree.QName(new_element).localname

                                            if new_element_localname == 'r':
                                                last_parent.append(new_element)
                                                last_run = new_element

                        elif target_child_localname == 'ph':
                            new_element = etree.fromstring(original_data.find('data[@id="{0}"]'.format(target_child.attrib['dataRef']), self.nsmap).text)

                            if last_parent is None:
                                last_parent = last_run = etree.SubElement(target_unit, '{{{0}}}r'.format(source_nsmap['w']))
                            elif last_run is None:
                                last_run = etree.SubElement(last_parent, '{{{0}}}r'.format(source_nsmap['w']))

                            last_run.append(new_element)

                        if target_child.tail is not None:
                            if last_parent is None:
                                last_parent = last_run = etree.SubElement(target_unit, '{{{0}}}r'.format(source_nsmap['w']))
                            elif last_run is None:
                                last_run = etree.SubElement(last_parent, '{{{0}}}r'.format(source_nsmap['w']))

                            w_t = etree.SubElement(last_run, '{{{0}}}t'.format(source_nsmap['w']))
                            if target_child.tail != target_child.tail.strip():
                                w_t.attrib['{{{0}}}space'.format(nsmap['xml'])] = 'preserve'
                            w_t.text = target_child.tail


            for target_unit in target_units:
                placeholder = self.xml_root.find('.//kaplan:placeholder[@id="{0}"]'.format(target_unit.attrib['id']), self.nsmap)
                paragraph_parent = placeholder.getparent()
                child_i = paragraph_parent.index(placeholder)
                paragraph_parent.remove(placeholder)
                for target_child in target_unit:
                    paragraph_parent.insert(child_i, target_child)
                    child_i += 1

            temp_dir = os.path.join(output_directory, ('.temp' + source_filename))

            if os.path.exists(temp_dir):
                remove_dir(temp_dir)

            if path_to_source_file is None:
                path_to_source_file = source_file.attrib['original']

            with zipfile.ZipFile(path_to_source_file) as source_zip:
                source_zip.extractall(temp_dir)

            internal_file = self.xml_root.find('.//kaplan:internal-file', self.nsmap)
            etree.ElementTree(internal_file[0]).write(os.path.join(temp_dir, internal_file.attrib['rel']),
                                                      encoding='UTF-8',
                                                      xml_declaration=True)

            to_zip = []
            for root, dirs, files in os.walk(temp_dir):
                for file_in_transit in files:
                    to_zip.append(os.path.join(root, file_in_transit))

            with zipfile.ZipFile(os.path.join(output_directory, source_filename), 'w') as target_zip:
                for path_to_file in to_zip:
                    target_zip.write(path_to_file, path_to_file[len(temp_dir):])

            remove_dir(temp_dir)

        elif source_filename.lower().endswith(('.odp', '.ods', '.odt')):
            def add_text(last_span, text):
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

            duplicated_xml_root = deepcopy(self.xml_root)

            source_nsmap = source_file[0][0].nsmap
            target_units = etree.Element('target-units')

            for trans_unit in duplicated_xml_root.findall('.//unit', self.nsmap):
                target_unit = etree.SubElement(target_units, 'target-unit', trans_unit.attrib)

                original_data = trans_unit.find('originalData', self.nsmap)
                active_tags = []

                last_parent = target_unit
                last_span = target_unit

                for segment in trans_unit.xpath('.//xliff:segment|.//xliff:ignorable', namespaces={'xliff':self.nsmap[None]}):
                    target = segment.find('target', self.nsmap)
                    if target is None or (target.text is None and len(target) == 0):
                        target = segment.find('source', self.nsmap)

                    if target.text is not None:
                        add_text(last_span, target.text)

                    for child in target:
                        child_localname = etree.QName(child).localname

                        if child_localname == 'sc':
                            last_parent_localname = etree.QName(last_parent).localname
                            active_tags.append(child.attrib['dataRef'])
                            new_child = etree.fromstring(original_data.find('data[@id="{0}"]'.format(child.attrib['dataRef']), self.nsmap).text)
                            new_child_localname = etree.QName(new_child).localname
                            if len(active_tags) == 1:
                                new_child_span = new_child.find('text:span', source_nsmap)
                                target_unit.append(new_child)
                                if new_child_span is not None:
                                    last_parent = new_child
                                    last_span = new_child_span
                                else:
                                    last_parent = last_span = new_child

                            elif len(active_tags) == 2:
                                if last_parent_localname == 'a' and new_child_localname == 'span':
                                    last_parent.append(new_child)
                                    last_span = new_child

                        elif child_localname == 'ec':
                            last_parent_localname = etree.QName(last_parent).localname
                            if active_tags.index(child.attrib['dataRef']) == 0:
                                last_parent = target_unit
                                last_span = target_unit
                            elif active_tags.index(child.attrib['dataRef']) == 1 and last_parent_localname == 'a':
                                last_span = last_parent

                            active_tags.remove(child.attrib['dataRef'])

                            if len(active_tags) > 1:
                                new_child = etree.fromstring(original_data.find('data[@id="{0}"]'.format(active_tags[1]), self.nsmap).text)
                                new_child_localname = etree.QName(new_child).localname
                                if last_parent_localname == 'a' and new_child_localname == 'span':
                                    last_parent.append(new_child)
                                    last_span = new_child
                            elif len(active_tags) == 1:
                                if last_parent == target_unit:
                                    new_child = etree.fromstring(original_data.find('data[@id="{0}"]'.format(active_tags[0]), self.nsmap).text)
                                    new_child_span = new_child.find('text:span', source_nsmap)
                                    target_unit.append(new_child)
                                    if new_child_span is not None:
                                        last_parent = new_child
                                        last_span = new_child_span
                                    else:
                                        last_parent = last_span = new_child
                        else:
                            last_span.append(etree.fromstring(original_data.find('data[@id="{0}"]'.format(child.attrib['dataRef']), self.nsmap).text))

                        if child.tail is not None:
                            add_text(last_span, child.tail)


                placeholder = duplicated_xml_root.find('.//kaplan:placeholder[@id="{0}"]'.format(target_unit.attrib['id']), self.nsmap)
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

            temp_dir = os.path.join(output_directory, ('.temp' + source_filename))

            if os.path.exists(temp_dir):
                remove_dir(temp_dir)

            if path_to_source_file is None:
                path_to_source_file = source_file.attrib['original']

            with zipfile.ZipFile(path_to_source_file) as source_zip:
                source_zip.extractall(temp_dir)

            internal_file = duplicated_xml_root.find('.//kaplan:internal-file', self.nsmap)
            etree.ElementTree(internal_file[0]).write(os.path.join(temp_dir, internal_file.attrib['rel']),
                                                      encoding='UTF-8',
                                                      xml_declaration=True)

            to_zip = []
            for root, dirs, files in os.walk(temp_dir):
                for file_in_transit in files:
                    to_zip.append(os.path.join(root, file_in_transit))

            with zipfile.ZipFile(os.path.join(output_directory, source_filename), 'w') as target_zip:
                for path_to_file in to_zip:
                    target_zip.write(path_to_file, path_to_file[len(temp_dir):])

        elif source_filename.lower().endswith('.po'):
            po_entries = {}

            for trans_unit in source_file.findall('.//unit', self.nsmap):
                po_id = int(trans_unit.attrib.get('rid', trans_unit.attrib['id']))
                keys = trans_unit.attrib['keys'].split(';')
                if po_id not in po_entries:
                    po_entries[po_id] = [trans_unit.attrib['metadata'], [], []]

                source_text = ''
                target_text = ''
                for segment in trans_unit.xpath('.//xliff:segment|.//xliff:ignorable', namespaces={'xliff':self.nsmap[None]}):
                    source_text += segment.find('source', self.nsmap).text
                    target = segment.find('target', self.nsmap)
                    if target is not None:
                        target_text += target.text
                else:
                    po_entries[po_id][1].append('{0} "{1}"'.format(keys[0], source_text))
                    po_entries[po_id][2].append('{0} "{1}"'.format(keys[1], target_text))

            with open(os.path.join(output_directory, source_filename), 'w') as outfile:
                outfile.write(source_file.find('kaplan:internal-file', self.nsmap).text + '\n')

                for po_entry_i in sorted(po_entries):
                    po_entry = po_entries[po_entry_i]
                    outfile.write(po_entry[0] + '\n')
                    for line in po_entry[1] + po_entry[2]:
                        outfile.write(line + '\n')
                    else:
                        outfile.write('\n')

        elif source_filename.lower().endswith('.txt'):
            with open(os.path.join(output_directory, source_filename), 'w') as outfile:
                for trans_unit in source_file.findall('.//unit', self.nsmap):
                    for segment in trans_unit.xpath('.//xliff:segment|.//xliff:ignorable', namespaces={'xliff':self.nsmap[None]}):
                        target = segment.find('target', self.nsmap)
                        if target is not None and target.text is not None:
                            outfile.write(target.text)

                        else:
                            outfile.write(segment.find('source', self.nsmap).text)

        else:
            raise ValueError('Filetype incompatible for this task!')

    @classmethod
    def new(cls, source_file, src, trgt):
        '''
        Takes in a source file and returns a KXLIFF instance.

        Args:
            source_file: Path to a source file.
            src: ISO 639-1 code for the source language.
            trgt: ISO 639-1 code for the target language.
        '''

        name = os.path.basename(source_file)

        if name.lower().endswith(('.kxliff', '.sdlxliff', '.xliff')):
            return cls(source_file)

        _segment_counter = 1
        _tu_counter = 1

        xml_root = etree.Element('{{{0}}}xliff'.format(nsmap['xliff']),
                                 attrib={'version':'2.1',
                                         'srcLang': src,
                                         'trgLang': trgt},
                                 nsmap={None:nsmap['xliff'], 'kaplan':nsmap['kaplan']})

        source_file_reference = etree.SubElement(xml_root, '{{{0}}}file'.format(nsmap['xliff']))
        source_file_reference.attrib['id'] = '1'
        source_file_reference.attrib['original'] = source_file

        _tu_template = etree.Element('{{{0}}}unit'.format(nsmap['xliff']))
        _segment = etree.SubElement(_tu_template, '{{{0}}}segment'.format(nsmap['xliff']))
        etree.SubElement(_segment, '{{{0}}}source'.format(nsmap['xliff']))
        etree.SubElement(_segment, '{{{0}}}target'.format(nsmap['xliff']))

        _placeholder_template = etree.Element('{{{0}}}placeholder'.format(nsmap['kaplan']))

        if name.lower().endswith('.docx'):

            def extract_or_pass(paragraph_child, paragraph_parent, tu, source_xml):
                def add_text(source_xml, text):
                    if len(source_xml) == 0:
                        if source_xml.text is None:
                            source_xml.text = ''
                        source_xml.text += text
                    else:
                        if source_xml[-1].tail is None:
                            source_xml[-1].tail = ''
                        source_xml[-1].tail += text

                def add_placeholder(tu, source_xml, data, tag, equiv=None, standalone=True, equiv_with_no=False):
                    original_data = tu.find('{{{0}}}originalData'.format(nsmap['xliff']))
                    if original_data is None:
                        original_data = etree.Element('{{{0}}}originalData'.format(nsmap['xliff']))
                        tu.insert(0, original_data)

                    tag = '{{{0}}}{1}'.format(nsmap['xliff'], tag)

                    _data = etree.SubElement(original_data, '{{{0}}}data'.format(nsmap['xliff']))
                    _data_id = str(len(original_data))
                    _data.attrib['id'] = _data_id
                    _data.text = etree.tostring(data, encoding='UTF-8')

                    _tag = etree.SubElement(source_xml, tag)
                    _tag_id = str(len(source_xml.findall(tag)))
                    _tag.attrib['id'] = _tag_id
                    _tag.attrib['dataRef'] = _data_id

                    if equiv is None:
                        equiv = data.tag.split('}')[-1]
                    if equiv_with_no:
                        equiv = '<{0}-{1}{2}>'.format(equiv, _tag_id, '/' if standalone else '')
                    else:
                        equiv = '<{0}{1}>'.format(data.tag.split('}')[-1], '/' if standalone else '')

                    _tag.attrib['equiv'] = html.escape(equiv)

                    return _tag_id

                def add_ending_tag(tu, source_xml, tag, equiv, starting_tag_i):
                    tag = '{{{0}}}{1}'.format(nsmap['xliff'], tag)

                    _tag = etree.SubElement(source_xml, tag, {'id': starting_tag_i})
                    _tag.attrib['equiv'] = html.escape('</{0}-{1}>'.format(equiv, starting_tag_i))

                if paragraph_child.tag.endswith('}r'):
                    run_properties = paragraph_child.find('w:rPr', source_nsmap)
                    if run_properties is not None and len(run_properties) > 0:
                        run_w_properties = etree.Element('{{{0}}}r'.format(source_nsmap['w']), paragraph_child.getparent().attrib)
                        run_w_properties.append(run_properties)

                        _tag_i = add_placeholder(tu, source_xml, run_w_properties, 'sc', 'tag', False, True)

                    for paragraph_grandchild in paragraph_child:
                        extract_or_pass(paragraph_grandchild,
                                        paragraph_child,
                                        tu,
                                        source_xml)

                    if run_properties is not None and len(run_properties) > 0:
                        add_ending_tag(tu, source_xml, 'ec', 'tag', _tag_i)

                elif paragraph_child.tag.endswith('}hyperlink'):
                    hyperlink = etree.Element('{{{0}}}hyperlink'.format(source_nsmap['w']), paragraph_child.attrib)

                    run_properties = paragraph_child[0].find('w:rPr', source_nsmap)
                    if len(paragraph_child) == 1:
                        if run_properties is not None and len(run_properties) > 0:
                            run_w_properties = etree.SubElement(hyperlink,
                                                                '{{{0}}}r'.format(source_nsmap['w']),
                                                                paragraph_child[0].attrib)
                            run_w_properties.append(run_properties)
                            paragraph_child = paragraph_child[0]

                    _tag_i = add_placeholder(tu, source_xml, hyperlink, 'sc', 'link', False, True)

                    for paragraph_grandchild in paragraph_child:
                        extract_or_pass(paragraph_grandchild,
                                        paragraph_child,
                                        tu,
                                        source_xml)

                    add_ending_tag(tu, source_xml, 'ec', 'link', _tag_i)

                elif paragraph_child.tag.endswith('}t'):
                    add_text(source_xml, paragraph_child.text)

                elif paragraph_child.tag.endswith('}tab'):
                    add_placeholder(tu, source_xml, paragraph_child, 'ph')

                elif paragraph_child.tag.endswith('}br'):
                    add_placeholder(tu, source_xml, paragraph_child, 'ph')

                elif paragraph_child.tag.endswith('}drawing'):
                    add_placeholder(tu, source_xml, paragraph_child, 'ph', True, True)

            with zipfile.ZipFile(source_file) as source_zip:
                source_file_content = etree.parse(source_zip.open('word/document.xml')).getroot()

            source_nsmap = source_file_content.nsmap
            internal_file = etree.Element('{{{0}}}internal-file'.format(nsmap['kaplan']), {'rel': 'word/document.xml'})
            internal_file.append(source_file_content)
            source_file_reference.insert(0, internal_file)

            for paragraph_element in source_file_content.xpath('w:body/w:p|w:body/w:tbl/w:tr/w:tc//w:p', namespaces={'w':source_nsmap['w']}):
                if paragraph_element.find('.//w:t', source_nsmap) is None:
                    continue
                placeholder_placed = False
                _tu = deepcopy(_tu_template)
                _tu.attrib['id'] = str(_tu_counter)
                _tu_counter += 1
                source_file_reference.append(_tu)
                _source = _tu[0][0]
                for paragraph_child in paragraph_element:
                    if paragraph_child.tag.endswith('}pPr'):
                        continue
                    textbox_paragraphs = paragraph_child.findall('.//w:p', source_nsmap) # TODO: Fix repeating TUs of text box content for mc:Choice and mc:Fallback.
                    if len(textbox_paragraphs) > 0:
                        for textbox_paragraph in textbox_paragraphs:
                            if textbox_paragraph.find('.//w:t', source_nsmap) is None:
                                continue
                            placeholder_placed = False
                            if len(_source) >= 0 or _source.text is not None:
                                _tu = deepcopy(_tu_template)
                                _tu.attrib['id'] = str(_tu_counter)
                                _tu_counter += 1
                                source_file_reference.append(_tu)
                                _source = _tu[0][0]

                            for textbox_child in textbox_paragraph:
                                if textbox_child.tag.endswith('}pPr'):
                                    continue
                                if not placeholder_placed:
                                    _placeholder = deepcopy(_placeholder_template)
                                    _placeholder.attrib['id'] = _tu.attrib['id']
                                    textbox_paragraph.insert(textbox_paragraph.index(textbox_child),
                                                             _placeholder)
                                    placeholder_placed = True
                                extract_or_pass(textbox_child,
                                                textbox_paragraph,
                                                _tu,
                                                _source)
                                textbox_paragraph.remove(textbox_child)
                        else:
                            _tu = deepcopy(_tu_template)
                            _tu.attrib['id'] = str(_tu_counter)
                            _tu_counter += 1
                            source_file_reference.append(_tu)
                            _source = _tu[0][0]
                            continue
                    if not placeholder_placed:
                        _placeholder = deepcopy(_placeholder_template)
                        _placeholder.attrib['id'] = _tu.attrib['id']
                        paragraph_element.insert(paragraph_element.index(paragraph_child),
                                                 _placeholder)
                        placeholder_placed = True
                    extract_or_pass(paragraph_child,
                                    paragraph_element,
                                    _tu,
                                    _source)
                    paragraph_element.remove(paragraph_child)

        elif name.lower().endswith(('.odp', '.ods', '.odt')):
            def extract_or_pass(current_element, parent, tu, source_xml):
                def add_text(source_xml, text):
                    if len(source_xml) == 0:
                        if source_xml.text is None:
                            source_xml.text = ''
                        source_xml.text += text
                    else:
                        if source_xml[-1].tail is None:
                            source_xml[-1].tail = ''
                        source_xml[-1].tail += text

                def add_placeholder(tu, source_xml, data, tag, equiv=None, standalone=True, equiv_with_no=False, data_id=None):
                    original_data = tu.find('{{{0}}}originalData'.format(nsmap['xliff']))
                    if original_data is None:
                        original_data = etree.Element('{{{0}}}originalData'.format(nsmap['xliff']))
                        tu.insert(0, original_data)

                    tag = '{{{0}}}{1}'.format(nsmap['xliff'], tag)

                    _data = original_data.find('xliff:data[@id="{0}"]'.format(data_id), nsmap)
                    if _data is None:
                        _data = etree.SubElement(original_data, '{{{0}}}data'.format(nsmap['xliff']))
                        _data_id = data_id if data_id is not None else str(len(original_data))
                        _data.attrib['id'] = _data_id
                        _data.text = etree.tostring(data, encoding='UTF-8')
                    else:
                        _data_id = _data.attrib['id']

                    _tag = etree.SubElement(source_xml, tag)
                    _tag_id = str(len(source_xml.findall(tag)))
                    _tag.attrib['id'] = _tag_id
                    _tag.attrib['dataRef'] = _data_id

                    if equiv is None:
                        equiv = data.tag.split('}')[-1]
                        if equiv_with_no:
                            equiv = '<{0}-{1}{2}>'.format(equiv, _tag_id, '/' if standalone else '')
                        else:
                            equiv = '<{0}{1}>'.format(data.tag.split('}')[-1], '/' if standalone else '')

                    _tag.attrib['equiv'] = html.escape(equiv)

                    return _tag_id, _data_id

                def add_ending_tag(tu, source_xml, tag, equiv, starting_tag_i, data_id):
                    tag = '{{{0}}}{1}'.format(nsmap['xliff'], tag)

                    tag_attrib = {'id': starting_tag_i,
                                  'dataRef': data_id,
                                  'equiv': html.escape(equiv)}
                    tag = etree.SubElement(source_xml, tag, tag_attrib)

                if current_element.text is not None:
                    add_text(source_xml, current_element.text)

                    current_element.text = None

                for child in current_element:
                    child_localname = etree.QName(child).localname

                    if child_localname == 'span':
                        child_copy = etree.Element(child.tag, child.attrib)
                        style_name = child.attrib['{{{0}}}style-name'.format(source_nsmap['text'])]

                        tag_id, data_id = add_placeholder(tu, source_xml, child_copy, 'sc', '<{0}>'.format(style_name), False, False, style_name)

                        extract_or_pass(child,
                                        current_element,
                                        tu,
                                        source_xml)

                        add_ending_tag(tu, source_xml, 'ec', '</{0}>'.format(style_name), tag_id, data_id)

                    elif child_localname == 'a':
                        child_copy = etree.Element(child.tag, child.attrib)
                        etree.tostring(child)
                        if len(child) == 1 and child[0].tail is None and child.text is None:

                            tag_id, data_id = add_placeholder(tu, source_xml, child_copy, 'sc', None, False, True)

                            add_text(source_xml, child[0].text)

                            add_ending_tag(tu, source_xml, 'ec', '</a-{0}>'.format(data_id), tag_id, data_id)

                        else:
                            tag_id, data_id = add_placeholder(tu, source_xml, child_copy, 'sc', None, False, True)

                            extract_or_pass(child,
                                            current_element,
                                            tu,
                                            source_xml)

                            add_ending_tag(tu, source_xml, 'ec', '</a-{0}>'.format(data_id), tag_id, data_id)

                    elif child_localname == 'frame' and child.find('draw:text-box', source_nsmap) is None:
                        add_placeholder(tu, source_xml, child, 'ph', None, True, True)

                    elif child_localname == 'line-break':
                        add_placeholder(tu, source_xml, etree.Element(child.tag), 'ph', '<line-break/>')

                    if child.tail is not None:
                        add_text(source_xml, child.tail)

                        child.tail = None

            source_nsmap = None

            with zipfile.ZipFile(source_file) as source_zip:
                for zip_child in source_zip.namelist():
                    if zip_child.lower().endswith('content.xml'):
                        internal_file = etree.Element('{{{0}}}internal-file'.format(nsmap['kaplan']), {'rel': zip_child})
                        internal_file.append(etree.parse(source_zip.open(zip_child)).getroot())
                        source_file_reference.append(internal_file)

            source_nsmap = source_file_reference.find('kaplan:internal-file[@rel="content.xml"]', nsmap)[0].nsmap

            for paragraph in source_file_reference.findall('.//text:p', source_nsmap):
                if (paragraph.text is None
                and (len(paragraph) == 0
                or (min(child.text is None for child in paragraph) and min(child.tail is None for child in paragraph)))):
                    continue
                _tu = deepcopy(_tu_template)
                _tu.attrib['id'] = str(_tu_counter)
                source_file_reference.append(_tu)
                _tu_counter += 1

                _source = _tu[0][0]

                extract_or_pass(paragraph, None, _tu, _source)

                placeholder = deepcopy(_placeholder_template)
                placeholder.attrib['id'] = _tu.attrib['id']

                paragraph.text = None
                for child in paragraph:
                    if child.find('draw:text-box', source_nsmap) is None:
                        paragraph.remove(child)
                    else:
                        child.tail = None

                paragraph.append(placeholder)

        elif name.lower().endswith('.po'):

            def entry_checkpoint(entry, entry_metadata, entries):
                if entry.get('msgid', None) is not None:
                    entry['metadata'] = '\n'.join(entry_metadata)
                    entries.append(entry)

                return entries

            entries = []

            regex_compile = regex.compile('([a-z0-9\[\]]+)?\s?"(.*?)"$')

            with open(source_file, encoding='UTF-8') as po_file:
                entry = {}
                entry_metadata = []
                last_element = ''

                for line in po_file:
                    line = line.strip()

                    if line.startswith('#'):
                        entry_metadata.append(line)
                        continue

                    if line == '':
                        entries = entry_checkpoint(entry, entry_metadata, entries)
                        entry, entry_metadata, last_element = {}, [], ''
                        continue

                    regex_match = regex_compile.search(line)

                    if regex_match == None:
                        continue

                    if regex_match.group(1):
                        last_element = regex_match.group(1)
                        entry[last_element] = ''

                    if regex_match.group(2):
                        entry[last_element] += regex_match.group(2)
                else:
                    entries = entry_checkpoint(entry, entry_metadata, entries)

            po_metadata = '{0}\nmsgid ""\nmsgstr ""\n{1}\n'.format(entries[0]['metadata'],
                                                                     '\n'.join('"' + line + '\\n"' for line in entries[0]['msgstr'].split('\\n') if line))

            source_file_content = etree.Element('{{{0}}}internal-file'.format(nsmap['kaplan']), nsmap={None:nsmap['kaplan']})
            source_file_content.attrib['{{{0}}}rel'.format(nsmap['kaplan'])] = 'self'
            source_file_content.text = po_metadata
            source_file_reference.insert(0, source_file_content)

            entries = entries[1:]

            for entry in entries:
                _tu = deepcopy(_tu_template)
                _tu.attrib['id'] = str(_tu_counter)
                _tu.attrib['metadata'] = entry.get('metadata', '')
                source_file_reference.append(_tu)
                _tu_counter += 1
                _source = _tu.find('.//xliff:source', nsmap)
                _target = _tu.find('.//xliff:target', nsmap)
                _source.text = entry['msgid']
                _target_key = 'msgstr' if 'msgstr' in entry else 'msgstr[0]'
                _target.text = entry[_target_key]

                _tu.attrib['keys'] = ';'.join(('msgid', _target_key))

                if 'msgid_plural' in entry or 'plural' in entry:
                    _tu.attrib['rid'] = _tu.attrib['id']
                    _source_key = 'msgid_plural' if 'msgid_plural' in entry else 'plural'
                    _tu = deepcopy(_tu)
                    _tu.attrib['id'] = str(_tu_counter)
                    source_file_reference.append(_tu)
                    _tu_counter += 1
                    _source = _tu.find('.//xliff:source', nsmap)
                    _target = _tu.find('.//xliff:target', nsmap)
                    _source.text = entry[_source_key]
                    _target.text = entry.get('msgstr[1]', '')

                    _tu.attrib['keys'] = ';'.join((_source_key, 'msgstr[1]'))

        elif name.lower().endswith('.txt'):

            with open(source_file, encoding='UTF-8') as source_file:
                for line in source_file:
                    _tu = deepcopy(_tu_template)
                    _tu.attrib['id'] = str(_tu_counter)
                    source_file_reference.append(_tu)
                    _tu_counter += 1
                    _source = _tu.find('.//xliff:source', nsmap)
                    _target = _tu.find('.//xliff:target', nsmap)

                    if line.strip() == '':
                        _tu[0].tag = '{{{0}}}ignorable'.format(nsmap['xliff'])
                        _tu[0].remove(_target)

                    _source.text = line

        _regex = (regex.compile(r'(\s+|^)'
                                r'(\p{Lu}\p{L}{0,3})'
                                r'(\.+)'
                                r'(\s+|$)'),
                  regex.compile(r'(\s+|^)'
                                r'([\p{Lu}\p{L}]+)'
                                r'([\.\!\?\:]+)'
                                r'(\s+|$)'))

        for segment in source_file_reference.findall('.//xliff:segment', nsmap):

            source = segment.find('xliff:source', nsmap)
            source_text = ''

            source_text += source.text if source.text is not None else ''
            for child in source:
                source_text += child.tail if child.tail is not None else ''

            if len(source_text.split()) <= 1:
                continue

            placeholders = ['placeholder_to_keep_segment_going',
                            'placeholder_to_end_segment']
            while placeholders[0] in source_text:
                placeholders[0] += random.choice(string.ascii_letters)
            while placeholders[1] in source_text:
                placeholders[1] += random.choice(string.ascii_letters)

            for hit in regex.findall(_regex[0], source_text):
                if hit is not None:
                    source_text = regex.sub(regex.escape(''.join(hit)),
                                            ''.join((hit[0],
                                                     hit[1],
                                                     hit[2],
                                                     placeholders[0],
                                                     hit[3])),
                                            source_text,
                                            1)

            for hit in regex.findall(_regex[1], source_text):
                if hit is not None:
                    source_text = regex.sub(regex.escape(''.join(hit)),
                                            ''.join((hit[0],
                                                     hit[1],
                                                     hit[2],
                                                     placeholders[1],
                                                     hit[3])),
                                            source_text,
                                            1)

            source_text = regex.sub(placeholders[0], '', source_text)
            len_sentences = []
            for sentence in source_text.split(placeholders[1]):
                if sentence is not None and sentence != '':
                    len_sentences.append(len(sentence))

            new_segments = etree.Element('{{{0}}}segments'.format(nsmap['xliff']))
            new_segment = etree.SubElement(new_segments, '{{{0}}}segment'.format(nsmap['xliff']))
            new_source = etree.SubElement(new_segment, '{{{0}}}source'.format(nsmap['xliff']))
            etree.SubElement(new_segment, '{{{0}}}target'.format(nsmap['xliff']))

            def create_segments(text_element, len_sentences, new_segment, new_source, new_segments=new_segments):
                while text_element is not None and len(text_element) > 0:
                    if len(text_element) >= len_sentences[0]:

                        if len(new_source) == 0:
                            if new_source.text is None:
                                new_source.text = ''
                            new_source.text += text_element[:len_sentences[0]]
                        else:
                            if new_source[-1].tail is None:
                                new_source[-1].tail = ''
                            new_source[-1].tail += text_element[:len_sentences[0]]
                        text_element = text_element[len_sentences[0]:]

                        len_sentences = len_sentences[1:]
                        new_segment = etree.SubElement(new_segments, '{{{0}}}segment'.format(nsmap['xliff']))
                        new_source = etree.SubElement(new_segment, '{{{0}}}source'.format(nsmap['xliff']))
                        etree.SubElement(new_segment, '{{{0}}}target'.format(nsmap['xliff']))
                    else:
                        if len(new_source) == 0:
                            if new_source.text is None:
                                new_source.text = ''
                            new_source.text += text_element
                        else:
                            if new_source[-1].tail is None:
                                new_source[-1].tail = ''
                            new_source[-1].tail += text_element

                        len_sentences[0] -= len(text_element)
                        text_element = None

                return len_sentences, new_segment, new_source

            source_text = source.text
            if source_text is not None:
                source.text = None
                len_sentences, new_segment, new_source = create_segments(source_text,
                                                                         len_sentences,
                                                                         new_segment,
                                                                         new_source)

            for child in source:
                child_tail = child.tail
                new_source.append(child)
                if child.tail is not None:
                    child.tail = None
                    len_sentences, new_segment, new_source = create_segments(child_tail,
                                                                             len_sentences,
                                                                             new_segment,
                                                                             new_source)

            if len(new_source) == 1 and etree.QName(new_source[0]).localname == 'ec' and new_source.text is None:
                new_child = new_source[0]
                new_segment.getprevious().find('xliff:source', nsmap).append(new_child)
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
            ignorable_sibling = segment.getprevious() if prev_or_next == 'prev' else segment.getnext()
            if ignorable_sibling is None or etree.QName(ignorable_sibling).localname != 'ignorable':
                segment_parent = segment.getparent()
                ignorable_i = segment_parent.index(segment)
                if prev_or_next == 'next':
                    ignorable_i += 1

                ignorable_sibling = etree.Element('{{{0}}}ignorable'.format(nsmap['xliff']))
                etree.SubElement(ignorable_sibling, '{{{0}}}source'.format(nsmap['xliff']))
                segment_parent.insert(ignorable_i, ignorable_sibling)

            return ignorable_sibling

        segment_counter = 1

        for segment in source_file_reference.findall('.//xliff:segment', nsmap):

            source = segment.find('xliff:source', nsmap)

            prev_ignorable = None
            prev_ignorable_complete = False

            while not prev_ignorable_complete:
                if source.text is not None:
                    lstripped_source_text = source.text.lstrip()
                    if lstripped_source_text != source.text:
                        if lstripped_source_text != '':
                            text_to_ignore = source.text[:-len(lstripped_source_text)]
                            source.text = lstripped_source_text
                            prev_ignorable_complete = True
                        else:
                            text_to_ignore = source.text
                            source.text = None
                        if prev_ignorable is None:
                            prev_ignorable = set_up_ignorable(segment, 'prev')
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

                    segment.tag = '{{{0}}}ignorable'.format(nsmap['xliff'])
                    prev_ignorable_complete = True

                elif len(source) > 0:
                    first_child = source[0]
                    first_child_localname = etree.QName(first_child).localname
                    if first_child_localname == 'ec':
                        pass
                    elif first_child_localname == 'sc':
                        ph_pairs = source.xpath('xliff:sc|xliff:ec', namespaces=nsmap)
                        if (len(ph_pairs) == 1 or (len(ph_pairs) == 2
                        and source[-1].tail is None and ph_pairs[1] == source[-1])):
                            pass
                        else:
                            prev_ignorable_complete = True
                    else:
                        if '&lt;tab' not in first_child.attrib.get('equiv', '') and '&lt;br' not in first_child.attrib.get('equiv', ''):
                            prev_ignorable_complete = True

                    if not prev_ignorable_complete:
                        if prev_ignorable is None:
                            prev_ignorable = set_up_ignorable(segment, 'prev')
                        source.text = first_child.tail
                        first_child.tail = None
                        prev_ignorable[0].append(first_child)
                else:
                    segment.getparent().remove(segment)
                    prev_ignorable_complete = True

            if etree.QName(segment).localname == 'ignorable' or segment.getparent() is None:
                continue

            next_ignorable = None
            next_ignorable_complete = False

            while not next_ignorable_complete:
                if len(source) > 0 and source[-1].tail is not None:
                    last_child = source[-1]
                    rstripped_last_child_tail = last_child.tail.rstrip()
                    if rstripped_last_child_tail != last_child.tail:
                        if rstripped_last_child_tail != '':
                            text_to_ignore = last_child.tail[len(rstripped_last_child_tail):]
                            last_child.tail = rstripped_last_child_tail
                            next_ignorable_complete = True
                        else:
                            text_to_ignore = last_child.tail
                            last_child.tail = None

                        if next_ignorable is None:
                            next_ignorable = set_up_ignorable(segment, 'next')

                        if next_ignorable[0].text is None:
                            next_ignorable[0].text = text_to_ignore
                        else:
                            next_ignorable[0].text = text_to_ignore + next_ignorable[0].text

                    else:
                        next_ignorable_complete = True
                elif len(source) > 0:
                    last_child = source[-1]
                    last_child_localname = etree.QName(last_child).localname
                    if last_child_localname == 'sc':
                        pass
                    elif last_child_localname == 'ec' and len(source.xpath('xliff:sc|xliff:ec', namespaces=nsmap)) == 1:
                        pass
                    elif last_child_localname == 'ph' and last_child.attrib.get('equiv', '').startswith(('&lt;br', '&lt;tab')):
                        pass
                    else:
                        next_ignorable_complete = True

                    if not next_ignorable_complete:
                        if next_ignorable is None:
                            next_ignorable = set_up_ignorable(segment, 'next')
                        next_ignorable[0].insert(0, last_child)
                        last_child.tail = next_ignorable[0].text
                        next_ignorable[0].text = None
                elif source.text is not None:
                    rstripped_source_text = source.text.rstrip()
                    if rstripped_source_text != source.text:
                        if rstripped_source_text != '':
                            text_to_ignore = source.text[len(rstripped_source_text):]
                            source.text = rstripped_source_text
                            next_ignorable_complete = True
                        else:
                            text_to_ignore = source.text
                            source.text = None

                        if next_ignorable is None:
                            next_ignorable = set_up_ignorable(segment, 'next')

                        if next_ignorable[0].text is None:
                            next_ignorable[0].text = text_to_ignore
                        else:
                            next_ignorable[0].text = text_to_ignore + next_ignorable[0].text

                    else:
                        next_ignorable_complete = True
                else:
                    segment.getparent().remove(segment)
                    next_ignorable_complete = True

            for sc_child in source.findall('xliff:sc', nsmap):
                next_sibling = sc_child.getnext()
                if (sc_child.tail is None and next_sibling is not None
                and etree.QName(next_sibling).localname == 'ec'
                and sc_child.attrib['id'] == next_sibling.attrib['id']):
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

            segment.attrib['id'] = str(segment_counter)
            segment_counter += 1

        kxliff = BytesIO(etree.tostring(xml_root, encoding='UTF-8'))
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

        target_segment = etree.fromstring(target_segment)

        assert etree.QName(target_segment).localname == 'target'

        for any_child in target_segment:
            if 'dataref' in any_child.attrib:
                any_child.attrib['dataRef'] = any_child.attrib.pop('dataref')

            any_child.attrib.pop('contenteditable', None)

        if self.xliff_version < 2.0:
            active_g_tags = []
            for any_child in target_segment:
                if any_child.tag.endswith('g'):
                    if any_child.tail is not None:
                        if len(active_g_tags) > 0:
                            active_g_tag = active_g_tags[0]
                            if len(active_g_tag) > 0:
                                if active_g_tag[-1].tail is None:
                                    active_g_tag[-1].tail = ''
                                active_g_tag[-1].tail += any_child.tail
                            else:
                                if active_g_tag.text is None:
                                    active_g_tag.text = ''
                                active_g_tag.text += any_child.tail

                            if any_child.text.startswith('</'):
                                for g_tag in active_g_tags:
                                    if g_tag.attrib['id'] == any_child.attrib['id']:
                                        active_g_tags.remove(g_tag)
                                        if len(active_g_tags) > 0:
                                            target_segment.replace(any_child, active_g_tags[0])
                                        else:
                                            target_segment.remove(any_child)
                                        break
                            else:
                                any_child.text = None
                                any_child.tail = None
                                active_g_tags.append(any_child)
                                target_segment.remove(any_child)

                        else:
                            if any_child.text.startswith('</'):
                                preceding_sibling = any_child.getprevious()
                                if preceding_sibling is not None:
                                    if target_segment.text is None:
                                        target_segment.text = ''
                                    target_segment.text += any_child.tail
                                else:
                                    if preceding_sibling.tail is None:
                                        preceding_sibling.tail = ''
                                    preceding_sibling.tail += any_child.tail
                                target_segment.remove(any_child)
                            else:
                                any_child.text = any_child.tail
                                any_child.tail = None
                                active_g_tags.append(any_child)

                    else:
                        if any_child.text.startswith('</'):
                            for g_tag in active_g_tags:
                                if g_tag.attrib['id'] == any_child.attrib['id']:
                                    active_g_tags.remove(g_tag)
                                    if len(active_g_tags) > 0:
                                        target_segment.replace(any_child, active_g_tags[0])
                                    else:
                                        target_segment.remove(any_child)
                                    break
                        else:
                            any_child.text = None
                            if len(active_g_tags) > 0:
                                target_segment.remove(any_child)
                            active_g_tags.append(any_child)

                else:
                    any_child.text = None
                    if len(active_g_tags) > 0:
                        active_g_tags[0].append(any_child)

        else:
            target_segment.tag = '{{{0}}}target'.format(self.nsmap[None])
            for child in target_segment:
                child.tag = '{{{0}}}{1}'.format(self.nsmap[None], etree.QName(child).localname)

        _target_segment = deepcopy(target_segment)

        translation_unit = self.translation_units.find('translation-unit[@id="{0}"]'.format(tu_no))

        if segment_no is not None:
            segment = translation_unit.find('segment[@id="{0}"]'.format(segment_no), self.nsmap)
            if segment is None:
                segment = translation_unit.find('segment[@id="{0}"]'.format(segment_no))
        else:
            segment = translation_unit.findall('segment', self.nsmap)[0]
            if segment is None:
                segment = translation_unit.findall('segment')[0]

        target = segment.find('target', self.nsmap)
        if target is None:
            target = segment.find('target')
        if target is None:
            segment.append(target_segment)
        else:
            segment[segment.index(target)] = target_segment

        if self.xliff_version >= 2.0:
            _translation_unit = self.xml_root.find('.//unit[@id="{0}"]'.format(tu_no), self.nsmap)

            if segment_no is not None:
                _segment = _translation_unit.find('segment[@id="{0}"]'.format(segment_no), self.nsmap)
            else:
                _segment = _translation_unit.findall('segment', self.nsmap)[0]

            _segment.attrib['state'] = segment_state

            for any_child in _target_segment:
                any_child.text = None

            _target = _segment.find('target', self.nsmap)
            if _target is None:
                _target = _segment.find('target')
            if _target is None:
                _segment.append(_target_segment)
            else:
                _segment[_segment.index(_target)] = _target_segment

        else:
            _translation_unit = self.xml_root.find('.//trans-unit[@id="{0}"]'.format(tu_no), self.nsmap)
            _target_segment.attrib['state'] = segment_state

            if segment_no is not None:
                _segment = _translation_unit.find('target//mrk[@mid="{0}"]'.format(segment_no), self.nsmap)
                _target_segment.tag = '{{{0}}}mrk'.format(self.nsmap[None])
                _target_segment.attrib['mtype'] = 'seg'
                _target_segment.attrib['mid'] = str(segment_no)
            else:
                _segment = _translation_unit.find('target', self.nsmap)
                _target_segment.tag = '{{{0}}}target'.format(self.nsmap[None])

            _segment.getparent().replace(_segment, _target_segment)
