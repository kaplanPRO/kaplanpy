from .version import __version__

def can_process(input_file):
    '''
    Determines whether kaplan can handle input_file.

    Args:
        input_file: Path to a file.
    '''
    if input_file.lower().endswith(('.docx', '.kxliff', '.odp', '.ods', '.odt', '.po', '.sdlxliff', '.txt', '.xliff')):
        return True
    else:
        return False

def open_bilingualfile(bilingualfile):
    try:
        from .kxliff import KXLIFF
        return KXLIFF.open_bilingualfile(bilingualfile)
    except:
        try:
            from .sdlxliff import SDLXLIFF
            return SDLXLIFF.open_bilingualfile(bilingualfile)
        except:
            try:
                from .xliff import XLIFF
                return XLIFF.open_bilingualfile(bilingualfile)
            except:
                raise TypeError('File not compatible.')
