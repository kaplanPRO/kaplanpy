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

    def get_translation_units(self, include_segments_wo_id=False):
        translation_units = super().get_translation_units(include_segments_wo_id)
        for tu in translation_units:
            for segment in tu:
                if not segment.attrib.get('id') != 'N/A':
                    continue
                seg_defs = self.xml_root.xpath('.//sdl:seg-defs/sdl:seg[@id="{0}"]'.format(segment.attrib['id']), namespaces={'sdl':self.nsmap['sdl']})[0]
                segment_state = seg_defs.attrib.get('conf', None)
                if segment_state is not None:
                    segment.attrib['state'] = segment_state.lower()

        return translation_units

    def update_segment(self, target_segment, tu_no, segment_no, segment_state, submitted_by):
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
