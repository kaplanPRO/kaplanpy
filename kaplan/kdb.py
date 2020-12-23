# Installed libraries
from lxml import etree

# Standard Python libraries
from copy import deepcopy
import csv
import datetime
import difflib
import html
import pathlib
import regex
import sqlite3

class KDB:
    '''
    Kaplan Database file
    .kdb can be either a termbase or a translation memory file.
    '''
    def __init__(self, path_to_kdb, src=None, trgt=None):
        self.conn = sqlite3.connect(path_to_kdb)

        lang_pair = self.conn.execute('''SELECT * FROM metadata''').fetchone()

        self.src = lang_pair[0]
        self.trgt = lang_pair[1]

        if src and trgt and (self.src != src or self.trgt != trgt):
            raise ValueError('Language pair is not a match!')

    @staticmethod
    def entry_to_segment(source_or_target_entry, xml_tag, reversed_tags={}, source_segment=None):
        segment = etree.Element(xml_tag)

        for text, tag in regex.findall('([^<>]+)?(<[^<>\s]+/>)?', source_or_target_entry):
            if text != '':
                if len(segment) == 0:
                    if segment.text is None:
                        segment.text = ''
                    segment.text += html.unescape(text)
                else:
                    if segment[-1].tail is None:
                        segment[-1].tail = ''
                    segment[-1].tail += html.unescape(text)
            if tag != '':
                tag = tag[1:-2]
                tag, tag_id = tag.split('-')

                if tag_id in reversed_tags and source_segment is not None:
                    source_tag = source_segment.xpath('{0}[@id="{1}"]'.format(tag, reversed_tags[tag_id].split('-')[-1]))
                    if source_tag != []:
                        source_tag = deepcopy(source_tag[0])
                        source_tag.tail = None
                        segment.append(source_tag)

        return segment

    def import_csv(self, path_to_csv, overwrite=True):
        entries = []

        time = str(datetime.datetime.utcnow())
        file_name = pathlib.Path(path_to_csv).name

        with open(path_to_csv) as csv_file:
            csv_file = csv.DictReader(csv_file)
            for row in csv_file:
                source = row[self.src]
                target = row[self.trgt]
                if source != '' and target != '':
                    entries.append((source.replace('"', '""'),
                                    target.replace('"', '""'),
                                    time,
                                    file_name))

        self.submit_entries(entries, overwrite)

    def lookup_segment(self, source_segment, diff=0.5):
        source_segment = etree.fromstring(source_segment)
        for child in source_segment:
            child.tag = etree.QName(child).localname

        source_entry, tags = self.segment_to_entry(source_segment, {})

        reversed_tags = {}
        for k in tags:
            reversed_tags[tags[k]] = k

        sm = difflib.SequenceMatcher()
        sm.set_seq1(source_entry)

        tm_hits = []

        for tm_entry in self.conn.execute('''SELECT * FROM main''').fetchall():
            sm.set_seq2(tm_entry[0])
            if sm.ratio() > diff:
                segment = etree.Element('segment')

                source = self.entry_to_segment(tm_entry[0], 'source', reversed_tags, source_segment)
                target = self.entry_to_segment(tm_entry[1], 'target', reversed_tags, source_segment)

                tm_hits.append({'ratio': sm.ratio(),
                                'source': source,
                                'target': target})

        tm_hits.sort(reverse=True)

        return tm_hits

    def lookup_terms(self): # TODO
        pass

    @classmethod
    def new(cls, path_to_kdb, src, trgt):
        if not path_to_kdb.lower().endswith('.kdb'):
            path_to_kdb += '.kdb'

        if pathlib.Path(path_to_kdb).exists():
            raise ValueError('File already exists!')

        conn = sqlite3.connect(path_to_kdb)
        cur = conn.cursor()

        cur.execute('''CREATE TABLE metadata (source, target)''')
        cur.execute('''INSERT INTO metadata VALUES ("{0}", "{1}")'''.format(src.replace('"', '""'), trgt.replace('"', '""')))

        cur.execute('''CREATE TABLE main (source, target, time, submitted_by)''')

        conn.commit()

        return cls(path_to_kdb)

    @staticmethod
    def segment_to_entry(source_or_target_segment, tags={}):
        entry = ''

        if source_or_target_segment.text is not None:
            entry += html.escape(source_or_target_segment.text)

        for child in source_or_target_segment:
            if child.attrib.get('id', None) is None:
                if child.text is not None:
                    entry += child.text
            else:
                child_id = '{0}-{1}'.format(child.tag, child.attrib['id'])
                if child_id not in tags:
                    if child_id[0].lower() == 's':
                        if 'e' + child_id[1:] in tags:
                            child_id = 'e' + child_id[1:]
                        else:
                            tags[child_id] = str(len(tags)+1)
                    elif child_id[0].lower() == 'e':
                        if 's' + child_id[1:] in tags:
                            child_id = 's' + child_id[1:]
                        else:
                            tags[child_id] = str(len(tags)+1)
                    else:
                        tags[child_id] = str(len(tags)+1)
                entry += '<{0}-{1}/>'.format(child.tag, tags[child_id])
            if child.tail is not None:
                entry += html.escape(child.tail)

        return entry, tags

    def submit_entries(self, entries, overwrite=True):
        if overwrite:
            source_entries = ((entry[0],) for entry in entries)
            self.conn.executemany('''DELETE FROM main WHERE source=?''', source_entries)

        self.conn.executemany('''INSERT INTO main VALUES (?,?,?,?)''', entries)

        self.conn.commit()

    def submit_entry(self, source, target, submitted_by=None, overwrite=True):
        source = source.replace('"', '""')
        target = target.replace('"', '""')
        if overwrite:
            self.conn.execute('''DELETE FROM main WHERE source=?''', (source,))

        entry = (source,
                 target,
                 str(datetime.datetime.utcnow()),
                 submitted_by)

        self.conn.execute('''INSERT INTO main VALUES (?,?,?,?)''', entry)

        self.conn.commit()

    def submit_segment(self, source, target, submitted_by=None, overwrite=True):
        source = etree.fromstring(source)
        for child in source:
            child.tag = etree.QName(child).localname
        source, tags = self.segment_to_entry(source, {})

        target = etree.fromstring(target)
        for child in target:
            child.tag = etree.QName(child).localname
        target, _ = self.segment_to_entry(target, tags)

        self.submit_entry(source, target, submitted_by, overwrite)
