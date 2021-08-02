import os
import random
import regex
import string

def remove_dir(path_to_dir):
    '''Removes a non-empty dir.'''

    for root, dirs, files in os.walk(path_to_dir, topdown=False):
        for target_file in files:
            os.remove(os.path.join(root, target_file))
        os.rmdir(root)

def split_into_sentences(text_unit: string):
    _regex = (regex.compile(r'(\s+|^)'
                            r'(\p{Lu}\p{L}{0,3})'
                            r'(\.+)'
                            r'(\s+|$)'),
              regex.compile(r'(\s+|^)'
                            r'([\p{Lu}\p{L}]+)'
                            r'([\.\!\?\:]+)'
                            r'(\s+|$)'))

    placeholders = ['placeholder_to_keep_segment_going',
                    'placeholder_to_end_segment']
    while placeholders[0] in text_unit:
        placeholders[0] += random.choice(string.ascii_letters)
    while placeholders[1] in text_unit:
        placeholders[1] += random.choice(string.ascii_letters)

    for hit in regex.findall(_regex[0], text_unit):
        if hit is not None:
            text_unit = regex.sub(regex.escape(''.join(hit)),
                                  ''.join((hit[0],
                                           hit[1],
                                           hit[2],
                                           placeholders[0],
                                           hit[3])),
                                  text_unit,
                                  1)

    for hit in regex.findall(_regex[1], text_unit):
        if hit is not None and hit[-1] != '':
            text_unit = regex.sub(regex.escape(''.join(hit)),
                                  ''.join((hit[0],
                                           hit[1],
                                           hit[2],
                                           placeholders[1])),
                                  text_unit,
                                  1)

    text_unit = regex.sub(placeholders[0], '', text_unit)

    return text_unit.split(placeholders[1])
