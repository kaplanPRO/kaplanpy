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

# Internal Python files
from .version import __version__ as version
from .xliff import XLIFF

class KDB:
    '''
    Kaplan Database file
    .kdb can be either a termbase or a translation memory file.
    '''
    def __init__(self, path_to_kdb, src=None, trgt=None):
        self.conn = sqlite3.connect(path_to_kdb)

        kdb_metadata = self.conn.execute('''SELECT * FROM metadata''').fetchone()

        self.src = kdb_metadata[0]
        self.trgt = kdb_metadata[1]

        if src and trgt and (self.src != src or self.trgt != trgt):
            raise ValueError('Language pair is not a match!')

        if len(kdb_metadata) > 2:
            self.version = tuple(map(int, (kdb_metadata[2].split('-')[0].split('.'))))
        else:
            self.version = (0,0,1)

        self.is_outdated = self.version < tuple(map(int, (version.split('-')[0].split('.'))))

    @staticmethod
    def entry_to_segment(source_or_target_entry, xml_tag, reversed_tags={}, source_segment=None, safe_mode=True):
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
                text_equiv = tag[1:-2]
                tag, tag_id = text_equiv.split('-')

                if tag_id in reversed_tags and source_segment is not None and safe_mode:
                    source_tag = source_segment.xpath('{0}[@id="{1}"]'.format(tag, reversed_tags[tag_id].split('-')[-1]))
                    if source_tag != []:
                        source_tag = deepcopy(source_tag[0])
                        source_tag.tail = None
                        segment.append(source_tag)

                elif not safe_mode:
                    if text_equiv.startswith(('sc', 'sm')):
                        text_equiv = '<' + text_equiv + '>'
                    elif text_equiv.startswith(('ec', 'em')):
                        text_equiv = '</' + text_equiv + '>'
                    else:
                        text_equiv = '<' + text_equiv + '/>'

                    tag_xml = etree.Element(tag,
                                            {'id':tag_id,
                                             'equiv':html.escape(text_equiv)})

                    segment.append(tag_xml)

        return segment

    def export_xliff(self, path_to_xliff):
        path_to_xliff = pathlib.Path(path_to_xliff)
        if path_to_xliff.suffix.lower() != '.xliff':
            path_to_xliff = path_to_xliff.with_suffix('.xliff')

        xliff_xml = etree.Element('xliff',
                                  {'version':'2.1',
                                   'srcLang':self.src,
                                   'trgLang':self.trgt},
                                  {None:'urn:oasis:names:tc:xliff:document:2.1',
                                   'kaplan':'https://kaplan.pro'})

        translation_units = etree.SubElement(xliff_xml,
                                             'file',
                                             {'id':'1'})

        tu_i = 1

        for kdb_entry in self.conn.execute('''SELECT * FROM main''').fetchall():
            if kdb_entry[0] == '' or kdb_entry[1] == '':
                continue
            translation_unit = etree.SubElement(translation_units,
                                                'unit',
                                                {'id':str(tu_i)})

            segment = etree.SubElement(translation_unit,
                                       'segment',
                                       {'id':str(tu_i)})

            source = self.entry_to_segment(kdb_entry[0],
                                           'source',
                                           safe_mode=False)
            segment.append(source)

            target = self.entry_to_segment(kdb_entry[1],
                                           'target',
                                           safe_mode=False)
            segment.append(target)

            tu_i += 1

        xliff = XLIFF(path_to_xliff.name,
                      xliff_xml)

        xliff.save(path_to_xliff.parent)

    def get_all_source_entries(self):
        return [row[0] for row in self.conn.execute('''SELECT source FROM main''').fetchall()]

    def get_entries(self, first_i=None, last_i=None):
        rows = self.conn.execute('''SELECT * FROM main''').fetchall()

        if self.version < (0,10,0):
            rows = tuple((None,) + row[:2] + (None,) + row[2:] for row in rows)

        return rows[first_i:last_i]

    def import_csv(self, path_to_csv, overwrite=True):
        entries = []

        time = str(datetime.datetime.utcnow())
        file_name = pathlib.Path(path_to_csv).name

        with open(path_to_csv, encoding='UTF-8') as csv_file:
            csv_file = csv.DictReader(csv_file)
            for row in csv_file:
                source = row['source']
                target = row['target']
                if source != '' and target != '':
                    entries.append((source.replace('"', '""'),
                                    target.replace('"', '""'),
                                    'imported',
                                    time,
                                    file_name))

        self.submit_entries(entries, overwrite)

    def import_xliff(self, path_to_xliff, overwrite=True):
        entries = []

        time = str(datetime.datetime.utcnow())
        file_name = pathlib.Path(path_to_xliff).name

        xliff = XLIFF.open_bilingualfile(path_to_xliff)

        for tu in xliff.get_translation_units():
            for segment in tu:
                source, tags = self.segment_to_entry(segment[0], {})
                target, _ = self.segment_to_entry(segment[1], tags)

                if target == '':
                    continue

                entries.append((source,
                                target,
                                'imported',
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
        sm.set_seq2(source_entry)

        tm_hits = []

        if self.version >= (0,10,0):
            sql_query = '''SELECT source, target, state, time, submitted_by FROM main'''
        else:
            sql_query = '''SELECT source, target, time, submitted_by FROM main'''

        for tm_entry in self.conn.execute(sql_query).fetchall():
            sm.set_seq1(tm_entry[0])
            if sm.ratio() >= diff:
                segment = etree.Element('segment')

                source = self.entry_to_segment(tm_entry[0], 'source', reversed_tags, source_segment)
                target = self.entry_to_segment(tm_entry[1], 'target', reversed_tags, source_segment)

                if self.version >= (0,10,0):
                    tm_hits.append((sm.ratio(), source, target, tm_entry[2], tm_entry[3], tm_entry[4]))
                else:
                    tm_hits.append((sm.ratio(), source, target, None, tm_entry[2], tm_entry[3]))

        return tm_hits

    def lookup_terms(self, source_segment, diff=0.7, casesensitive=False):
        source_entry, _ = self.segment_to_entry(source_segment)
        source_entry = regex.sub('<[^<>]+>', ' ', source_entry)
        if not casesensitive:
            source_entry = source_entry.lower()
        source_entry = source_entry.split()

        sm = difflib.SequenceMatcher()

        if self.version >= (0,10,0):
            sql_query = '''SELECT source, target, state, time, submitted_by FROM main'''
        else:
            sql_query = '''SELECT source, target, time, submitted_by FROM main'''

        kdb_hits = []
        for kdb_entry in self.conn.execute(sql_query).fetchall():
            if not casesensitive:
                kdb_source_entry = kdb_entry[0].lower().split()
            else:
                kdb_source_entry = kdb_entry[0].split()
            kdb_hits_by_word = []
            for kdb_source_word in kdb_source_entry:
                kdb_source_len = len(kdb_source_word)
                sm.set_seq2(kdb_source_word)
                kdb_hit_ratios = []
                for source_word in source_entry:
                    sm.set_seq1(source_word)
                    kdb_hit_ratios.append(sm.ratio())
                kdb_hits_by_word.append([max(kdb_hit_ratios)*kdb_source_len, kdb_source_len])

            kdb_hit_ratio = sum([word_ratio for word_ratio, word_length in kdb_hits_by_word])/sum([word_length for word_ratio, word_length in kdb_hits_by_word])

            if kdb_hit_ratio >= diff:
                if self.version >= (0,10,0):
                    kdb_hits.append((kdb_hit_ratio, kdb_entry[0], kdb_entry[1], kdb_entry[2], kdb_entry[3], kdb_entry[4]))
                else:
                    kdb_hits.append((kdb_hit_ratio, kdb_entry[0], kdb_entry[1], None, kdb_entry[2], kdb_entry[3]))

        kdb_hits.sort(reverse=True)

        return kdb_hits

    @classmethod
    def new(cls, path_to_kdb, src, trgt):
        if not path_to_kdb.lower().endswith('.kdb'):
            path_to_kdb += '.kdb'

        if pathlib.Path(path_to_kdb).exists():
            raise ValueError('File already exists!')

        conn = sqlite3.connect(path_to_kdb)
        cur = conn.cursor()

        cur.execute('''CREATE TABLE metadata (source TEXT, target TEXT, version TEXT)''')
        cur.execute('''INSERT INTO metadata VALUES (?, ?, ?)''', (src.replace('"', '""'), trgt.replace('"', '""'), version))

        cur.execute('''CREATE TABLE main (id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, target TEXT, state TEXT, time TEXT, submitted_by TEXT)''')

        conn.commit()

        return cls(path_to_kdb)

    def remove_rows(self, rows):
        rows = tuple((row,) for row in rows)

        self.conn.executemany('''DELETE FROM main WHERE id = (?)''', rows)
        self.conn.commit()

    @staticmethod
    def segment_to_entry(source_or_target_segment, tags={}):
        entry = ''

        if source_or_target_segment.text is not None:
            entry += html.escape(source_or_target_segment.text)

        for child in source_or_target_segment:
            child.tag = etree.QName(child).localname
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

        if self.version >= (0,10,0):
            self.conn.executemany('''INSERT INTO main(source, target, state, time, submitted_by) VALUES (?,?,?,?,?)''', entries)
        else:
            entries = (entry[:2] + entry[3:] for entry in entries)
            self.conn.executemany('''INSERT INTO main(source, target, time, submitted_by) VALUES (?,?,?,?)''', entries)

        self.conn.commit()

    def submit_entry(self, source, target, submitted_by=None, state='translated', overwrite=True):
        if target is None or target == '':
            return False

        source = source.replace('"', '""')
        target = target.replace('"', '""')
        if overwrite:
            self.conn.execute('''DELETE FROM main WHERE source=?''', (source,))

        if self.version >= (0,10,0):
            entry = (source,
                     target,
                     state,
                     str(datetime.datetime.utcnow()),
                     submitted_by)

            self.conn.execute('''INSERT INTO main(source, target, state, time, submitted_by) VALUES (?,?,?,?,?)''', entry)
        else:
            entry = (source,
                     target,
                     str(datetime.datetime.utcnow()),
                     submitted_by)

            self.conn.execute('''INSERT INTO main(source, target, time, submitted_by) VALUES (?,?,?,?)''', entry)

        self.conn.commit()

    def submit_segment(self, source, target, submitted_by=None, state='translated', overwrite=True):
        source = etree.fromstring(source)
        for child in source:
            child.tag = etree.QName(child).localname
        source, tags = self.segment_to_entry(source, {})

        target = etree.fromstring(target)
        for child in target:
            child.tag = etree.QName(child).localname
        target, _ = self.segment_to_entry(target, tags)

        self.submit_entry(source, target, submitted_by, state, overwrite)

    def upgrade(self):
        assert self.is_outdated, 'KDB object not outdated.'

        if self.version == (0,0,1):
            self.conn.execute('''ALTER TABLE metadata ADD COLUMN version;''')
            self.conn.execute('''UPDATE metadata SET version="{0}"'''.format(version))
            self.conn.commit()
            all_entries = self.conn.execute('''SELECT * FROM main''').fetchall()
            self.conn.execute('''DROP TABLE main''')
            self.conn.commit()
            self.conn.execute('''CREATE TABLE main (id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, target TEXT, state TEXT, time TEXT, submitted_by TEXT)''')
            self.conn.commit()
            self.conn.executemany('''INSERT INTO main(source, target, time, submitted_by) VALUES (?,?,?,?)''', all_entries)
            self.conn.commit()
        else:
            self.conn.execute('''UPDATE metadata SET version="{0}"'''.format(version))
            self.conn.commit()

        self.version = tuple(map(int, (version.split('-')[0].split('.'))))
        self.is_outdated = False
