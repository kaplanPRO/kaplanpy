from datetime import datetime
from pathlib import Path

from lxml import etree
from kaplan import __version__

class TMX:
    def __init__(self, name, xml_root):
        self.name = name
        self.xml_root = xml_root

        datatype = self.xml_root[0].attrib['datatype'].lower()

        assert datatype in ('plaintext','xml'), 'Datatype not supported'


        self.datatype = datatype
        self.srclang = self.xml_root[0].attrib['srclang']

    def add(self, source, target, trgtlang):
        xml_body = self.xml_root[-1]

        xml_tu = etree.SubElement(xml_body,
                                  'tu',
                                  attrib={'creationdate':datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}
                                 )

        xml_source = etree.SubElement(xml_tu,
                                      'tuv',
                                      attrib={'{http://www.w3.org/XML/1998/namespace}lang':self.srclang})

        xml_target = etree.SubElement(xml_tu,
                                      'tuv',
                                      attrib={'{http://www.w3.org/XML/1998/namespace}lang':trgtlang})

        seg_source = etree.fromstring('<seg>' + source + '</seg>')
        xml_source.append(seg_source)
        seg_target = etree.fromstring('<seg>' + target + '</seg>')
        xml_target.append(seg_target)

    def gen_translation_units(self):
        for tu in self.xml_root.xpath('body/tu'):
            yield tu

    @classmethod
    def new(cls, name, srclang, datatype='xml', o_tmf=None):
        xml_root = etree.Element('tmx', attrib={'version':'1.4'})

        xml_header = etree.SubElement(xml_root,
                                      'header',
                                      attrib={'creationtool': 'kaplanpy',
                                              'creationtoolversion': __version__,
                                              'datatype':datatype,
                                              'datatype': 'xml',
                                              'adminlang': srclang,
                                              'srclang': srclang,
                                              'creationdate': datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
                                              }
                                     )

        if o_tmf is not None:
            xml_header.set('o-tmf', o_tmf)

        etree.SubElement(xml_root, 'body')

        return cls(name, xml_root)

    @classmethod
    def open(cls, path):
        name = Path(path).name
        xml = etree.parse(str(path))

        xml_root = xml.getroot()

        return cls(name, xml_root)

    def save(self, directory, name=None):
        if name is None:
            name = self.name
        self.xml_root.getroottree().write(str(Path(directory, name)),
                                          encoding='UTF-8',
                                          xml_declaration=True)
