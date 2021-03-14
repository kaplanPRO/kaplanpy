# Installed libraries
from lxml import etree

# Standard Python libraries
import difflib
import json
import os
import zipfile

# Internal Python files
from .kdb import KDB
import kaplan

class Project:
    '''
    A Kaplan project.

    Args:
        project_metadata: Dict with the following attributes:
            title: Title of the project.
            directory: Path to the project directory.
            source_language: ISO 639-1 code for the source language.
            target_language: ISO 639-1 code for the target language.
            files: List of files.
            translation_memories (optional): List of translation memories.
    '''
    def __init__(self, project_metadata):
        self.title = project_metadata['title']
        self.directory = project_metadata['directory']
        self.source_language = project_metadata['source_language']
        self.target_language = project_metadata['target_language']
        self.files = project_metadata['files']
        self.translation_memories = project_metadata.get('translation_memories', {})
        self.termbases = project_metadata.get('termbases', {})
        self.reports = project_metadata.get('reports', {})

    def analyze(self):

        project_entries = []

        project_tm_entries = []
        for tm_i in self.translation_memories:
            project_tm_entries += KDB(self.translation_memories[tm_i]).get_all_source_entries()

        project_report = {}
        project_total = {'Repetitions': 0,
                         '100%': 0,
                         '95%-99%': 0,
                         '85%-94%': 0,
                         '75%-84%': 0,
                         '50%-74%': 0,
                         'New': 0,
                         'Total': 0
                        }

        for file_i in self.files:
            file_report = {'Repetitions': 0,
                           '100%': 0,
                           '95%-99%': 0,
                           '85%-94%': 0,
                           '75%-84%': 0,
                           '50%-74%': 0,
                           'New': 0,
                           'Total': 0
                          }

            for tu in kaplan.open_bilingualfile(self.files[file_i]['targetBF']).get_translation_units():
                for segment in tu:
                    if segment.tag.split('}')[-1] == 'ignorable':
                        continue

                    source_entry, _ = KDB.segment_to_entry(segment[0])
                    word_count = len(source_entry.split())

                    sm = difflib.SequenceMatcher()
                    sm.set_seq2(source_entry)

                    if source_entry in project_entries:
                        file_report['Repetitions'] += word_count
                    elif source_entry in project_tm_entries:
                        file_report['100%'] += word_count
                        project_entries.append(source_entry)
                    else:
                        highest_match = 0.0
                        for entry in project_entries + project_tm_entries:
                            sm.set_seq1(entry)
                            highest_match = max(sm.ratio(), highest_match)

                        if highest_match >= 0.95:
                            file_report['95%-99%'] += word_count
                        elif highest_match >= 0.85:
                            file_report['85%-94%'] += word_count
                        elif highest_match >= 0.75:
                            file_report['75%-84%'] += word_count
                        elif highest_match >= 0.5:
                            file_report['50%-74%'] += word_count
                        else:
                            file_report['New'] += word_count

                        project_entries.append(source_entry)

                    file_report['Total'] += word_count

            project_total['Repetitions'] += file_report['Repetitions']
            project_total['100%'] += file_report['100%']
            project_total['95%-99%'] += file_report['95%-99%']
            project_total['85%-94%'] += file_report['85%-94%']
            project_total['75%-84%'] += file_report['75%-84%']
            project_total['50%-74%'] += file_report['50%-74%']
            project_total['New'] += file_report['New']
            project_total['Total'] += file_report['Total']

            project_report[self.files[file_i]['name']] = file_report

        if len(self.files) > 1:
            project_report['Total'] = project_total

        return project_report

    def export(self, target_path, files_to_export=None, include_source_and_resources=True):
        if not target_path.lower().endswith('.kpp'):
            target_path += '.kpp'

        manifest = {
            'title': self.title,
            'src': self.source_language,
            'trg': self.target_language,
            'files': {},
        }

        with zipfile.ZipFile(target_path, 'w') as project_package:
            for i in self.files:
                if files_to_export and i not in files_to_export:
                    continue
                file_dict = {}

                if include_source_and_resources:
                    source = self.files[i].get('source')
                    if source:
                        file_dict['source'] = '/'.join((self.source_language,
                                                           os.path.basename(source)))
                        project_package.write(source,
                                              file_dict['source'])

                    originalBF = self.files[i]['originalBF']
                    file_dict['originalBF'] = '/'.join((self.source_language,
                                                       os.path.basename(originalBF)))

                    project_package.write(originalBF,
                                          file_dict['originalBF'])

                targetBF = self.files[i]['targetBF']
                file_dict['targetBF'] = '/'.join((self.target_language,
                                                 os.path.basename(targetBF)))

                project_package.write(targetBF,
                                      file_dict['targetBF'])

                manifest['files'][i] = file_dict

            if self.translation_memories != {} and include_source_and_resources:
                manifest['tms'] = {}
                for i in range(len(self.translation_memories)):
                    manifest['tms'][i] = '/'.join(('TM',
                                                  os.path.basename(self.translation_memories[i])))

                    project_package.write(self.translation_memories[i],
                                          manifest['tms'][i])

            if self.termbases != {} and include_source_and_resources:
                manifest['tbs'] = {}
                for i in range(len(self.translation_memories)):
                    manifest['tbs'][i] = '/'.join(('TB',
                                                  os.path.basename(self.termbases[i])))

                    project_package.write(self.termbases[i],
                                          manifest['tbs'][i])

            if self.reports != {}:
                manifest['reports'] = self.reports

            project_package.writestr('manifest.json',
                                     json.dumps(manifest, indent=4))

    @staticmethod
    def extract(project_package, project_directory):
        with zipfile.ZipFile(project_package) as project_package:
            manifest = json.loads(project_package.read('manifest.json'))

            for i in manifest['files']:
                for key in manifest['files'][i]:
                    project_package.extract(manifest['files'][i][key],
                                            project_directory)

            if 'tms' in manifest:
                for i in manifest['tms']:
                    project_package.extract(manifest['tms'][i],
                                            project_directory)

            if 'tbs' in manifest:
                for i in manifest['tbs']:
                    project_package.extract(manifest['tbs'][i],
                                            project_directory)

        return manifest

    @staticmethod
    def extract_target_files(project_package, project_directory, project_files):
        with zipfile.ZipFile(project_package) as project_package:
            manifest = json.loads(project_package.read('manifest.json'))

            for project_file in project_files:
                project_package.extract(manifest['files'][project_file]['targetBF'],
                                        project_directory)

    @staticmethod
    def get_manifest(project_package):
        with zipfile.ZipFile(project_package) as project_package:
            manifest = json.loads(project_package.read('manifest.json'))

        return manifest
