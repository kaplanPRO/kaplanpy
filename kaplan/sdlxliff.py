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

    def update_segment(self, segment_state, target_segment, tu_no, segment_no, submitted_by):
        super().update_segment(target_segment, tu_no, segment_no)

        segment_details = self.xml_root.xpath('.//sdl:seg[@id="{0}"]'.format(segment_no), namespaces={'sdl':self.nsmap['sdl']})[0]
        segment_details_modified_on = segment_details.xpath('sdl:value[@key="modified_on"]', namespaces={'sdl':self.nsmap['sdl']})
        if segment_details_modified_on == []:
            segment_details_modified_on = etree.SubElement(segment_details,
                                                           '{{{0}}}value'.format(self.nsmap['sdl']),
                                                           {'key': 'modified_on'})
        else:
            segment_details_modified_on = segment_details_modified_on[0]
        segment_details_modified_on.text = str(datetime.datetime.utcnow())
        segment_details_last_modified_by = segment_details.xpath('sdl:value[@key="last_modified_by"]', namespaces={'sdl':self.nsmap['sdl']})
        if segment_details_last_modified_by == []:
            segment_details_last_modified_by = etree.SubElement(segment_details,
                                                                '{{{0}}}value'.format(self.nsmap['sdl']),
                                                                {'key': 'last_modified_by'})
        else:
            segment_details_last_modified_by = segment_details_last_modified_by[0]
        segment_details_last_modified_by.text = submitted_by
