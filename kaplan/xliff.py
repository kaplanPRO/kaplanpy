# Installed libraries
from lxml import etree
import regex

# Standard Python libraries
from copy import deepcopy
from datetime import datetime
import difflib
import html
from pathlib import Path

nsmap = {
    'xliff': 'urn:oasis:names:tc:xliff:document:2.1',
    'xml': 'http://www.w3.org/XML/1998/namespace'
}

class XLIFF:
    '''
    XML Localisation File

    Args:
        name: Name of the file
        xml_root: The xml root of the file
    '''
    def __init__(self, name, xml_root):
        self.name = name
        self.xml_root = xml_root

        self.xliff_version = float(self.xml_root.attrib['version'])
        self.nsmap = self.xml_root.nsmap

    def gen_translation_units(self, include_segments_wo_id=True):
        '''
        Returns a Python generator object containing translation units.
        '''
        if self.xliff_version >= 2.0:
            for translation_unit in self.xml_root.findall('.//unit', self.nsmap):
                _translation_unit = deepcopy(translation_unit)
                _translation_unit.tag = 'translation-unit'
                _tu_notes = _translation_unit.find('notes', self.nsmap)
                _tu_lqi = _translation_unit.find('kaplan:locQualityIssues', {'kaplan':self.nsmap.get('kaplan',None)})
                for _child in _translation_unit:
                    if not _child.tag.endswith(('}segment', '}ignorable')):
                        _translation_unit.remove(_child)
                        continue
                    _child.attrib['state'] = _child.attrib.get('subState', _child.attrib.get('state', 'initial-blank'))
                    _child.attrib.pop('subState', None)
                for _any_child in _translation_unit.findall('.//'):
                    if 'equiv' in _any_child.attrib:
                        _any_child.text = html.unescape(_any_child.attrib['equiv'])

                if _tu_notes is not None or _tu_lqi is not None:
                    for _segment in _translation_unit.findall('segment', self.nsmap):
                        segment_misc = []
                        if _tu_notes is not None:
                            for note in _tu_notes.xpath('xliff:note[@state="open" and @segment="{0}"]'.format(_segment.attrib.get('id')), namespaces={'xliff': self.nsmap[None]}):
                                segment_misc.append((datetime.fromisoformat(note.attrib.get('added_at')), note))
                        if _tu_lqi is not None:
                            for lqi in _tu_lqi.xpath('kaplan:locQualityIssue[@segment="{0}"]'.format(_segment.attrib.get('id')), namespaces={'kaplan':self.nsmap.get('kaplan', None)}):
                                if lqi.attrib.get('resolved'):
                                    continue
                                lqi.tag = 'lqi'
                                segment_misc.append((datetime.fromisoformat(lqi.attrib.get('added_at')), lqi))
                        if len(segment_misc) > 0:
                            _segment_misc = etree.Element('misc')
                            for time, misc in sorted(segment_misc):
                                if misc.text is None:
                                    misc.text = ''
                                _segment_misc.append(misc)
                            _segment.append(_segment_misc)
                etree.cleanup_namespaces(_translation_unit)

                yield _translation_unit
        else:
            for translation_unit in self.xml_root.findall('.//trans-unit', self.nsmap):
                segments = []
                if translation_unit.find('seg-source//mrk[@mtype="seg"]', self.nsmap) is not None:
                    for source_segment in translation_unit.findall('seg-source//mrk[@mtype="seg"]', self.nsmap):
                        target_segment = translation_unit.find('target//mrk[@mid="{0}"]'.format(source_segment.attrib['mid']), self.nsmap)

                        segments.append([source_segment, target_segment])
                elif translation_unit.find('seg-source', self.nsmap) is not None and include_segments_wo_id:
                    for source_segment in translation_unit.findall('seg-source', self.nsmap):
                        target_segment = translation_unit.find('target', self.nsmap)

                        segments.append([source_segment, target_segment])
                elif translation_unit.find('source', self.nsmap) is not None and include_segments_wo_id:
                    segments.append([translation_unit.find('source', self.nsmap), translation_unit.find('target', self.nsmap)])


                _translation_unit = etree.Element('translation-unit', translation_unit.attrib)
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
                                _b_g_tag = etree.Element('g', _any_child.attrib)
                                _e_g_tag = deepcopy(_b_g_tag)

                                _b_g_tag.text = '<g-{0}>'.format(_any_child.attrib['id'])
                                _e_g_tag.text = '</g-{0}>'.format(_any_child.attrib['id'])

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

                etree.cleanup_namespaces(_translation_unit)

                yield _translation_unit

    def get_translation_units(self, include_segments_wo_id=True):
        '''
        Returns a list of all translation units.
        '''
        translation_units = etree.Element('translation-units')

        for translation_unit in self.gen_translation_units(include_segments_wo_id):
            translation_units.append(translation_unit)

        return translation_units

    def merge_segments(self, *args):
        raise TypeError('This function is available for the kxliff.KXLIFF class only.')

    @classmethod
    def open_bilingualfile(cls, bilingualfile):
        '''
        Opens an .xliff file.
        '''
        xml_root = etree.parse(bilingualfile).getroot()

        name = Path(bilingualfile).name

        return cls(name, xml_root)

    def save(self, output_directory):
        '''
        Saves the bilingual file in a given directory.
        '''
        self.xml_root.getroottree().write(str(Path(output_directory, self.name)),
                                          encoding='UTF-8',
                                          xml_declaration=True)

    def set_segment_lock(self, segment_no, lock=True):
        '''
        Sets the lock status for a segment

        Args:
            segment_no (str or int): The number of the segment.
            lock (bool): Whether the segment should be locked.
        '''
        if self.xliff_version >= 2.0:
            segment = self.xml_root.find('.//segment[@id="{0}"]'.format(segment_no), self.nsmap)
            if segment is None:
                raise ValueError('Segment #{} does not exists.'.format(segment_no))
            cur_substate = segment.attrib.get('subState', segment.attrib.get('state', 'initial-blank'))
            is_locked = cur_substate.lower().endswith('-locked')
            if (lock and is_locked) or (not lock and not is_locked):
                pass
            elif lock and not is_locked:
                segment.attrib['subState'] = cur_substate + '-locked'
            elif not lock and is_locked:
                segment.attrib['subState'] = cur_substate[:-7]
        else:
            segment = self.xml_root.find('.//target//mrk[@mid="{0}"][@mtype="seg"]'.format(segment_no), self.nsmap)
            if segment is None:
                raise ValueError('Segment #{} does not exists.'.format(segment_no))
            cur_state = segment.attrib.get('state', 'new')
            is_locked = cur_state.lower().startswith('x-locked')
            if (lock and is_locked) or (not lock and not is_locked):
                pass
            elif lock and not is_locked:
                segment.attrib['state'] = 'x-locked-' + cur_state
            elif not lock and is_locked:
                segment.attrib['state'] = cur_state[9:]

    def update_segment(self, target_segment, tu_no, segment_no=None, segment_state=None, submitted_by=None):
        '''
        Updates a target segment.

        Args:
            target_segment (str): Target segment in HTML.
            tu_no (str or int): The number of the translation unit .
            segment_no (str or int) (optional): The number of the segment. Segments
                                                that make up the entire tu do not have numbers.
            segment_state (str) (optional): The state of the segment (ie. translated, signed-off, etc.).
            submitted_by (str) (optional): Username or ID of the segment author.
        '''

        target_segment = etree.fromstring(target_segment)

        assert etree.QName(target_segment).localname == 'target'

        segment = None
        if self.xliff_version >= 2.0:
            translation_unit = self.xml_root.find('.//unit[@id="{0}"]'.format(tu_no), self.nsmap)
            if segment_no:
                segment = translation_unit.find('segment[@id="{0}"]'.format(segment_no), self.nsmap)
            else:
                segment = translation_unit.find('segment', self.nsmap)

            attribute = 'subState'
        else:
            translation_unit = self.xml_root.find('.//trans-unit[@id="{0}"]'.format(tu_no), self.nsmap)
            if segment_no:
                segment = translation_unit.find('target//mrk[@mid="{0}"][@mtype="seg"]'.format(segment_no), self.nsmap)
            else:
                segment = translation_unit.find('target//mrk[@mtype="seg"]', self.nsmap)

            attribute = 'state'

        if segment is None:
            raise ValueError('Segment does not exist.')

        assert 'locked' not in segment.attrib.get(attribute, ''), 'Segment is locked.'

        segment_substate = None
        if segment_state:
            segment_state = segment_state.lower()
            if self.xliff_version >= 2.0:
                if segment_state == 'blank':
                    segment_state = 'initial'
                    segment_substate = 'initial-blank'
                elif segment_state == 'draft':
                    segment_state = 'initial'
                    segment_substate = 'initial-draft'
                elif segment_state in ('translated', 'reviewed'):
                    segment_substate = segment_state
                else:
                    segment_substate = segment_state
                    segment_state = None

            else:
                if segment_state not in ('new', 'translated', 'signed-off'):
                    segment_state = 'x-{}'.format(segment_state)

        for any_child in target_segment:
            if 'dataref' in any_child.attrib:
                any_child.attrib['dataRef'] = any_child.attrib.pop('dataref')

            any_child.attrib.pop('contenteditable', None)
            any_child.attrib.pop('draggable', None)

        if self.xliff_version < 2.0:
            active_g_tags = []
            for any_child in target_segment:
                any_child_tag = etree.QName(any_child).localname
                if any_child_tag not in ('g', 'x', 'bx', 'ex', 'bpt', 'ept', 'ph', 'it', 'mrk'):
                    raise ValueError('Target has unrecognized child: {}'.format(any_child_tag))

                if any_child_tag == 'g':
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
                child_tag = etree.QName(child).localname
                if child_tag not in ('ec', 'sc', 'ph'):
                    raise ValueError('Target has unrecognized child: {}'.format(child_tag))
                child.tag = '{{{0}}}{1}'.format(self.nsmap[None], child_tag)

        _target_segment = deepcopy(target_segment)

        if self.xliff_version >= 2.0:
            _translation_unit = self.xml_root.find('.//unit[@id="{0}"]'.format(tu_no), self.nsmap)

            if segment_no is not None:
                _segment = _translation_unit.find('segment[@id="{0}"]'.format(segment_no), self.nsmap)
            else:
                _segment = _translation_unit.findall('segment', self.nsmap)[0]

            if segment_state and submitted_by:
                _segment.attrib['state'] = segment_state
                _segment.attrib['subState'] = segment_substate
                _segment.attrib['modified_on'] = datetime.utcnow().isoformat()
                _segment.attrib['modified_by'] = submitted_by

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
            if segment_state and submitted_by:
                _target_segment.attrib['state'] = segment_state
                _target_segment.attrib['modified_on'] = datetime.utcnow().isoformat()
                _target_segment.attrib['modified_by'] = submitted_by

            if segment_no is not None:
                _segment = _translation_unit.find('target//mrk[@mid="{0}"]'.format(segment_no), self.nsmap)
                _target_segment.tag = '{{{0}}}mrk'.format(self.nsmap[None])
                _target_segment.attrib['mtype'] = 'seg'
                _target_segment.attrib['mid'] = str(segment_no)
            else:
                _segment = _translation_unit.find('target', self.nsmap)
                _target_segment.tag = '{{{0}}}target'.format(self.nsmap[None])

            _segment.getparent().replace(_segment, _target_segment)
