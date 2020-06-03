from lxml import etree

from .utils import nsmap

def extract_od(self, p_element, parent_element, paragraph_continues=False):
    '''Extracts paragraph elements in .odp, .ods and .odt files.'''

    span_properties = None

    if p_element.tag == '{{{0}}}span'.format(self.nsmap['text']):
        span_properties = p_element.attrib['{{{0}}}style-name'.format(self.nsmap['text'])]

        if not paragraph_continues:
            self.paragraphs.append([[etree.Element('{{{0}}}run'.format(nsmap['kaplan'])), span_properties]])

            parent_element.replace(p_element, etree.Element('{{{0}}}paragraph'.format(nsmap['kaplan']),
                                                                    no=str(len(self.paragraphs))))

            paragraph_continues = True
        else:
            self.paragraphs[-1].append([etree.Element('{{{0}}}run'.format(nsmap['kaplan'])), span_properties])

            parent_element.remove(p_element)

    if p_element.text is not None:
        if not paragraph_continues:
            self.paragraphs.append([])
            if p_element.tag == '{{{0}}}p'.format(self.nsmap['text']):
                p_element.insert(0, etree.Element('{{{0}}}paragraph'.format(nsmap['kaplan']),
                                                        no=str(len(self.paragraphs))))
            else:
                parent_element.insert(0, etree.Element('{{{0}}}paragraph'.format(nsmap['kaplan']),
                                                                no=str(len(self.paragraphs))))

            paragraph_continues = True

        if span_properties:
            self.paragraphs[-1].append([etree.Element('{{{0}}}run'.format(nsmap['kaplan'])), span_properties])
        else:
            self.paragraphs[-1].append([etree.Element('{{{0}}}run'.format(nsmap['kaplan']))])

        self.paragraphs[-1][-1][0].append(etree.Element('{{{0}}}text'.format(nsmap['kaplan'])))
        self.paragraphs[-1][-1][0][-1].text = p_element.text

        p_element.text = None

    for child_element in p_element:
        if child_element.tag == '{{{0}}}span'.format(self.nsmap['text']):
            if span_properties:
                self.paragraphs[-1][-1][1] = [span_properties, 'Beginning']

            extract_od(self, child_element, p_element, paragraph_continues)

            if span_properties:
                self.paragraphs[-1].append([etree.Element('{{{0}}}run'.format(nsmap['kaplan'])), [span_properties, 'End']])

            paragraph_continues = True

        elif child_element.tag == '{{{0}}}a'.format(self.nsmap['text']):
            hyperlink_tag = child_element.__deepcopy__(True)
            hyperlink_tag.text = None
            for hyperlink_tag_child in hyperlink_tag:
                hyperlink_tag.remove(hyperlink_tag_child)
            hyperlink_tag.tail = None
            hyperlink_tag = etree.tostring(hyperlink_tag)

            if not paragraph_continues:
                self.paragraphs.append([[None, None, hyperlink_tag, 'beginning']])
                p_element.replace(child_element, etree.Element('{{{0}}}paragraph'.format(nsmap['kaplan']),
                                    no=str(len(self.paragraphs))))

                paragraph_continues = True
            else:
                self.paragraphs[-1].append([None, None, hyperlink_tag, 'beginning'])
                p_element.remove(child_element)

            extract_od(self, child_element, p_element, paragraph_continues)

            self.paragraphs[-1].append([None, None, hyperlink_tag, 'end'])

        elif child_element.tag == '{{{0}}}tab'.format(self.nsmap['text']):
            if paragraph_continues:
                self.paragraphs[-1][-1][0].append(etree.Element('{{{0}}}tab'.format(nsmap['kaplan'])))
                p_element.remove(child_element)

        elif child_element.tag == '{{{0}}}line-break'.format(self.nsmap['text']):
            if  paragraph_continues:
                self.paragraphs[-1][-1][0].append(etree.Element('{{{0}}}br'.format(nsmap['kaplan'])))
                p_element.remove(child_element)

        elif child_element.tag == '{{{0}}}s'.format(self.nsmap['text']):
            if paragraph_continues:
                if (len(self.paragraphs[-1][-1][0]) == 0
                or self.paragraphs[-1][-1][0][-1].tag != '{{{0}}}text'.format(nsmap['kaplan'])):
                    self.paragraphs[-1][-1][0].append(etree.Element('{{{0}}}text'.format(nsmap['kaplan'])))
                    self.paragraphs[-1][-1][0][-1].text = ' '
                else:
                    self.paragraphs[-1][-1][0][-1].text += ' '
                p_element.remove(child_element)

        elif child_element.tag == '{{{0}}}frame'.format(self.nsmap['draw']):
            if child_element[0].tag == '{{{0}}}text-box'.format(self.nsmap['draw']):
                for sub_p_element in child_element[0].xpath('text:p', namespaces=self.nsmap):
                    extract_od(self, sub_p_element, child_element, paragraph_continues)
            elif child_element[0].tag == '{{{0}}}image'.format(self.nsmap['draw']):
                image_copy = child_element.__deepcopy__(True)
                image_copy.tail = None
                if paragraph_continues:
                    self.images.append(etree.tostring(image_copy))
                    self.paragraphs[-1].append([etree.Element('{{{0}}}run'.format(nsmap['kaplan']))])
                    self.paragraphs[-1][-1][0].append(etree.Element('{{{0}}}image'.format(self.t_nsmap['kaplan']),
                                                                    no=str(len(self.images)),
                                                                    nsmap=self.t_nsmap))

                    p_element.remove(child_element)

                elif (child_element.tail is not None
                or p_element.find('text:a', self.nsmap) is not None
                or p_element.find('text:span', self.nsmap) is not None
                or p_element.find('text:s', self.nsmap) is not None):
                    self.images.append(etree.tostring(image_copy))
                    self.paragraphs.append([[etree.Element('{{{0}}}run'.format(nsmap['kaplan']))]])
                    self.paragraphs[-1][-1][0].append(etree.Element('{{{0}}}image'.format(self.t_nsmap['kaplan']),
                                                                    no=str(len(self.images)),
                                                                    nsmap=self.t_nsmap))

                    p_element.replace(child_element, etree.Element('{{{0}}}paragraph'.format(nsmap['kaplan']),
                                                                    no=str(len(self.paragraphs))))


                    paragraph_continues = True

        elif child_element.tag == '{{{0}}}custom-shape'.format(self.nsmap['draw']):
            for sub_p_element in child_element.xpath('text:p', namespaces=self.nsmap):
                extract_od(self, sub_p_element, child_element, paragraph_continues)

        elif child_element.tag == '{{{0}}}paragraph'.format(nsmap['kaplan']):
            continue

        else:
            if paragraph_continues:
                self.miscellaneous_tags.append(etree.tostring(child_element))
                if len(self.paragraphs[-1][-1]) != 1:
                    self.paragraphs[-1].append([etree.Element('{{{0}}}run'.format(nsmap['kaplan']))])

                self.paragraphs[-1][-1][0].append(etree.Element('{{{0}}}{1}'.format(nsmap['kaplan'], child_element.tag.split('}')[1]),
                                                                no=str(len(self.miscellaneous_tags))))

                p_element.remove(child_element)

        if child_element.tail is not None:
            if not paragraph_continues:
                self.paragraphs.append([])
                p_element.insert(p_element.index(child_element) + 1, etree.Element('{{{0}}}paragraph'.format(nsmap['kaplan']),
                                        no=str(len(self.paragraphs))))

                paragraph_continues = True

            if span_properties:
                self.paragraphs[-1].append([etree.Element('{{{0}}}run'.format(nsmap['kaplan'])), span_properties])
            else:
                self.paragraphs[-1].append([etree.Element('{{{0}}}run'.format(nsmap['kaplan']))])

            self.paragraphs[-1][-1][0].append(etree.Element('{{{0}}}text'.format(nsmap['kaplan'])))
            self.paragraphs[-1][-1][0][-1].text = child_element.tail

            child_element.tail = None

    else:
        if (len(self.paragraphs[-1]) == 1
        and len(self.paragraphs[-1][0]) == 1
        and len(self.paragraphs[-1][0][0]) == 0):
            self.paragraphs = self.paragraphs[:-1]
