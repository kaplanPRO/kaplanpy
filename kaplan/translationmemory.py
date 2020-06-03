import difflib
import os

from lxml import etree

from .utils import get_current_time_in_utc, nsmap, segment_to_tm_segment
from .version import __version__


class TranslationMemory():
    def __init__(self, tm_path, source_language=None, target_language=None):
        self.translation_memory = etree.parse(tm_path).getroot()
        self.tm_path = tm_path
        self.source_language = self.translation_memory[0].attrib['srclang']
        self.target_language = self.translation_memory[0].attrib['trgtlang']

    def lookup(self, source_segment, match=0.5, convert_segment=True):
        segment_hits = []

        if convert_segment:
            segment_query = segment_to_tm_segment(source_segment)
        else:
            segment_query = source_segment

        sequence_matcher = difflib.SequenceMatcher()
        sequence_matcher.set_seq2(segment_query)

        for translation_unit in self.translation_memory[1]:
            sequence_matcher.set_seq1(translation_unit[1].text)
            match_ratio = sequence_matcher.ratio()
            if match_ratio >= match:
                segment_hits.append((match_ratio,
                                    translation_unit[0].__deepcopy__(True),
                                    translation_unit[2].__deepcopy__(True)))
        if segment_hits:
            sorted_segment_hits = [segment_hits[0]]
            for segment_hit in segment_hits[1:]:
                for sorted_segment_hit in sorted_segment_hits:
                    if segment_hit[0] > sorted_segment_hit[0]:
                        sorted_segment_hits.insert(sorted_segment_hits.index(sorted_segment_hit), segment_hit)
                        break
                    elif segment_hit[0] == sorted_segment_hit[0]:
                        sorted_segment_hits.insert(sorted_segment_hits.index(sorted_segment_hit)+1, segment_hit)
                        break
                    else:
                        sorted_segment_hits.append(segment_hit)
                        break
            return sorted_segment_hits
        else:
            return ()

    @classmethod
    def new(cls, tm_path, source_language, target_language, overwrite=False):
        if os.path.exists(tm_path) and not overwrite:
            raise ValueError('To overwrite a translation memory, set overwrite=True')

        translation_memory = etree.Element('{{{0}}}tm'.format(nsmap['kaplan']), nsmap=nsmap)
        translation_memory.attrib['version'] = '0.0.1'
        translation_memory.append(etree.Element('{{{0}}}header'.format(nsmap['kaplan'])))
        translation_memory[0].attrib['creationtool'] = 'kaplan'
        translation_memory[0].attrib['creationtoolversion'] = __version__
        translation_memory[0].attrib['creationdate'] = get_current_time_in_utc()
        translation_memory[0].attrib['datatype'] = 'PlainText'
        translation_memory[0].attrib['segtype'] = 'sentence'
        translation_memory[0].attrib['adminlang'] = 'en'
        translation_memory[0].attrib['srclang'] = source_language
        translation_memory[0].attrib['trgtlang'] = target_language
        translation_memory.append(etree.Element('{{{0}}}body'.format(nsmap['kaplan'])))

        translation_memory.getroottree().write(tm_path,
                                               encoding='UTF-8',
                                               xml_declaration=True)

        return cls(tm_path)

    def submit_segment(self, source_segment, target_segment, author_id):
        segment_query = segment_to_tm_segment(source_segment)

        for translation_unit in self.translation_memory[1]:
            if translation_unit[1].text == segment_query:
                translation_unit[2] = target_segment.__deepcopy__(True)
                translation_unit.attrib['changedate'] = get_current_time_in_utc()
                translation_unit.attrib['changeid'] = author_id
                break
        else:
            translation_unit = etree.Element('{{{0}}}tu'.format(nsmap['kaplan']))
            translation_unit.attrib['creationdate'] = get_current_time_in_utc()
            translation_unit.attrib['creationid'] = author_id
            translation_unit.append(source_segment.__deepcopy__(True))
            translation_unit.append(etree.Element('{{{0}}}query'.format(nsmap['kaplan'])))
            translation_unit[1].text = segment_query
            translation_unit.append(target_segment.__deepcopy__(True))

            self.translation_memory[1].append(translation_unit)

        self.translation_memory.getroottree().write(self.tm_path,
                                                    encoding='UTF-8',
                                                    xml_declaration=True)
