__version__ = '0.16.0'

def can_process(input_file):
    '''
    Determines whether kaplan can handle input_file.

    Args:
        input_file: Path to a file.
    '''
    if input_file.lower().endswith(('.docx', '.json', '.kxliff', '.odp', '.ods', '.odt', '.po', '.sdlxliff', '.txt', '.xliff')):
        return True
    else:
        return False

def open_bilingualfile(bilingualfile):
    '''
    Opens a compatible xliff variant.

    Args:
        bilingualfile: Path to a .kxliff, .xliff, or .sdlxliff file.
    '''
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
