
import os, sys, shutil, json, logging
import configparser

from constants import PROJECT_ROOT, resolve_path
from exceptions import ConfigLoadError

LOG_LEVEL = {
    'none': logging.NOTSET,
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL
}

class Singleton(type):
    '''Use as metaclass to implement singleton pattern'''

    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class BotConfig(metaclass=Singleton):

    def __init__(self, filename) -> None:
        self.load_config_file(filename)

    def load_config_file(self, filename):
        filepath = resolve_path(filename, force_exists=False)

        if not os.path.isfile(filepath):
            if os.path.isfile(filepath + '.ini'):
                filepath = filepath + '.ini'
            elif os.path.isfile(resolve_path('config/config_template.ini', force_exists=False)):
                shutil.copy(resolve_path('config/config_template.ini'), filepath)
            else:
                raise ConfigLoadError(f'Config file not found: {filepath}')

        try:
            config = configparser.ConfigParser()
            config.read(filepath)

            # bot
            self.bot_prefix = config.get('bot', 'prefix', fallback='$')
            self.bot_title = config.get('bot', 'title', fallback='bot')

            # audio
            self.audio_root = config.get('audio', 'storage_root')
            self.audio_server_storage = config.get('audio', 'server_storage')
            self.audio_common_storage = config.get('audio', 'common_storage')
            self.ffmpeg_exe = config.get('audio', 'ffmpeg', fallback='thisisnotset')
            self.audio_timeout = config.getint('audio', 'timeout_seconds', fallback=8)
            self.outro_timeout = config.getint('audio', 'outro_timeout_seconds', fallback=8)

            # logging
            temp_level = config.get('logging', 'level', fallback='info').lower()
            self.log_level = LOG_LEVEL[temp_level] if temp_level in LOG_LEVEL else logging.INFO
            self.log_name = config.get('logging', 'name', fallback=__name__)
            self.log_stdout = config.getint('logging', 'stdout', fallback=1)

            # storage
            self.storage_dir = config.get('storage', 'dir')


            # checks ============================
            if not os.path.isfile(self.ffmpeg_exe):
                raise ConfigLoadError(f'could not locate FFMPEG\'s executable at {self.ffmpeg_exe}')

            if not os.path.isdir(resolve_path(self.audio_root, force_exists=False)):
                os.mkdir(resolve_path(self.audio_root, force_exists=False))

            if not os.path.isdir(resolve_path(os.path.join(self.audio_root, self.audio_server_storage), force_exists=False)):
                os.mkdir(resolve_path(os.path.join(self.audio_root, self.audio_server_storage), force_exists=False))
            if not os.path.isdir(resolve_path(os.path.join(self.audio_root, self.audio_common_storage), force_exists=False)):
                os.mkdir(resolve_path(os.path.join(self.audio_root, self.audio_common_storage), force_exists=False))

        except Exception as e:
            raise ConfigLoadError(f'Error loading config from {filepath}: {str(e)}')

        