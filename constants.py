
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# locate config file
CONFIG_FILE = 'config.ini'

# store info per guild
COL_GUILD = 'guild'

# prefix the collection name
COL_SOUNDS = 'soundbit'

# global suffix
COL_GLOBAL = 'global'

# only consider these file types
AUDIO_FILE_TYPES = ['mpeg']

# save files to this extension
AUDIO_FILE_EXT = 'mp3'

# admin
GOD_IDS = [
    '239605736030601216', # nate
    '191575768801869824', # christian
    '176417915975761920', # chris
    '275052217931792384'  # pat
]

def resolve_path(path, force_exists=True):
    '''If filename is not found, check if it exists relative to project root'''

    if os.path.exists(path):
        return path
    
    if not force_exists or os.path.exists(os.path.join(PROJECT_ROOT, path)):
        return os.path.join(PROJECT_ROOT, path)
    else:
        raise IOError('Could not find: {}'.format(os.path.join(PROJECT_ROOT, path)))
