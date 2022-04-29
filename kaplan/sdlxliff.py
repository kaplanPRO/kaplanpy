# Installed libraries
from lxml import etree

# Standard Python libraries
import datetime

# Internal Python files
from .xliff import XLIFF

class SDLXLIFF(XLIFF):
    def __init__(self, name, xml_root):
        if not name.lower().endswith('.sdlxliff') or 'sdl' not in xml_root.nsmap:
            raise TypeError('This class may only handle .sdlxliff files.')
        super().__init__(name, xml_root)

    def gen_translation_units(self, include_segments_wo_id=False):
        '''
        Returns a Python generator object containing translation units.
        '''
        for translation_unit in super().gen_translation_units(include_segments_wo_id):
            for segment in translation_unit:
                if not include_segments_wo_id and segment.attrib.get('id') == 'N/A':
                    continue
                seg_defs = self.xml_root.xpath('.//sdl:seg-defs/sdl:seg[@id="{0}"]'.format(segment.attrib['id']), namespaces={'sdl':self.nsmap['sdl']})[0]
                segment_state = seg_defs.attrib.get('conf', None)
                segment_lock = seg_defs.attrib.get('locked', 'false').lower() == 'true'
                if segment_state is not None:
                    segment.attrib['state'] = segment_state.lower()
                    if segment_lock:
                        segment.attrib['state'] += '-locked'
                elif segment_lock:
                    segment.attrib['state'] = 'locked'

            yield translation_unit

    def get_translation_units(self, include_segments_wo_id=False):
        '''
        Returns a list of all translation units.
        '''
        translation_units = etree.Element('translation-units')

        for translation_unit in self.gen_translation_units(include_segments_wo_id):
            translation_units.append(translation_unit)

        return translation_units

    def set_segment_lock(self, segment_no, lock=True):
        '''
        Sets the lock status for a segment

        Args:
            segment_no (str or int): The number of the segment.
            lock (bool): Whether the segment should be locked.
        '''
        segment_details = self.xml_root.xpath('.//sdl:seg[@id="{0}"]'.format(segment_no), namespaces={'sdl':self.nsmap['sdl']})[0]
        if lock:
            segment_details.attrib['locked'] = 'true'
        else:
            segment_details.attrib.pop('locked', None)

    def update_segment(self, target_segment, tu_no, segment_no, segment_state, submitted_by):
        '''
        Updates a target segment.
        '''
        super().update_segment(target_segment, tu_no, segment_no)

        if segment_no is None:
            return

        segment_details = self.xml_root.xpath('.//sdl:seg[@id="{0}"]'.format(segment_no), namespaces={'sdl':self.nsmap['sdl']})[0]
        if segment_state.lower() == 'blank':
            segment_details.attrib.pop('conf', None)
        else:
            segment_details.attrib['conf'] = segment_state[0].upper() + segment_state[1:].lower()

        if segment_details.xpath('sdl:value[@key="created_on"]', namespaces={'sdl':self.nsmap['sdl']}) == []:
            segment_details_modified_on = etree.SubElement(segment_details,
                                                           '{{{0}}}value'.format(self.nsmap['sdl']),
                                                           {'key': 'created_on'})
        else:
            segment_details_modified_on = segment_details.xpath('sdl:value[@key="modified_on"]', namespaces={'sdl':self.nsmap['sdl']})
            if segment_details_modified_on == []:
                segment_details_modified_on = etree.SubElement(segment_details,
                                                               '{{{0}}}value'.format(self.nsmap['sdl']),
                                                               {'key': 'modified_on'})
            else:
                segment_details_modified_on = segment_details_modified_on[0]
        segment_details_modified_on.text = datetime.datetime.utcnow().strftime('%m/%d/%Y %H:%M:%S')

        if segment_details.xpath('sdl:value[@key="created_by"]', namespaces={'sdl':self.nsmap['sdl']}) == []:
            segment_details_last_modified_by = etree.SubElement(segment_details,
                                                                '{{{0}}}value'.format(self.nsmap['sdl']),
                                                                {'key': 'created_by'})
        else:
            segment_details_last_modified_by = segment_details.xpath('sdl:value[@key="last_modified_by"]', namespaces={'sdl':self.nsmap['sdl']})
            if segment_details_last_modified_by == []:
                segment_details_last_modified_by = etree.SubElement(segment_details,
                                                                    '{{{0}}}value'.format(self.nsmap['sdl']),
                                                                    {'key': 'last_modified_by'})
            else:
                segment_details_last_modified_by = segment_details_last_modified_by[0]
        segment_details_last_modified_by.text = submitted_by
