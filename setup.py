import setuptools

from kaplan.version import __version__

with open('README.md', 'r') as input_file:
    long_description = input_file.read()

setuptools.setup(
    name='kaplan',
    version=__version__,
    author='Çağatay Onur Şengör',
    author_email='contact@csengor.com',
    description='A computer-assisted translation tool package',
    keywords = ['CAT', 'computer-assisted translation', 'computer-aided translation', 'translation', 'free-to-use'],
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/kaplanPRO/kaplanpy',
    project_urls = {
        'Kaplan Desktop': 'https://sourceforge.net/projects/kaplan-desktop',
        'Kaplan Homepage': 'https://kaplan.pro',
    },
    packages=setuptools.find_packages(),
    install_requires=[
        'lxml',
        'regex'
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
    ],
)
