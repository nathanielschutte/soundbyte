
class SoundbyteException(Exception):
    def __init__(self, msg, *args) -> None:
        super().__init__(msg)
        self._msg = msg
    
    @property
    def message(self):
        return self._msg

class FormattedException(SoundbyteException):
    def __init__(self, error, *args, header='Soundbyte error:') -> None:
        self.error = error
        self.header = header
        self.format = '\n{header}\n{error}\n'
    
    @property
    def message(self):
        return self.format.format(header = self.header, error = self.error)

class ConfigLoadError(FormattedException):
    """Raised if config data cannot be loaded"""
    pass

class BotLoadError(FormattedException):
    """Raised if bot is not instantiated properly"""
    pass
