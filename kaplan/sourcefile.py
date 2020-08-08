from hashlib import sha256
import os, random, string, zipfile

from lxml import etree
import regex

from .utils import nsmap


class SourceFile:
    def __init__(self, file_path, list_of_abbreviations=None):
        self.file_type = ''
        self.file_name = ''
        self.hyperlinks = []
        self.images = []
        self.master_files = []
        self.miscellaneous_tags = []
        self.nsmap = None
        self.paragraphs = []
        self.sha256_hash = sha256()
        self.tags = []
        self.t_nsmap = nsmap

        buffer_size = 5 * 1048576  # 5 MB
        sf = open(file_path, 'rb')
        while True:
            data = sf.read(buffer_size)
            if data:
                self.sha256_hash.update(data)
            else:
                break
        sf.close()

        self.sha256_hash = self.sha256_hash.hexdigest()

        self.file_name = os.path.basename(file_path)

        if file_path.lower().endswith('.docx'):

            def extract_p_run(r_element, p_element, paragraph_continues):
                kaplan_run = etree.Element('{{{0}}}run'.format(self.t_nsmap['kaplan']), nsmap=self.t_nsmap)
                run_properties = r_element.find('w:rPr', self.nsmap)
                if len(r_element) == 1:
                    if (r_element[0].tag == '{{{0}}}br'.format(self.nsmap['w']) and
                        b'type="page"' in etree.tostring(r_element[0])):
                        paragraph_continues = False

                        return paragraph_continues

                    elif (not paragraph_continues and run_properties is not None):

                        return paragraph_continues

                if run_properties is not None:
                    for run_property in run_properties:
                        if ('{{{0}}}val'.format(self.nsmap['w']) in run_property.attrib
                                and run_property.attrib['{{{0}}}val'.format(self.nsmap['w'])].lower() == 'false'):
                            run_properties.remove(run_property)
                        elif run_property.tag == '{{{0}}}lang'.format(self.nsmap['w']):
                            run_properties.remove(run_property)
                        elif run_property.tag == '{{{0}}}noProof'.format(self.nsmap['w']):
                            run_properties.remove(run_property)
                    if len(run_properties) > 0:
                        run_properties = [run_properties,
                                          etree.Element('{{{0}}}rPr'.format(self.nsmap['w']), nsmap=self.nsmap)]
                        for run_property in run_properties[0]:
                            run_properties[1].append(run_property)
                        run_properties = etree.tostring(run_properties[1])
                    else:
                        run_properties = None

                for sub_r_element in r_element:
                    if sub_r_element.tag == '{{{0}}}t'.format(self.nsmap['w']):
                        if (kaplan_run.find('kaplan:text', self.t_nsmap) is not None
                           and kaplan_run[-1].tag == '{{{0}}}text'.format(self.t_nsmap['kaplan'])):
                            kaplan_run[-1].text += sub_r_element.text
                        else:
                            kaplan_run.append(etree.Element('{{{0}}}text'.format(self.t_nsmap['kaplan']),
                                                             nsmap=self.t_nsmap))
                            kaplan_run[-1].text = sub_r_element.text
                    elif sub_r_element.tag == '{{{0}}}tab'.format(self.nsmap['w']):
                        kaplan_run.append(etree.Element('{{{0}}}tab'.format(self.t_nsmap['kaplan']),
                                                         nsmap=self.t_nsmap))
                    elif sub_r_element.tag == '{{{0}}}br'.format(self.nsmap['w']):
                        if ('{{{0}}}type'.format(self.nsmap['w']) in sub_r_element.attrib
                                and sub_r_element.attrib['{{{0}}}type'.format(self.nsmap['w'])] == 'page'):
                            kaplan_run.append(etree.Element('{{{0}}}br'.format(self.t_nsmap['kaplan']),
                                                             type='page', nsmap=self.t_nsmap))
                        else:
                            kaplan_run.append(etree.Element('{{{0}}}br'.format(self.t_nsmap['kaplan']),
                                                             nsmap=self.t_nsmap))
                    elif sub_r_element.tag == '{{{0}}}drawing'.format(self.nsmap['w']):
                        self.images.append(etree.tostring(sub_r_element))
                        kaplan_run.append(etree.Element('{{{0}}}image'.format(self.t_nsmap['kaplan']),
                                                         no=str(len(self.images)),
                                                         nsmap=self.t_nsmap))
                    elif sub_r_element.tag == '{{{0}}}rPr'.format(self.nsmap['w']):
                        pass

                if paragraph_continues:
                    self.paragraphs[-1].append([kaplan_run, run_properties])
                    p_element.remove(r_element)
                else:
                    self.paragraphs.append([[kaplan_run, run_properties]])
                    p_element.replace(r_element,
                                      etree.Element('{{{0}}}paragraph'.format(self.t_nsmap['kaplan']),
                                                    no=str(len(self.paragraphs)),
                                                    nsmap=self.t_nsmap))
                    paragraph_continues = True

                return paragraph_continues

            sf = zipfile.ZipFile(file_path)
            for zip_child in sf.namelist():
                if 'word/document.xml' in zip_child:
                    self.master_files.append([zip_child, sf.open(zip_child)])
                elif 'word/document2.xml' in zip_child:
                    self.master_files.append([zip_child, sf.open(zip_child)])
            sf.close()

            assert self.master_files
            self.file_type = 'docx'

            for master_file in self.master_files:
                master_file[1] = etree.parse(master_file[1])

                master_file[1] = master_file[1].getroot()
                self.nsmap = master_file[1].nsmap

                placeholders = []
                for paragraph_element in master_file[1].findall('.//w:p', self.nsmap):
                    if paragraph_element.find('.//w:t', self.nsmap) is None:
                        placeholders.append(paragraph_element)
                        placeholder_xml = etree.Element('{{{0}}}paragraph_placeholder'.format(self.t_nsmap['kaplan']),
                                                        no=str(len(placeholders)),
                                                        nsmap=self.t_nsmap)
                        paragraph_element.getparent().replace(paragraph_element,
                                                              placeholder_xml)

                for paragraph_element in master_file[1].xpath('w:body/w:p|w:body/w:tbl/w:tr', namespaces=self.nsmap):
                    add_to_last_paragraph = False
                    for sub_element in paragraph_element:
                        if (sub_element.tag == '{{{0}}}r'.format(self.nsmap['w'])
                                and sub_element.find('{{{0}}}AlternateContent'.format(self.nsmap['mc'])) is not None):
                            add_to_last_paragraph = False
                            tb_elements = sub_element.findall('.//{{{0}}}txbxContent'.format(self.nsmap['w']))
                            if len(tb_elements) == 1 or len(tb_elements) == 2:
                                for tb_paragraph_element in tb_elements[0].findall('w:p', self.nsmap):
                                    for tb_sub_element in tb_paragraph_element:
                                        if tb_sub_element.tag == '{{{0}}}r'.format(self.nsmap['w']):
                                            add_to_last_paragraph = extract_p_run(tb_sub_element,
                                                                                  tb_paragraph_element,
                                                                                  add_to_last_paragraph)
                                        elif tb_sub_element.tag == '{{{0}}}pPr'.format(self.nsmap['w']):
                                            pass
                                        else:
                                            tb_paragraph_element.remove(tb_sub_element)
                                if len(tb_elements) == 2:
                                    tb_elements.append(etree.fromstring(etree.tostring(tb_elements[0])))
                                    tb_elements[1].getparent().replace(tb_elements[1], tb_elements[2])
                            add_to_last_paragraph = False
                        elif sub_element.tag == '{{{0}}}r'.format(self.nsmap['w']):
                            add_to_last_paragraph = extract_p_run(sub_element,
                                                                  paragraph_element,
                                                                  add_to_last_paragraph)
                        elif sub_element.tag == '{{{0}}}hyperlink'.format(self.nsmap['w']):
                            add_to_last_paragraph = extract_p_run(sub_element.find('w:r', self.nsmap),
                                                                  sub_element,
                                                                  add_to_last_paragraph)
                            self.paragraphs[-1][-1].append(etree.tostring(sub_element))
                            paragraph_element.remove(sub_element)
                        elif sub_element.tag == '{{{0}}}pPr'.format(self.nsmap['w']):
                            pass
                        elif sub_element.tag == '{{{0}}}tc'.format(self.nsmap['w']):
                            for tc_p_element in sub_element.findall('w:p', self.nsmap):
                                add_to_last_paragraph = False
                                for sub_tc_p_element in tc_p_element:
                                    if sub_tc_p_element.tag == '{{{0}}}r'.format(self.nsmap['w']):
                                        add_to_last_paragraph = extract_p_run(sub_tc_p_element,
                                                                              tc_p_element,
                                                                              add_to_last_paragraph)
                        else:
                            paragraph_element.remove(sub_element)

                for paragraph_placeholder in master_file[1].findall('.//kaplan:paragraph_placeholder', self.t_nsmap):
                    paragraph_element = placeholders[int(paragraph_placeholder.attrib['no']) - 1]
                    paragraph_placeholder.getparent().replace(paragraph_placeholder, paragraph_element)

        elif file_path.lower().endswith('.odt'):

            from .sfhelper import extract_od

            sf = zipfile.ZipFile(file_path)
            self.master_files.append(['styles.xml', sf.open('styles.xml')])
            self.master_files.append(['content.xml', sf.open('content.xml')])
            for zip_child in sf.namelist():
                if zip_child != 'content.xml' and zip_child.endswith('content.xml'):
                    self.master_files.append([zip_child, sf.open(zip_child)])
            sf.close()

            assert self.master_files
            self.file_type = 'odt'

            for master_file in self.master_files:
                master_file[1] = etree.parse(master_file[1])

                master_file[1] = master_file[1].getroot()
                self.nsmap = master_file[1].nsmap

                for paragraph_element in master_file[1].xpath('office:body/office:text/text:p|office:body/office:text/table:table//text:p|office:body/office:text/draw:frame/draw:text-box/text:p|office:body/office:text/text:list/text:list-item/text:p|office:body/office:chart//text:p|office:master-styles/style:master-page/style:header/text:p|office:master-styles/style:master-page/style:footer/text:p', namespaces=self.nsmap):
                    extract_od(self, paragraph_element, paragraph_element.getparent())

        elif file_path.lower().endswith('.ods'):

            from .sfhelper import extract_od

            sf = zipfile.ZipFile(file_path)
            self.master_files.append(['content.xml', sf.open('content.xml')])
            for zip_child in sf.namelist():
                if zip_child != 'content.xml' and zip_child.endswith('content.xml'):
                    self.master_files.append([zip_child, sf.open(zip_child)])
            sf.close()

            assert self.master_files
            self.file_type = 'ods'
            self.sheets = {}

            for master_file in self.master_files:
                master_file[1] = etree.parse(master_file[1])

                master_file[1] = master_file[1].getroot()
                self.nsmap = master_file[1].nsmap

                if master_file[0] == 'content.xml':
                    for sheet_element in master_file[1].xpath('office:body/office:spreadsheet/table:table', namespaces=self.nsmap):
                        if '{{{0}}}name'.format(self.nsmap['table']) in sheet_element.attrib:
                            self.paragraphs.append([[etree.Element('{{{0}}}run'.format(nsmap['kaplan']))]])
                            self.paragraphs[-1][-1][0].append(etree.Element('{{{0}}}text'.format(nsmap['kaplan'])))
                            self.paragraphs[-1][-1][0][-1].text = sheet_element.attrib['{{{0}}}name'.format(self.nsmap['table'])]
                            self.sheets[sheet_element.attrib['{{{0}}}name'.format(self.nsmap['table'])]] = str(len(self.paragraphs))

                            sheet_element.attrib['{{{0}}}name'.format(self.nsmap['table'])] = str(len(self.paragraphs))

                        for paragraph_element in sheet_element.xpath('table:table-row/table:table-cell/text:p|table:shapes/draw:frame/draw:text-box/text:p', namespaces=self.nsmap):
                            extract_od(self, paragraph_element, paragraph_element.getparent())
                else:
                    for paragraph_element in master_file[1].xpath('office:body/office:chart//text:p', namespaces=self.nsmap):
                        paragraph_parent = paragraph_element.getparent()
                        extract_od(self, paragraph_element, paragraph_parent)

                        for cell_reference in paragraph_parent.xpath('draw:g/svg:desc', namespaces=self.nsmap):
                            cell_reference_text = cell_reference.text
                            for sheet_reference in regex.findall(':?([^:]+?)\.', cell_reference_text):
                                if sheet_reference in self.sheets:
                                    cell_reference_text = cell_reference_text.replace(sheet_reference, '{{{0}}}'.format(self.sheets[sheet_reference]), 1)
                            else:
                                cell_reference.text = cell_reference_text

        elif file_path.lower().endswith('.odp'):

            from .sfhelper import extract_od

            sf = zipfile.ZipFile(file_path)
            self.master_files.append(['content.xml', sf.open('content.xml')])
            for zip_child in sf.namelist():
                if zip_child != 'content.xml' and zip_child.endswith('content.xml'):
                    self.master_files.append([zip_child, sf.open(zip_child)])
            sf.close()

            assert self.master_files
            self.file_type = 'ods'
            self.sheets = {}

            for master_file in self.master_files:
                master_file[1] = etree.parse(master_file[1])

                master_file[1] = master_file[1].getroot()
                self.nsmap = master_file[1].nsmap

                for paragraph_element in master_file[1].xpath('office:body//text:p', namespaces=self.nsmap):
                    paragraph_parent = paragraph_element.getparent()
                    extract_od(self, paragraph_element, paragraph_parent)

        elif file_path.lower().endswith('.txt'):

            self.file_type = 'txt'

            self.master_files.append([[]])

            with open(file_path, 'r', encoding='UTF-8') as source_file:
                for line in source_file:
                    self.master_files[0][0].append(etree.Element('{{{0}}}paragraph'.format(self.t_nsmap['kaplan']),
                                                                no=str(len(self.paragraphs)+1)))
                    line = line.strip()
                    if line != '':
                        self.paragraphs.append([[etree.Element('{{{0}}}run'.format(nsmap['kaplan']))]])
                        self.paragraphs[-1].append([etree.Element('{{{0}}}run'.format(nsmap['kaplan']))])
                        self.paragraphs[-1][-1][0].append(etree.Element('{{{0}}}text'.format(nsmap['kaplan'])))
                        self.paragraphs[-1][-1][0][-1].text = line
                    else:
                        self.paragraphs.append([])

        elif file_path.lower().endswith('.xliff'):

            self.file_type = 'xliff'

            sf = etree.parse(file_path)
            sf = sf.getroot()
            self.master_files.append([[sf]])
            self.nsmap = sf.nsmap

            for file_element in sf.findall('{{{0}}}file'.format(self.nsmap[None])):
                if file_element.attrib['datatype'] != 'plaintext':
                    continue
                for translation_unit in file_element.findall('{{{0}}}body/{{{0}}}trans-unit'.format(self.nsmap[None])):
                    if len(translation_unit[0]) > 0 or len(translation_unit[1]) > 0:
                        continue
                    segment_element = etree.Element('{{{0}}}segment'.format(self.t_nsmap['kaplan']))
                    segment_element.append(etree.Element('{{{0}}}source'.format(self.t_nsmap['kaplan'])))
                    segment_element[0].append(etree.Element('{{{0}}}text'.format(self.t_nsmap['kaplan'])))
                    segment_element[0][0].text = translation_unit.find('{{{0}}}source'.format(self.nsmap[None])).text
                    segment_element.append(etree.Element('{{{0}}}status'.format(self.t_nsmap['kaplan'])))
                    segment_element.append(etree.Element('{{{0}}}target'.format(self.t_nsmap['kaplan'])))
                    segment_element[2].append(etree.Element('{{{0}}}text'.format(self.t_nsmap['kaplan'])))
                    segment_element[2][0].text = translation_unit.find('{{{0}}}target'.format(self.nsmap[None])).text
                    self.paragraphs.append([segment_element])

                    translation_unit.attrib['{{{0}}}paragraph-no'.format(self.t_nsmap['kaplan'])] = str(len(self.paragraphs))
            else:
                return

        elif file_path.lower().endswith('.po'):
            self.file_type = 'po'

            entries = []
            regex_compile = regex.compile('([a-z0-9\[\]]+)?\s?"(.*?)"$')
            with open(file_path, 'r', encoding='UTF-8') as po_file:
                entry = {}
                entry_metadata = []
                last_element = ''

                for line in po_file:

                    line = line.strip()

                    if line.startswith('#'):
                        entry_metadata.append(line)
                        continue

                    regex_match = regex_compile.search(line)

                    if line == '':
                        if entry.get('msgid', None) is not None:
                            entry['metadata'] = '\n'.join(entry_metadata)
                            entries.append(entry)
                        entry = {}
                        entry_metadata = []
                        last_element = ''
                        continue

                    if regex_match == None:
                        continue

                    if regex_match.group(1):
                        last_element = regex_match.group(1)
                        entry[last_element] = ''

                    if regex_match.group(2):
                        entry[last_element] += regex_match.group(2)
                else:
                    if entry.get('msgid', None) is not None:
                        entries.append(entry)
                        entry['metadata'] = '\n'.join(entry_metadata)
                    entry = {}
                    entry_metadata = []
                    last_element = ''

            po_metadata = entries[0]
            entries = entries[1:]

            for entry in entries:

                self.paragraphs.append([])

                segment_element = etree.Element('{{{0}}}segment'.format(self.t_nsmap['kaplan']))
                if 'metadata' in entry:
                    segment_element.attrib['metadata'] = entry['metadata']
                segment_element.append(etree.Element('{{{0}}}source'.format(self.t_nsmap['kaplan'])))
                segment_element[0].append(etree.Element('{{{0}}}text'.format(self.t_nsmap['kaplan'])))
                segment_element[0][0].text = entry['msgid']
                segment_element.append(etree.Element('{{{0}}}status'.format(self.t_nsmap['kaplan'])))
                segment_element.append(etree.Element('{{{0}}}target'.format(self.t_nsmap['kaplan'])))
                segment_element[2].append(etree.Element('{{{0}}}text'.format(self.t_nsmap['kaplan'])))
                target_key = 'msgstr' if 'msgstr' in entry else 'msgstr[0]'
                segment_element[2][0].text = entry[target_key]
                segment_element.attrib['keys'] = ';'.join(('msgid', target_key))

                self.paragraphs[-1].append(segment_element)

                if 'msgid_plural' in entry or 'plural' in entry:

                    segment_element = etree.Element('{{{0}}}segment'.format(self.t_nsmap['kaplan']))
                    segment_element.append(etree.Element('{{{0}}}source'.format(self.t_nsmap['kaplan'])))
                    segment_element[0].append(etree.Element('{{{0}}}text'.format(self.t_nsmap['kaplan'])))
                    source_key = 'msgid_plural' if 'msgid_plural' in entry else 'plural'
                    segment_element[0][0].text = entry[source_key]
                    segment_element.append(etree.Element('{{{0}}}status'.format(self.t_nsmap['kaplan'])))
                    segment_element.append(etree.Element('{{{0}}}target'.format(self.t_nsmap['kaplan'])))
                    segment_element[2].append(etree.Element('{{{0}}}text'.format(self.t_nsmap['kaplan'])))
                    segment_element[2][0].text = entry['msgstr[1]']
                    segment_element.attrib['keys'] = ';'.join((source_key, 'msgstr[1]'))

                    self.paragraphs[-1].append(segment_element)

            po_details = '\n'.join('"' + line + '\\n"' for line in po_metadata['msgstr'].split('\\n') if line)

            po_metadata = '{0}\nmsgid: ""\nmsgstr: ""\n{1}\n'.format(po_metadata['metadata'], po_details)

            self.master_files.append(po_metadata)

            return

        # Filetype-specific processing ends here.

        kaplan_link_template = etree.Element('{{{0}}}link'.format(self.t_nsmap['kaplan']))

        for paragraph_index in range(len(self.paragraphs)):
            organised_paragraph = etree.Element('{{{0}}}OrganisedParagraph'.format(self.t_nsmap['kaplan']),
                                                nsmap=self.t_nsmap)
            for run in self.paragraphs[paragraph_index]:
                if len(run) == 2 and run[1] is not None:
                    segment_type = None
                    if type(run[1]) == list and len(run[1]) == 2:
                        segment_type = run[1][1]
                        run[1] = run[1][0]
                    if run[1] not in self.tags:
                        self.tags.append(run[1])
                    kaplan_tag_template = etree.tostring(etree.Element('{{{0}}}tag'.format(self.t_nsmap['kaplan']),
                                                                        no=str(self.tags.index(run[1])+1),
                                                                        nsmap=self.t_nsmap))

                    if segment_type is None or segment_type is 'Beginning':
                        kaplan_tag = etree.fromstring(kaplan_tag_template)
                        kaplan_tag.attrib['type'] = 'beginning'
                        organised_paragraph.append(kaplan_tag)

                    for run_element in run[0]:
                        organised_paragraph.append(run_element)

                    if segment_type is None or segment_type is 'End':
                        kaplan_tag = etree.fromstring(kaplan_tag_template)
                        kaplan_tag.attrib['type'] = 'end'
                        organised_paragraph.append(kaplan_tag)

                elif len(run) == 3:
                    if run[1] is not None:
                        if run[1] not in self.tags:
                            self.tags.append(run[1])
                        kaplan_tag_template = etree.tostring(etree.Element('{{{0}}}tag'.format(self.t_nsmap['kaplan']),
                                                                            no=str(self.tags.index(run[1])+1),
                                                                            nsmap=self.t_nsmap))

                        kaplan_tag = etree.fromstring(kaplan_tag_template)
                        kaplan_tag.attrib['type'] = 'beginning'
                        organised_paragraph.append(kaplan_tag)

                    if run[2] is not None:
                        if run[2] not in self.hyperlinks:
                            self.hyperlinks.append(run[2])
                        kaplan_link_template = etree.tostring(etree.Element('{{{0}}}link'.format(self.t_nsmap['kaplan']),
                                                                             no=str(self.hyperlinks.index(run[2])+1),
                                                                             nsmap=self.t_nsmap))

                        kaplan_link = etree.fromstring(kaplan_link_template)
                        kaplan_link.attrib['type'] = 'beginning'
                        organised_paragraph.append(kaplan_link)

                    for run_element in run[0]:
                        organised_paragraph.append(run_element)

                    if run[2] is not None:
                        kaplan_link = etree.fromstring(kaplan_link_template)
                        kaplan_link.attrib['type'] = 'end'
                        organised_paragraph.append(kaplan_link)

                    if run[1] is not None:
                        kaplan_tag = etree.fromstring(kaplan_tag_template)
                        kaplan_tag.attrib['type'] = 'end'
                        organised_paragraph.append(kaplan_tag)

                elif len(run) == 4:
                    if run[2] not in self.hyperlinks:
                            self.hyperlinks.append(run[2])

                    kaplan_link = kaplan_link_template.__deepcopy__(True)
                    kaplan_link.attrib['no'] = str(self.hyperlinks.index(run[2])+1)
                    kaplan_link.attrib['type'] = run[3]
                    organised_paragraph.append(kaplan_link)

                else:
                    for run_element in run[0]:
                        organised_paragraph.append(run_element)

            for kaplan_tag_end in organised_paragraph.findall('kaplan:tag[@type="end"]', self.t_nsmap):
                if (kaplan_tag_end.getnext() is not None
                        and kaplan_tag_end.tag == kaplan_tag_end.getnext().tag
                        and kaplan_tag_end.attrib['no'] == kaplan_tag_end.getnext().attrib['no']
                        and kaplan_tag_end.getnext().attrib['type'] == 'beginning'):
                    organised_paragraph.remove(kaplan_tag_end.getnext())
                    organised_paragraph.remove(kaplan_tag_end)

            placeholders = ['placeholder_to_keep_segment_going',
                            'placeholder_to_end_segment']
            while placeholders[0] in str(etree.tostring(organised_paragraph)):
                placeholders[0] += random.choice(string.ascii_letters)
            while placeholders[1] in str(etree.tostring(organised_paragraph)):
                placeholders[1] += random.choice(string.ascii_letters)

            _regex = regex.compile(r'(\s+|^)'
                                   r'(\p{Lu}\p{L}{0,3})'
                                   r'(\.+)'
                                   r'(\s+|$)')
            for kaplan_t in organised_paragraph.findall('kaplan:text', self.t_nsmap):
                mid_sentence_punctuation = []
                for _hit in regex.findall(_regex, kaplan_t.text):
                    if _hit is not None:
                        _hit = list(_hit)
                        mid_sentence_punctuation.append(_hit)
                for to_be_replaced in mid_sentence_punctuation:
                    kaplan_t.text = regex.sub(regex.escape(''.join(to_be_replaced)),
                                               ''.join((to_be_replaced[0],
                                                        to_be_replaced[1],
                                                        to_be_replaced[2],
                                                        placeholders[0],
                                                        to_be_replaced[3])),
                                               kaplan_t.text,
                                               1)

            if list_of_abbreviations:
                list_of_abbreviations = '|'.join(list_of_abbreviations)
                _regex = regex.compile(r'(\s+|^)({0})(\.+)(\s+|$)'.format(list_of_abbreviations))
                for kaplan_t in organised_paragraph.findall('kaplan:text', self.t_nsmap):
                    mid_sentence_punctuation = []
                    for _hit in regex.findall(_regex, kaplan_t.text):
                        if _hit is not None:
                            mid_sentence_punctuation.append(_hit)
                    for to_be_replaced in mid_sentence_punctuation:
                        kaplan_t.text = regex.sub(regex.escape(''.join(to_be_replaced)),
                                                   ''.join((to_be_replaced[0],
                                                            to_be_replaced[1],
                                                            to_be_replaced[2],
                                                            placeholders[0],
                                                            to_be_replaced[3])),
                                                   kaplan_t.text,
                                                   1)

            _regex = regex.compile(r'(\s+|^)'
                                   r'([\p{Lu}\p{L}]+)'
                                   r'([\.\!\?\:]+)'
                                   r'(\s+|$)')
            for kaplan_t in organised_paragraph.findall('kaplan:text', self.t_nsmap):
                end_sentence_punctuation = []
                for _hit in regex.findall(_regex, kaplan_t.text):
                    if _hit is not None:
                        end_sentence_punctuation.append(_hit)
                for to_be_replaced in end_sentence_punctuation:
                    kaplan_t.text = regex.sub(regex.escape(''.join(to_be_replaced)) + '(?!placeholder)',
                                               ''.join((to_be_replaced[0],
                                                        to_be_replaced[1],
                                                        to_be_replaced[2],
                                                        placeholders[1],
                                                        to_be_replaced[3])),
                                               kaplan_t.text,
                                               1)
                kaplan_t.text = regex.sub(placeholders[0],
                                           '',
                                           kaplan_t.text)

            organised_paragraph = [[], organised_paragraph]
            organised_paragraph[0].append(etree.Element('{{{0}}}source'.format(self.t_nsmap['kaplan']),
                                                        nsmap=self.t_nsmap))
            for kaplan_element in organised_paragraph[1]:
                if kaplan_element.tag == '{{{0}}}text'.format(self.t_nsmap['kaplan']):
                    if kaplan_element.text is None:
                        continue
                    _text = kaplan_element.text.split(placeholders[1])
                    for _text_i in range(len(_text)):
                        if _text_i != 0:
                            organised_paragraph[0].append(etree.Element('{{{0}}}source'.format(self.t_nsmap['kaplan']),
                                                                        nsmap=self.t_nsmap))
                            if _text[_text_i] is '':
                                continue
                        organised_paragraph[0][-1].append(etree.Element('{{{0}}}text'.format(self.t_nsmap['kaplan']),
                                                            nsmap=self.t_nsmap))
                        organised_paragraph[0][-1][-1].text = _text[_text_i]
                elif (kaplan_element.tag == '{{{0}}}br'.format(self.t_nsmap['kaplan'])
                        and 'type' in kaplan_element.attrib
                        and kaplan_element.attrib['type'] == 'page'):
                    if len(organised_paragraph[0][-1]) == 0:
                        organised_paragraph[0] = organised_paragraph[0][:-1]
                    organised_paragraph[0].append(etree.Element('{{{0}}}non-text-segment'.format(self.t_nsmap['kaplan']),
                                                                nsmap=self.t_nsmap))
                    organised_paragraph[0][-1].append(kaplan_element)
                    organised_paragraph[0].append(etree.Element('{{{0}}}source'.format(self.t_nsmap['kaplan']),
                                                nsmap=self.t_nsmap))
                elif kaplan_element.tag == '{{{0}}}br'.format(self.t_nsmap['kaplan']):
                    if (len(organised_paragraph[0][-1]) == 0
                            or (len(organised_paragraph[0][-1]) == 1
                            and organised_paragraph[0][-1][-1].tag == '{{{0}}}text'.format(self.t_nsmap['kaplan'])
                            and organised_paragraph[0][-1][-1].text is '')):
                        organised_paragraph[0] = organised_paragraph[0][:-1]
                        organised_paragraph[0].append(etree.Element('{{{0}}}non-text-segment'.format(self.t_nsmap['kaplan']),
                                                                    nsmap=self.t_nsmap))
                        organised_paragraph[0][-1].append(kaplan_element)
                        organised_paragraph[0].append(etree.Element('{{{0}}}source'.format(self.t_nsmap['kaplan']),
                                                    nsmap=self.t_nsmap))

                    else:
                        organised_paragraph[0][-1].append(kaplan_element)

                else:
                    organised_paragraph[0][-1].append(kaplan_element)
            if (len(organised_paragraph[0][-1]) == 0
                    or (len(organised_paragraph[0][-1]) == 1
                    and organised_paragraph[0][-1][-1].tag == '{{{0}}}text'.format(self.t_nsmap['kaplan'])
                    and organised_paragraph[0][-1][-1].text is '')):
                organised_paragraph[0] = organised_paragraph[0][:-1]

            for organised_segment in organised_paragraph[0]:
                if organised_segment.tag == '{{{0}}}non-text-segment'.format(self.t_nsmap['kaplan']):
                    continue
                if (len(organised_segment) == 0
                        or (len(organised_paragraph[0][-1]) == 1
                        and organised_paragraph[0][-1][-1].tag == '{{{0}}}text'.format(self.t_nsmap['kaplan'])
                        and organised_paragraph[0][-1][-1].text is '')):
                    organised_paragraph[0].remove(organised_segment)
                    continue
                if (organised_segment[0].tag == '{{{0}}}tag'.format(self.t_nsmap['kaplan'])
                and organised_segment[0].attrib['type'] == 'end'):
                    if (organised_segment.getprevious()
                    and organised_segment.getprevious().xpath('kaplan:tag[@type="beginning][@no="{0}"]'.format(organised_segment[0].attrib['no']))):
                        organised_segment.getprevious().append(organised_segment[0])
                    elif len(organised_segment) == 1:
                        organised_segment.tag = '{{{0}}}non-text-segment'.format(self.t_nsmap['kaplan'])
                        continue
                    else:
                        _segment_i = organised_paragraph[0].index(organised_segment)
                        if organised_paragraph[0][_segment_i-1].tag != '{{{0}}}non-text-segment'.format(self.t_nsmap['kaplan']):
                            organised_paragraph[0].insert(_segment_i,
                                                        etree.Element('{{{0}}}non-text-segment'.format(self.t_nsmap['kaplan']),
                                                                    nsmap=self.t_nsmap))

                        organised_paragraph[0][_segment_i].append(organised_segment[0])
                if (organised_segment[-1].tag == '{{{0}}}tag'.format(self.t_nsmap['kaplan'])
                and organised_segment[-1].attrib['type'] == 'beginning'):
                    if (organised_segment.getnext()
                    and organised_segment.getnext().xpath('kaplan:tag[@type="end"][@no="{0}"]'.format(organised_segment[0].attrib['no']), namespaces=self.t_nsmap)):
                        organised_segment.getnext().append(organised_segment[0])
                    elif len(organised_segment) == 1:
                        organised_segment.tag = '{{{0}}}non-text-segment'.format(self.t_nsmap['kaplan'])
                        continue
                    else:
                        _segment_i = organised_paragraph[0].index(organised_segment)
                        if organised_paragraph[0][_segment_i+1].tag != '{{{0}}}non-text-segment'.format(self.t_nsmap['kaplan']):
                            _segment_i += 1
                            organised_paragraph[0].insert(_segment_i,
                                                        etree.Element('{{{0}}}non-text-segment'.format(self.t_nsmap['kaplan']),
                                                                    nsmap=self.t_nsmap))

                        organised_paragraph[0][_segment_i].append(organised_segment[0])


                active_ftags = []
                no_text_yet = True
                items_to_nontext = []
                perform_move = False
                for organised_segment_child in organised_segment:
                    if organised_segment_child.tag == '{{{0}}}tag'.format(self.t_nsmap['kaplan']):
                        if organised_segment_child.attrib['type'] == 'beginning':
                            if (organised_segment.index(organised_segment_child) == 0
                            and not organised_segment.xpath('kaplan:tag[@type="end"][@no="{0}"]'.format(organised_segment_child.attrib['no']), namespaces=self.t_nsmap)):
                                if (organised_segment.getprevious()
                                and organised_segment.getprevious().tag == '{{{0}}}non-text-segment'.format(self.t_nsmap['kaplan'])):
                                    organised_segment.getprevious().append(organised_segment)
                                else:
                                    _segment_i = organised_paragraph[0].index(organised_segment)
                                    organised_paragraph[0].insert(_segment_i,
                                                                etree.Element('{{{0}}}non-text-segment'.format(self.t_nsmap['kaplan']),
                                                                            nsmap=self.t_nsmap))
                                    organised_paragraph[0][_segment_i].append(organised_segment_child)
                            else:
                                active_ftags.append(organised_segment_child.attrib['no'])
                        elif organised_segment_child.attrib['type'] == 'end':
                            if organised_segment_child.attrib['no'] in active_ftags:
                                active_ftags.remove(organised_segment_child.attrib['no'])
                            else:
                                if organised_segment.index(organised_segment_child) == len(organised_segment)-1:
                                    if (organised_segment.getnext()
                                    and organised_segment.getnext().tag == '{{{0}}}non-text-segment'.format(self.t_nsmap['kaplan'])):
                                        organised_segment.getnext().append(organised_segment_child)
                                    else:
                                        _segment_i = organised_paragraph[0].index(organised_segment) + 1
                                        organised_paragraph[0].insert(_segment_i,
                                                                    etree.Element('{{{0}}}non-text-segment'.format(self.t_nsmap['kaplan']),
                                                                                nsmap=self.t_nsmap))
                                        organised_paragraph[0][_segment_i].append(organised_segment_child)

                                else:
                                    _tag = organised_segment_child.__deepcopy__(True)
                                    _tag.attrib['type'] = 'beginning'
                                    organised_segment.insert(0, _tag)

                    if no_text_yet:
                        if organised_segment_child.tag == '{{{0}}}text'.format(self.t_nsmap['kaplan']):
                            leading_space = regex.match(r'\s+', organised_segment_child.text)
                            if leading_space:
                                leading_space = leading_space.group()
                                if leading_space == organised_segment_child.text:
                                    items_to_nontext.append(organised_segment_child)
                                else:
                                    organised_segment_child.text = organised_segment_child.text[len(leading_space):]
                                    items_to_nontext.append(etree.Element('{{{0}}}text'.format(self.t_nsmap['kaplan'])))
                                    items_to_nontext[-1].text = leading_space
                                perform_move = True
                            no_text_yet = False
                        elif organised_segment_child.tag == '{{{0}}}tag'.format(self.t_nsmap['kaplan']):
                            items_to_nontext.append(organised_segment_child)

                        elif (organised_segment_child.tag == '{{{0}}}br'.format(self.t_nsmap['kaplan'])
                        or organised_segment_child.tag == '{{{0}}}tab'.format(self.t_nsmap['kaplan'])):
                            items_to_nontext.append(organised_segment_child)
                            perform_move = True
                        else:
                            no_text_yet = False

                else:
                    if active_ftags:
                        for active_ftag in active_ftags:
                            organised_segment.append(etree.Element('{{{0}}}tag'.format(self.t_nsmap['kaplan'])))
                            organised_segment[-1].attrib['no'] = active_ftag
                            organised_segment[-1].attrib['type'] = 'end'
                        else:
                            active_ftags = []

                    if items_to_nontext and perform_move:
                        organised_segment_i = organised_paragraph[0].index(organised_segment)
                        if organised_paragraph[0][organised_segment_i-1].tag != '{{{0}}}non-text-segment'.format(self.t_nsmap['kaplan']):
                            organised_paragraph[0].insert(organised_segment_i, etree.Element('{{{0}}}non-text-segment'.format(self.t_nsmap['kaplan'])))
                        else:
                            organised_segment_i -= 1

                        for item_to_nontext in items_to_nontext:
                            if item_to_nontext.tag == '{{{0}}}.tag'.format(self.t_nsmap['kaplan']):
                                if item_to_nontext.attrib['type'] == 'beginning':
                                    active_ftags.append(item_to_nontext.attrib['no'])
                                else:
                                    active_ftags.remove(item_to_nontext.attrib['no'])
                            organised_paragraph[0][organised_segment_i].append(item_to_nontext)
                        else:
                            if active_ftags:
                                _first_child = organised_paragraph[0][organised_segment_i+1][0]
                                if (_first_child.tag == '{{{0}}}.tag'.format(self.t_nsmap['kaplan'])
                                and _first_child.attrib['type'] == 'end'
                                and _first_child.attrib['no'] in active_ftags):
                                    organised_paragraph[0][organised_segment_i].append(_first_child)
                                else:
                                    _tag = etree.Element('{{{0}}}.tag'.format(self.t_nsmap['kaplan']))
                                    _tag.attrib['no'] = active_ftags[0]
                                    _tag.attrib['type'] = 'end'
                                    organised_paragraph[0][organised_segment_i].append(_tag)

                                    _tag = _tag.__deepcopy__(True)
                                    _tag.attrib['type'] = 'beginning'
                                    organised_paragraph[0][organised_segment_i+1].insert(0, _tag)

                    elif no_text_yet:
                        organised_segment.tag = '{{{0}}}non-text-segment'.format(self.t_nsmap['kaplan'])

            self.paragraphs[paragraph_index] = organised_paragraph[0]

    def write_bilingual_file(self, output_directory):
        bilingual_file = etree.Element('{{{0}}}bilingual_file'.format(self.t_nsmap['kaplan']), nsmap=self.t_nsmap)

        etree.SubElement(bilingual_file, '{{{0}}}paragraphs'.format(self.t_nsmap['kaplan']))

        _counter = 0
        for p_i in range(len(self.paragraphs)):
            new_p_element = etree.Element('{{{0}}}paragraph'.format(self.t_nsmap['kaplan']), no=str(p_i + 1))
            for segment_element in self.paragraphs[p_i]:
                if segment_element.tag == '{{{0}}}source'.format(self.t_nsmap['kaplan']):
                    _counter += 1
                    new_s_element = etree.Element('{{{0}}}segment'.format(self.t_nsmap['kaplan']), no=str(_counter))
                    new_s_element.append(segment_element)
                    new_s_element.append(etree.Element('{{{0}}}status'.format(self.t_nsmap['kaplan'])))
                    new_s_element.append(etree.Element('{{{0}}}target'.format(self.t_nsmap['kaplan'])))
                elif segment_element.tag == '{{{0}}}segment'.format(self.t_nsmap['kaplan']):
                    _counter += 1
                    new_s_element = segment_element.__deepcopy__(True)
                    new_s_element.attrib['no'] = str(_counter)
                else:
                    new_s_element = segment_element
                new_p_element.append(new_s_element)
            bilingual_file[-1].append(new_p_element)

        if self.images:
            bilingual_file.append(etree.Element('{{{0}}}images'.format(self.t_nsmap['kaplan'])))
            for i_i in range(len(self.images)):
                new_i_element = etree.Element('{{{0}}}image'.format(self.t_nsmap['kaplan']), no=str(i_i + 1))
                new_i_element.text = self.images[i_i]
                bilingual_file[-1].append(new_i_element)

        if self.tags:
            bilingual_file.append(etree.Element('{{{0}}}tags'.format(self.t_nsmap['kaplan'])))
            for t_i in range(len(self.tags)):
                new_t_element = etree.Element('{{{0}}}tag'.format(self.t_nsmap['kaplan']), no=str(t_i + 1))
                new_t_element.text = self.tags[t_i]
                bilingual_file[-1].append(new_t_element)

        if self.miscellaneous_tags:
            bilingual_file.append(etree.Element('{{{0}}}miscellaneous_tags'.format(self.t_nsmap['kaplan'])))
            for mt_i in range(len(self.miscellaneous_tags)):
                new_t_element = etree.Element('{{{0}}}miscellaneous_tag'.format(self.t_nsmap['kaplan']), no=str(mt_i + 1))
                new_t_element.text = self.miscellaneous_tags[mt_i]
                bilingual_file[-1].append(new_t_element)

        if self.hyperlinks:
            bilingual_file.append(etree.Element('{{{0}}}hyperlinks'.format(self.t_nsmap['kaplan'])))
            for h_i in range(len(self.hyperlinks)):
                new_h_element = etree.Element('{{{0}}}hyperlink'.format(self.t_nsmap['kaplan']), no=str(h_i + 1))
                new_h_element.text = self.hyperlinks[h_i]
                bilingual_file[-1].append(new_h_element)

        bilingual_file.append(etree.Element('{{{0}}}source_file'.format(self.t_nsmap['kaplan']),
                                            sha256=self.sha256_hash,
                                            name=self.file_name,
                                            type=self.file_type))
        for master_file in self.master_files:
            if len(master_file) == 2:
                new_sf_element = etree.Element('{{{0}}}internal_file'.format(self.t_nsmap['kaplan']),
                                            internal_path=master_file[0])
                new_sf_element.append(master_file[1])

                bilingual_file[-1].append(new_sf_element)
            elif len(self.master_files) == 1 and type(master_file) == str:
                bilingual_file[-1].text = master_file
            else:
                new_sf_element = etree.Element('{{{0}}}internal_file'.format(self.t_nsmap['kaplan']))
                for paragraph_placeholder in master_file[0]:
                    new_sf_element.append(paragraph_placeholder)

                bilingual_file[-1].append(new_sf_element)

        bilingual_file.getroottree().write(os.path.join(output_directory, self.file_name) + '.xml',
                                           encoding='UTF-8',
                                           xml_declaration=True)
