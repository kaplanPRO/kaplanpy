# Installed libraries
from lxml import etree

# Standard Python libraries
import json
import os
import zipfile

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
