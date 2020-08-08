import os, regex

from lxml import etree

from .utils import get_current_time_in_utc, nsmap


class BilingualFile:
    def __init__(self, file_path):
        self.hyperlinks = []
        self.images = []
        self.paragraphs = []
        self.tags = []
        self.miscellaneous_tags = []

        self.xml_root = etree.parse(file_path).getroot()
        self.t_nsmap = self.xml_root.nsmap

        self.file_type = self.xml_root.find('kaplan:source_file', self.t_nsmap).attrib['type']
        self.file_name = self.xml_root.find('kaplan:source_file', self.t_nsmap).attrib['name']
        if len(self.xml_root.find('kaplan:source_file', self.t_nsmap)) > 0:
            self.nsmap = self.xml_root.find('kaplan:source_file', self.t_nsmap)[0][0].nsmap
        else:
            self.nsmap = self.xml_root.nsmap

        for xml_paragraph in self.xml_root.find('kaplan:paragraphs', self.t_nsmap):
            paragraph_no = xml_paragraph.attrib['no']
            current_paragraph = []
            for xml_segment in xml_paragraph.findall('kaplan:segment', self.t_nsmap):
                current_paragraph.append([xml_segment[0],
                                          xml_segment[1],
                                          xml_segment[2],
                                          int(paragraph_no),
                                          int(xml_segment.attrib['no'])])

            self.paragraphs.append(current_paragraph)

        if self.xml_root.find('kaplan:tags', self.t_nsmap) is not None:
            for xml_tag in self.xml_root.find('kaplan:tags', self.t_nsmap):
                self.tags.append(xml_tag.text)

        if self.xml_root.find('kaplan:miscellaneous_tags', self.t_nsmap) is not None:
            for xml_mtag in self.xml_root.find('kaplan:miscellaneous_tags', self.t_nsmap):
                self.miscellaneous_tags.append(xml_mtag.text)

        if self.xml_root.find('kaplan:hyperlinks', self.t_nsmap) is not None:
            for xml_hl in self.xml_root.find('kaplan:hyperlinks', self.t_nsmap):
                self.hyperlinks.append(xml_hl.text)

        if self.xml_root.find('kaplan:images', self.t_nsmap) is not None:
            for xml_image in self.xml_root.find('kaplan:images', self.t_nsmap):
                self.images.append(xml_image.text)

    def generate_target_translation(self, source_file_path, output_directory):
        from hashlib import sha256
        import zipfile

        from .utils import file_clean_up

        sha256_hash = sha256()
        buffer_size = 5 * 1048576  # 5 MB
        sf = open(source_file_path, 'rb')
        while True:
            data = sf.read(buffer_size)
            if data:
                sha256_hash.update(data)
            else:
                break
        sf.close()
        sha256_hash = sha256_hash.hexdigest()

        sf_sha256 = self.xml_root.find('kaplan:source_file', self.t_nsmap).attrib['sha256']

        assert sha256_hash == sf_sha256, 'SHA256 hash of the file does not match that of the source file'

        target_paragraphs = []
        for xml_paragraph in self.xml_root[0]:
            target_paragraph = []
            for xml_segment in xml_paragraph:
                if xml_segment.tag == '{{{0}}}segment'.format(self.t_nsmap['kaplan']):
                    if len(xml_segment[2]) == 0:
                        for source_elem in xml_segment[0]:
                            target_paragraph.append(source_elem)
                    else:
                        for target_elem in xml_segment[2]:
                            target_paragraph.append(target_elem)
                else:
                    for source_elem in xml_segment:
                        target_paragraph.append(source_elem)

            target_paragraphs.append(target_paragraph)

        final_paragraphs = []

        if self.file_type == 'docx':

            for target_paragraph in target_paragraphs:
                active_ftags = []
                final_paragraph = [etree.Element('{{{0}}}r'.format(self.nsmap['w']))]
                start_new_run = False
                for sub_elem in target_paragraph:
                    if start_new_run:
                        if len(final_paragraph[-1]) > 0:
                            final_paragraph.append(etree.Element('{{{0}}}r'.format(self.nsmap['w'])))
                        start_new_run = False
                        if active_ftags:
                            final_paragraph[-1].append(etree.Element('{{{0}}}rPr'.format(self.nsmap['w'])))
                            for active_ftag_no in reversed(active_ftags):
                                if int(active_ftag_no) <= len(self.tags):
                                    active_ftag = etree.fromstring(self.tags[int(active_ftag_no)-1])
                                    for prop in active_ftag:
                                        if final_paragraph[-1][-1].find(prop.tag) is None:
                                            final_paragraph[-1][-1].append(prop)

                    if sub_elem.tag == '{{{0}}}text'.format(self.t_nsmap['kaplan']):
                        if (final_paragraph[-1].find('w:t', self.nsmap) is not None
                                and final_paragraph[-1][-1].tag == '{{{0}}}t'.format(self.nsmap['w'])):
                            final_paragraph[-1][-1].text += sub_elem.text
                        else:
                            final_paragraph[-1].append(etree.Element('{{{0}}}t'.format(self.nsmap['w'])))
                            final_paragraph[-1][-1].set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
                            final_paragraph[-1][-1].text = sub_elem.text
                    elif sub_elem.tag == '{{{0}}}tag'.format(self.t_nsmap['kaplan']):
                        start_new_run = True
                        if sub_elem.attrib['type'] == 'beginning':
                            if sub_elem.attrib['no'] not in active_ftags:
                                active_ftags.append(sub_elem.attrib['no'])
                        else:
                            if sub_elem.attrib['no'] in active_ftags:
                                active_ftags.remove(sub_elem.attrib['no'])
                    elif sub_elem.tag == '{{{0}}}tab'.format(self.t_nsmap['kaplan']):
                        final_paragraph[-1].append(etree.Element('{{{0}}}tab'.format(self.nsmap['w'])))
                    elif sub_elem.tag == '{{{0}}}br'.format(self.t_nsmap['kaplan']):
                        if 'type' in sub_elem.attrib and sub_elem.attrib['type'] == 'page':
                            if len(final_paragraph[-1]) > 0:
                                final_paragraph.append(etree.Element('{{{0}}}r'.format(self.nsmap['w'])))
                            final_paragraph[-1].append(etree.Element('{{{0}}}br'.format(self.nsmap['w'])))
                            final_paragraph[-1][-1].attrib['type'] = 'page'
                        else:
                            final_paragraph[-1].append(etree.Element('{{{0}}}br'.format(self.nsmap['w'])))
                    elif sub_elem.tag == '{{{0}}}image'.format(self.t_nsmap['kaplan']):
                        if int(sub_elem.attrib['no']) <= len(self.images):
                            if len(final_paragraph[-1]) > 0:
                                final_paragraph.append(etree.Element('{{{0}}}r'.format(self.nsmap['w'])))
                            final_paragraph[-1].append(etree.fromstring(self.images[int(sub_elem.attrib['no'])-1]))
                            final_paragraph.append(etree.Element('{{{0}}}r'.format(self.nsmap['w'])))

                if len(final_paragraph[-1]) == 0:
                    final_paragraph = final_paragraph[:-1]

                final_paragraphs.append(final_paragraph)

            for internal_file in self.xml_root[-1]:
                internal_file = internal_file[0]
                for paragraph in internal_file.findall('.//w:p', self.nsmap):
                    for paragraph_placeholder in paragraph.findall('kaplan:paragraph', self.t_nsmap):
                        current_elem_i = paragraph.index(paragraph_placeholder)
                        paragraph.remove(paragraph_placeholder)
                        for final_run in final_paragraphs[int(paragraph_placeholder.attrib['no'])-1]:
                            if len(final_run) == 0:
                                pass
                            elif len(final_run) == 1 and final_run[0].tag.endswith('rPr'):
                                pass
                            else:
                                paragraph.insert(current_elem_i,
                                                etree.fromstring(etree.tostring(final_run)))
                                current_elem_i += 1

        elif self.file_type == 'odt' or self.file_type == 'ods' or self.file_type == 'odp':

            for target_paragraph in target_paragraphs:
                active_ftags = []
                active_links = []
                final_paragraph = []

                for child in target_paragraph:
                    if child.tag == '{{{0}}}text'.format(self.nsmap['kaplan']):
                        if child.text is None:
                            continue
                        if len(active_ftags) > 1 and active_links:
                            if len(final_paragraph[-1][-1][-1]) == 0:
                                if final_paragraph[-1][-1][-1].text is None:
                                    final_paragraph[-1][-1][-1].text = ''
                                final_paragraph[-1][-1][-1].text += child.text
                            else:
                                if final_paragraph[-1][-1][-1][-1].tail is None:
                                    final_paragraph[-1][-1][-1][-1].tail = ''
                                final_paragraph[-1][-1][-1][-1].tail += child.text
                        elif (active_links and active_ftags) or len(active_ftags) > 1:
                            if len(final_paragraph[-1][-1]) == 0:
                                if final_paragraph[-1][-1].text is None:
                                    final_paragraph[-1][-1].text = ''
                                final_paragraph[-1][-1].text += child.text
                            else:
                                if final_paragraph[-1][-1][-1].tail is None:
                                    final_paragraph[-1][-1][-1].tail = ''
                                final_paragraph[-1][-1][-1].tail += child.text
                        elif active_links or active_ftags:
                            if len(final_paragraph[-1]) == 0:
                                if final_paragraph[-1].text is None:
                                    final_paragraph[-1].text = ''
                                final_paragraph[-1].text += child.text
                            else:
                                if final_paragraph[-1][-1].tail is None:
                                    final_paragraph[-1][-1].tail = ''
                                final_paragraph[-1][-1].tail += child.text
                        else:
                            final_paragraph.append(child.text)

                    elif child.tag == '{{{0}}}tag'.format(self.nsmap['kaplan']):
                        if child.attrib['type'] == 'beginning':
                            if child.attrib['no'] not in active_ftags:
                                active_ftags.insert(0, child.attrib['no'])

                        else:
                            if child.attrib['no'] in active_ftags:
                                active_ftags.remove(child.attrib['no'])

                            if active_ftags or active_links:
                                last_span = final_paragraph[-1][-1]

                            else:
                                last_span = final_paragraph[-1]

                            if len(last_span) == 0 and (last_span.text is '' or last_span.text is None):
                                last_span.getparent().remove(last_span)

                        if len(active_ftags) > 1 and active_links:
                            final_paragraph[-1][-1].append(etree.Element('{{{0}}}span'.format(self.nsmap['text'])))
                            final_paragraph[-1][-1][-1].attrib['{{{0}}}style-name'.format(self.nsmap['text'])] = self.tags[int(active_ftags[0])-1]

                        elif (active_ftags and active_links) or len(active_ftags) > 1:
                            final_paragraph[-1].append(etree.Element('{{{0}}}span'.format(self.nsmap['text'])))
                            final_paragraph[-1][-1].attrib['{{{0}}}style-name'.format(self.nsmap['text'])] = self.tags[int(active_ftags[0])-1]

                        elif active_ftags:
                            final_paragraph.append(etree.Element('{{{0}}}span'.format(self.nsmap['text'])))
                            final_paragraph[-1].attrib['{{{0}}}style-name'.format(self.nsmap['text'])] = self.tags[int(active_ftags[0])-1]

                    elif child.tag == '{{{0}}}image'.format(self.nsmap['kaplan']):
                        if len(active_ftags) > 1 and active_links:
                            final_paragraph[-1][-1][-1].append(etree.fromstring(self.images[int(child.attrib['no'])-1]))
                        elif (active_ftags and active_links) or len(active_ftags) > 1:
                            final_paragraph[-1][-1].append(etree.fromstring(self.images[int(child.attrib['no'])-1]))
                        elif active_ftags or active_links:
                            final_paragraph[-1].append(etree.fromstring(self.images[int(child.attrib['no'])-1]))
                        else:
                            final_paragraph.append(etree.fromstring(self.images[int(child.attrib['no'])-1]))

                    elif child.tag == '{{{0}}}link'.format(self.nsmap['kaplan']):
                        if child.attrib['type'] == 'beginning':
                            if child.attrib['no'] not in active_links:
                                active_links.append(child.attrib['no'])
                        else:
                            if child.attrib['no'] in active_links:
                                active_links.remove(child.attrib['no'])

                        if active_links:
                            final_paragraph.append(etree.fromstring(self.hyperlinks[int(child.attrib['no'])-1]))
                            if active_ftags:
                                final_paragraph[-1].append(etree.Element('{{{0}}}span'.format(self.nsmap['text'])))
                                final_paragraph[-1][-1].attrib['{{{0}}}style-name'.format(self.nsmap['text'])] = self.tags[int(active_ftags[0])-1]

                    elif child.tag == '{{{0}}}br'.format(self.nsmap['kaplan']):
                        if len(active_ftags) > 1 and active_links:
                            final_paragraph[-1][-1][-1].append(etree.Element('{{{0}}}line-break'.format(self.nsmap['text'])))
                        elif (active_ftags and active_links) or len(active_ftags) > 1:
                            final_paragraph[-1][-1].append(etree.Element('{{{0}}}line-break'.format(self.nsmap['text'])))
                        elif active_ftags or active_links:
                            final_paragraph[-1].append(etree.Element('{{{0}}}line-break'.format(self.nsmap['text'])))
                        else:
                            final_paragraph.append(etree.Element('{{{0}}}line-break'.format(self.nsmap['text'])))

                    elif child.tag == '{{{0}}}tab'.format(self.nsmap['kaplan']):
                        if len(active_ftags) > 1 and active_links:
                            final_paragraph[-1][-1][-1].append(etree.Element('{{{0}}}tab'.format(self.nsmap['text'])))
                        elif (active_ftags and active_links) or len(active_ftags) > 1:
                            final_paragraph[-1][-1].append(etree.Element('{{{0}}}tab'.format(self.nsmap['text'])))
                        elif active_ftags or active_links:
                            final_paragraph[-1].append(etree.Element('{{{0}}}tab'.format(self.nsmap['text'])))
                        else:
                            final_paragraph.append(etree.Element('{{{0}}}tab'.format(self.nsmap['text'])))

                    else:
                        if len(active_ftags) > 1 and active_links:
                            final_paragraph[-1][-1][-1].append(etree.fromstring(self.miscellaneous_tags[int(child.attrib['no'])-1]))
                        elif (active_ftags and active_links) or len(active_ftags) > 1:
                            final_paragraph[-1][-1].append(etree.fromstring(self.miscellaneous_tags[int(child.attrib['no'])-1]))
                        elif active_ftags or active_links:
                            final_paragraph[-1].append(etree.fromstring(self.miscellaneous_tags[int(child.attrib['no'])-1]))
                        else:
                            final_paragraph.append(etree.fromstring(self.miscellaneous_tags[int(child.attrib['no'])-1]))


                final_paragraphs.append(final_paragraph)

            if self.file_type == 'ods':
                self.sheets = {}
                internal_file = self.xml_root[-1][0][0]
                for sheet_element in internal_file.xpath('office:body/office:spreadsheet/table:table', namespaces=self.nsmap):
                    if '{{{0}}}name'.format(self.nsmap['table']) in sheet_element.attrib:
                        sheet_p = sheet_element.attrib['{{{0}}}name'.format(self.nsmap['table'])]
                        sheet_p = self.paragraphs[int(sheet_p) - 1][0]
                        if len(sheet_p[2]) > 0:
                            self.sheets[sheet_element.attrib['{{{0}}}name'.format(self.nsmap['table'])]] = sheet_p[2][0].text
                            sheet_element.attrib['{{{0}}}name'.format(self.nsmap['table'])] = sheet_p[2][0].text
                        else:
                            self.sheets[sheet_element.attrib['{{{0}}}name'.format(self.nsmap['table'])]] = sheet_p[0][0].text
                            sheet_element.attrib['{{{0}}}name'.format(self.nsmap['table'])] = sheet_p[0][0].text

            for internal_file in self.xml_root[-1]:
                internal_file = internal_file[0]
                for paragraph_placeholder in internal_file.findall('.//kaplan:paragraph', self.t_nsmap):
                    paragraph_placeholder_parent = paragraph_placeholder.getparent()
                    placeholder_i = paragraph_placeholder_parent.index(paragraph_placeholder)
                    child_i = placeholder_i

                    if self.file_type == 'ods':
                        for cell_reference in paragraph_placeholder_parent.getparent().xpath('draw:g/svg:desc', namespaces=self.nsmap):
                            cell_reference_text = cell_reference.text
                            for sheet_reference in regex.findall('{([0-9]+)}', cell_reference_text):
                                if sheet_reference in self.sheets:
                                    cell_reference_text = cell_reference_text.replace('{{{0}}}'.format(sheet_reference), '{0}'.format(self.sheets[sheet_reference]), 1)
                            else:
                                cell_reference.text = cell_reference_text

                    for final_paragraph_child in final_paragraphs[int(paragraph_placeholder.attrib['no'])-1]:
                        if type(final_paragraph_child) == str:
                            if child_i == 0:
                                if paragraph_placeholder_parent.text is None:
                                    paragraph_placeholder_parent.text = ''
                                paragraph_placeholder_parent.text += final_paragraph_child
                            else:
                                if paragraph_placeholder_parent[child_i-1].tail is None:
                                    paragraph_placeholder_parent[child_i-1].tail = ''
                                paragraph_placeholder_parent[child_i-1].tail += final_paragraph_child
                        else:
                            if child_i == placeholder_i:
                                paragraph_placeholder_parent.replace(paragraph_placeholder, final_paragraph_child)
                            else:
                                paragraph_placeholder_parent.insert(child_i, final_paragraph_child)

                            child_i += 1

                    else:
                        if child_i == 0 and paragraph_placeholder in paragraph_placeholder_parent:
                            paragraph_placeholder_parent.remove(paragraph_placeholder)

        elif self.file_type == 'txt':
            if not os.path.exists(output_directory):
                os.mkdir(output_directory)

            for target_paragraph in target_paragraphs:
                final_paragraph = []

                for child in target_paragraph:
                    final_paragraph.append(child.text)
                else:
                    final_paragraph = ''.join(final_paragraph)

                final_paragraphs.append(final_paragraph)

            with open(os.path.join(output_directory, self.file_name), 'w') as target_file:
                for final_paragraph in final_paragraphs:
                    if final_paragraph is not None:
                        target_file.write(final_paragraph + '\n')
                    else:
                        target_file.write('\n')

            return

        elif self.file_type == 'xliff':
            for p_i in range(len(self.paragraphs)):
                translation_unit = self.xml_root.find('.//{{{0}}}trans-unit[@{{{1}}}paragraph-no="{2}"]'.format(self.nsmap[None], self.t_nsmap['kaplan'], p_i+1))
                translation_unit.find('{{{0}}}target'.format(self.nsmap[None])).text = self.paragraphs[p_i][0][2][0].text
            else:
                if not os.path.exists(output_directory):
                    os.mkdir(output_directory)

                self.xml_root[-1][0][0].getroottree().write(os.path.join(output_directory,
                                                                        self.file_name),
                                                            encoding='UTF-8',
                                                            xml_declaration=True)
                return

        elif self.file_type == 'po':
            paragraphs = self.xml_root.find('kaplan:paragraphs', self.nsmap)

            with open(os.path.join(output_directory, self.file_name), 'w') as outfile:
                outfile.write(self.xml_root.find('kaplan:source_file', self.nsmap).text)
                for p_i in range(len(self.paragraphs)):
                    paragraph = paragraphs[p_i]
                    segments = paragraph.findall('kaplan:segment', self.nsmap)
                    outfile.write('\n')
                    if 'metadata' in segments[0].attrib:
                        outfile.write(segments[0].attrib['metadata'])
                        outfile.write('\n')
                    entry = []
                    for s_i in range(len(segments)):
                        segment_keys = segments[s_i].attrib['keys'].split(';')
                        entry.insert(s_i, '{0} "{1}"'.format(segment_keys[0],
                                                             segments[s_i].find('kaplan:source', self.nsmap)[0].text))
                        entry.append('{0} "{1}"'.format(segment_keys[1],
                                                        segments[s_i].find('kaplan:target', self.nsmap)[0].text))
                    for line in entry:
                        outfile.write(line)
                        outfile.write('\n')
                outfile.write('\n')

            return

        # Filetype-specific processing ends here.

        with zipfile.ZipFile(source_file_path) as zf:
            for name in zf.namelist():
                zf.extract(name, os.path.join(output_directory, '.temp'))

        for internal_file in self.xml_root[-1]:
            etree.ElementTree(internal_file[0]).write(os.path.join(output_directory,
                                                                    '.temp',
                                                                    internal_file.attrib['internal_path']),
                                                        encoding='UTF-8',
                                                        xml_declaration=True)

        to_zip = []
        for root, dir, files in os.walk(os.path.join(output_directory, '.temp')):
            for name in files:
                to_zip.append(os.path.join(root, name))

        with zipfile.ZipFile(os.path.join(output_directory, self.file_name), 'w') as target_zf:
            for name in to_zip:
                target_zf.write(name, name[len(os.path.join(output_directory, '.temp')):])

        file_clean_up(os.path.join(output_directory, '.temp'))

    def merge_segments(self, list_of_segments):
        '''Merges two segments of the same paragraph.'''

        assert type(list_of_segments) == list, 'The parameter \'list_of_segments\' must be a list.'

        list_of_segments = sorted([int(segment_no) for segment_no in set(list_of_segments)])

        current_segment_no = 0
        paragraph = None
        for segment_no in list_of_segments:
            if current_segment_no == 0:
                current_segment_no = segment_no
            else:
                current_segment_no += 1
                assert current_segment_no == segment_no, 'Segments must be consecutive.'

            segment = self.xml_root[0].find('.//kaplan:segment[@no="{0}"]'.format(segment_no), self.nsmap)
            if paragraph is None:
                paragraph = segment.getparent()
            else:
                assert segment.getparent() == paragraph, 'Segments are of different paragraphs.'

            list_of_segments[list_of_segments.index(segment_no)] = segment

        segment_range = paragraph[paragraph.index(list_of_segments[0]):paragraph.index(list_of_segments[-1])+1]

        segment_range[0][1].text = 'Draft'
        for segment in segment_range[1:]:
            if segment.tag == '{{{0}}}non-text-segment'.format(self.nsmap['kaplan']):
                for segment_child in segment:
                    segment_range[0][0].append(segment_child.__deepcopy__(True))
                    segment_range[0][2].append(segment_child.__deepcopy__(True))
                else:
                    paragraph.remove(segment)
            else:
                for segment_child in segment[0]:
                    segment_range[0][0].append(segment_child)
                for segment_child in segment[2]:
                    segment_range[0][2].append(segment_child)
                paragraph.remove(segment)

    def save(self, output_directory):
        self.xml_root.getroottree().write(os.path.join(output_directory, self.file_name) + '.xml',
                                          encoding='UTF-8',
                                          xml_declaration=True)

    def update_segment(self, segment_status, segment_target, paragraph_no, segment_no, author_id, auto_propagation=True):
        assert type(segment_target) == etree._Element or type(segment_target) == str

        xml_segment = self.xml_root[0][paragraph_no - 1].find('kaplan:segment[@no="{0}"]'.format(segment_no),
                                                              self.t_nsmap)
        sub_p_id = xml_segment.getparent().findall('kaplan:segment', self.t_nsmap).index(xml_segment)
        segment = self.paragraphs[paragraph_no - 1][sub_p_id]

        segments_list = [(xml_segment, sub_p_id, segment)]
        segment_no_list = []
        if segment_status == 'Translated' and auto_propagation:
            for paragraph in self.xml_root[0]:
                for xml_segment in paragraph.findall('kaplan:segment', self.t_nsmap):
                    if etree.tostring(segments_list[0][0][0]) == etree.tostring(xml_segment[0]):
                        sub_p_id = xml_segment.getparent().findall('kaplan:segment', self.t_nsmap).index(xml_segment)
                        segment = self.paragraphs[self.xml_root[0].index(paragraph)][sub_p_id]
                        if segment[-1] != segments_list[0][2][-1]:
                            segments_list.append((xml_segment, sub_p_id, segment))
                            segment_no_list.append(segment[-1])

        for xml_segment, sub_p_id, segment in segments_list:
            xml_segment[1].text = segment_status
            xml_segment[2] = etree.Element('{{{0}}}target'.format(self.t_nsmap['kaplan']))

            if type(segment_target) == str:
                xml_segment[2].append(etree.Element('{{{0}}}text'.format(self.t_nsmap['kaplan'])))
                xml_segment[2][0].text = segment_target
            else:
                for sub_elem in segment_target:
                    xml_segment[2].append(sub_elem.__deepcopy__(True))

            segment[1] = xml_segment[1]
            segment[2] = xml_segment[2]

            if 'creationdate' in xml_segment.attrib:
                xml_segment.attrib['changedate'] = get_current_time_in_utc()
                xml_segment.attrib['changeid'] = author_id
            else:
                xml_segment.attrib['creationdate'] = get_current_time_in_utc()
                xml_segment.attrib['creationid'] = author_id

            self.paragraphs[paragraph_no - 1][sub_p_id] = segment

        return segment_no_list
