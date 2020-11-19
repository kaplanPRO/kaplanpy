# Installed libraries
from lxml import etree
import regex

# Standard Python libraries
from copy import deepcopy
import difflib
import html
from io import BytesIO
import os

nsmap = {
    'kaplan': 'https://kaplan.pro',
    'xliff': 'urn:oasis:names:tc:xliff:document:2.1',
    'xml': 'http://www.w3.org/XML/1998/namespace'
}

class XLIFF:
    '''
    XML Localisation File (http://docs.oasis-open.org/xliff/xliff-core/v2.1/xliff-core-v2.1.html)

    Args:
        tm: Either the path to a KTM file or a KTM file as a BytesIO instance.
        src (optional): ISO 639-1 code for the source language.
        trgt (optional): ISO 639-1 code for the target language.
    '''
    def __init__(self, path_or_xliff_file, src=None, trgt=None):
        self.name = os.path.basename(path_or_xliff_file) if type(path_or_xliff_file) == str else path_or_xliff_file.name
        self.xml_root = etree.parse(path_or_xliff_file).getroot()

        if self.xml_root.nsmap[None] != nsmap['xliff']:
            raise TypeError('This class can only parse XLIFF v2.1')

    def lookup_segment(self, source_segment, diff=0.5):
        source_segment = etree.fromstring(source_segment)
        ids = {}
        for any_child in source_segment:
            any_child.tag = etree.QName(any_child).localname
            if any_child.attrib.get('id', None):
                copy_child = deepcopy(any_child)
                copy_child.tail = None
                ids['<' + '-'.join((copy_child.tag, copy_child.attrib['id'])) + '>'] = etree.tostring(copy_child, encoding='UTF-8')

        source_string, _ = self.prepare_segment(source_segment)

        sm = difflib.SequenceMatcher()
        sm.set_seq1(source_string)

        tm_hits = []

        for source_entry in self.xml_root.xpath('.//xliff:source', namespaces=nsmap):
            sm.set_seq2(source_entry.text)
            if sm.ratio() > diff:
                segment = etree.Element('segment')
                source_hit = source_entry.text
                source = etree.SubElement(segment, 'source')
                for text, tag in regex.findall('([^<>]+)?(<[^<>\s]+>)?', source_hit):
                    if text != '':
                        text = html.unescape(text)
                        if len(source) == 0:
                            if source.text is not None:
                                source.text += text
                            else:
                                source.text = text
                        else:
                            if source[-1].tail is not None:
                                source[-1].tail += text
                            else:
                                source[-1].tail = text
                    if tag != '':
                        if tag not in ids:
                            continue
                        tag = etree.fromstring(ids[tag])
                        source.append(tag)

                target_hit = source_entry.getparent()[1].text
                target = etree.SubElement(segment, 'target')
                for text, tag in regex.findall('([^<>]+)?(<[^<>\s]+>)?', target_hit):
                    if text != '':
                        text = html.unescape(text)
                        if len(target) == 0:
                            if target.text is not None:
                                target.text += text
                            else:
                                target.text = text
                        else:
                            if target[-1].tail is not None:
                                target[-1].tail += text
                            else:
                                target[-1].tail = text
                    if tag != '':
                        if tag not in ids:
                            continue
                        tag = etree.fromstring(ids[tag])
                        target.append(tag)

                tm_hits.append((sm.ratio(), segment))

        tm_hits.sort(reverse=True)

        return tm_hits

    @classmethod
    def new(cls, name, src, trgt):
        '''
            name: File name for the KTM file.
            src: ISO 639-1 code for the source language.
            trgt: ISO 639-1 code for the target language.
        '''


        xml_root = etree.Element('{{{0}}}xliff'.format(nsmap['xliff']),
                                 attrib={'version': '2.1',
                                         'srcLang': src,
                                         'trgLang': trgt},
                                 nsmap={None:nsmap['xliff'], 'kaplan':nsmap['kaplan']})

        etree.SubElement(xml_root,
                         '{{{0}}}file'.format(nsmap['xliff']),
                         attrib={'id':'1'})

        xliff = BytesIO(etree.tostring(xml_root, encoding='UTF-8'))

        if not name.lower().endswith('.xliff'):
            name += '.xliff'
        xliff.name = name

        return cls(xliff)

    @staticmethod
    def prepare_segment(source_segment, target_segment=None):
        source_segment = deepcopy(source_segment)
        if target_segment is not None:
            target_segment = deepcopy(target_segment)

        ids = {}

        source_string = ''
        if source_segment.text is not None:
            source_string += html.escape(source_segment.text)
        for any_child in source_segment.findall('.//'):
            any_child.tag = etree.QName(any_child).localname
            if any_child.attrib.get('id', None) is None:
                if any_child.text is not None:
                    source_string += any_child.text
                continue
            child_id = '-'.join((any_child.tag, any_child.attrib['id']))

            if child_id not in ids:
                ids[child_id] = str(len(ids) + 1)

            source_string += '<' + '-'.join((any_child.tag, ids[child_id])) + '>'

            if any_child.tail is not None:
                source_string += html.escape(any_child.tail)

        target_string = ''
        if target_segment is not None:
            if target_segment.text is not None:
                target_string = html.escape(target_segment.text)
            for any_child in target_segment.findall('.//'):
                any_child.tag = etree.QName(any_child).localname
                if any_child.attrib.get('id', None) is None:
                    if any_child.text is not None:
                        source_string += any_child.text
                    continue
                child_id = '-'.join((any_child.tag, any_child.attrib['id']))

                if child_id not in ids:
                    ids[child_id] = str(len(ids) + 1)

                target_string += '<' + '-'.join((any_child.tag, ids[child_id])) + '>'

                if any_child.tail is not None:
                    target_string += html.escape(any_child.tail)

        return source_string, target_string

    def save(self, output_directory):
        self.xml_root.getroottree().write(os.path.join(output_directory, self.name),
                                          encoding='UTF-8',
                                          xml_declaration=True)

    def submit_segment(self, source_segment, target_segment):
        source_segment, target_segment = self.prepare_segment(etree.fromstring(source_segment), etree.fromstring(target_segment))

        tm_hit = None
        for source_entry in self.xml_root.xpath('.//xliff:source', namespaces=nsmap):
            if source_segment == source_entry.text:
                tm_hit = source_entry.getparent()
                break

        translation_units = self.xml_root[0]

        if tm_hit is None:
            new_translation_unit = etree.SubElement(translation_units,
                                                    '{{{0}}}unit'.format(nsmap['xliff']),
                                                    {'id':str(len(translation_units)+1)})

            new_segment = etree.SubElement(new_translation_unit,
                                          '{{{0}}}segment'.format(nsmap['xliff']),
                                          {'id':str(len(translation_units.xpath('.//xliff:segment', namespaces=nsmap))+1)})

            etree.SubElement(new_segment, '{{{0}}}source'.format(nsmap['xliff'])).text = source_segment
            etree.SubElement(new_segment, '{{{0}}}target'.format(nsmap['xliff'])).text = target_segment

        else:
            tm_hit[1].text = target_segment
