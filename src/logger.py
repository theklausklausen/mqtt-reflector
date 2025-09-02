import logging
import os


class Logger:

    logger = None
    
    def __init__(self, object: str) -> None:
            loglevel = logging.DEBUG if os.getenv('DEBUG', 'False') == 'True' else logging.INFO
            self.log = logging.getLogger(object)
            self.log.setLevel(level=loglevel)
            self.log.setFormatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            self.info_message(f'{__name__}Logger initialized')

    def debug_message(self, message):
        self.log.debug(message)
        print(message)

    def info_message(self, message):
        self.log.info(message)
        print(message)

    def error_message(self, message):
        self.log.error(message)
        print(message)
        
    def warning_message(self, message):
        self.log.warning(message)
        print(message)
