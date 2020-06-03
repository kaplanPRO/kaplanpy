import datetime
import re

from html import escape
from lxml import etree

from .language_codes import language_codes

nsmap = {'kaplan': 'https://kaplan.pro'}

supported_file_formats = ('.docx', '.odp', '.ods', '.odt', '.txt', '.xliff')

def get_current_time_in_utc():
    return datetime.datetime.utcnow().strftime(r'%Y%M%dT%H%M%SZ')

def html_to_segment(source_or_target_segment, segment_designation, nsmap={'kaplan': 'https://kaplan.pro'}):

    segment = re.findall(r'<tag[\s\S]+?class="([\s\S]+?)">([\s\S]+?)</tag>|([^<^>]+)',
                        source_or_target_segment)

    segment_xml = etree.Element('{{{0}}}{1}'.format(nsmap['kaplan'], segment_designation),
                                nsmap=nsmap)
    for element in segment:
        if element[0]:
            tag = element[0].split()
            tag.insert(0, element[1][len(tag[0]):])
            segment_xml.append(etree.Element('{{{0}}}{1}'.format(nsmap['kaplan'], tag[1])))
            segment_xml[-1].attrib['no'] = tag[0]
            if len(tag) > 2:
                segment_xml[-1].attrib['type'] = tag[2]
        elif element[2]:
            segment_xml.append(etree.Element('{{{0}}}text'.format(nsmap['kaplan'])))
            segment_xml[-1].text = element[2]

    return segment_xml

def segment_to_html(source_or_target_segment):
    segment_html = ''
    for sub_elem in source_or_target_segment:
        if sub_elem.tag.endswith('}text'):
            segment_html += escape(sub_elem.text)
        else:
            tag = etree.Element('tag')
            tag.attrib['contenteditable'] = 'false'
            tag.attrib['class'] = sub_elem.tag.split('}')[-1]
            tag.text = tag.attrib['class']
            if 'type' in sub_elem.attrib:
                if sub_elem.attrib['type'] == 'beginning' or sub_elem.attrib['type'] == 'end':
                    tag.attrib['class'] += ' ' + sub_elem.attrib['type']
                else:
                    tag.attrib['class'] += ' ' + 'standalone'
            else:
                tag.attrib['class'] += ' ' + 'standalone'

            if 'no' in sub_elem.attrib:
                tag.text += sub_elem.attrib['no']

            segment_html += etree.tostring(tag).decode()

    return segment_html

def segment_to_tm_segment(segment):
    target_segment = ''

    for segment_child in segment:
        if segment_child.tag == '{{{0}}}text'.format(nsmap['kaplan']):
            target_segment += segment_child.text
        elif segment_child.tag == '{{{0}}}tag'.format(nsmap['kaplan']):
            if segment_child.attrib['type'] == 'beginning':
                target_segment += '<tag{0}>'.format(segment_child.attrib['no'])
            else:
                target_segment += '</tag{0}>'.format(segment_child.attrib['no'])
        else:
            _tag_label = segment_child.tag.split('}')[-1]
            if 'no' in segment_child.attrib:
                _tag_label += segment_child.attrib['no']
            target_segment += '<{0}/>'.format(_tag_label)

    return target_segment

def analyse_files(file_path_or_paths, tm_paths=[], source_language=None, target_language=None):
    import difflib
    from .bilingualfile import BilingualFile
    from .translationmemory import TranslationMemory

    if type(file_path_or_paths) is not tuple and type(file_path_or_paths) is not list:
        raise TypeError('file_path_or_paths must be a tuple or a list.')

    if type(tm_paths) is not tuple and type(tm_paths) is not list:
        raise TypeError('tm_paths must be a tuple or a list.')


    tms = (TranslationMemory(tm_path) for tm_path in tm_paths)

    report = {}

    segments = []

    for file_path in file_path_or_paths:
        bf = BilingualFile(file_path)

        report[bf.file_name] = {
            'Repetitions': 0,
            '100%': 0,
            '99%-50%': 0,
            'No match': 0,
            'Total': 0
        }

        for paragraph in bf.paragraphs:
            for segment in paragraph:
                segment = segment_to_tm_segment(segment[0])
                if segment in segments:
                    report[bf.file_name]['Repetitions'] += len(segment.split(' '))
                else:
                    sequence_matcher = difflib.SequenceMatcher()
                    sequence_matcher.set_seq2(segment)
                    match_ratio = 0
                    for saved_segment in segments:
                        sequence_matcher.set_seq1(saved_segment)
                        new_ratio = sequence_matcher.ratio()
                        if new_ratio > match_ratio:
                            match_ratio = new_ratio
                    segments.append(segment)

                    for tm in tms:
                        tm_hits = tm.lookup(segment, convert_segment=False)

                        if tm_hits and tm_hits[0][0] > match_ratio:
                            match_ratio = tm_hits[0][0]

                    if match_ratio >= 1:
                        report[bf.file_name]['100%'] += len(segment.split(' '))
                    elif match_ratio < 1 and match_ratio >= 0.5:
                        report[bf.file_name]['99%-50%'] += len(segment.split(' '))
                    else:
                        report[bf.file_name]['No match'] += len(segment.split(' '))
                    report[bf.file_name]['Total'] += len(segment.split(' '))

    project_total = {
        'Repetitions': 0,
        '100%': 0,
        '99%-50%': 0,
        'No match': 0,
        'Total': 0
    }

    for file_name in report:
        for key in report[file_name]:
            project_total[key] += report[file_name][key]

    report['Project Total'] = project_total

    return report

def file_clean_up(directory_path):
    '''Removes all files inside the given directory path.'''

    import os

    for root, dirs, files in os.walk(directory_path, topdown=False):
        for target_file in files:
            os.remove(os.path.join(root, target_file))
        os.rmdir(root)
