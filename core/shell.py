import logging
import re
import subprocess
import sys
import os
from threading import Thread
from os.path import expandvars

logger = logging.getLogger(__name__)


class LogPipe(Thread):

    def __init__(self, level: int):
        super().__init__()
        self.daemon = False
        self.level = level
        self.fdRead, self.fdWrite = os.pipe()
        self.pipeReader = os.fdopen(self.fdRead)
        self.start()

    def __enter__(self, *args, **kwargs):
        return self

    def __exit__(self, *args, **kwargs):
        return self.close()

    def fileno(self):
        return self.fdWrite

    def run(self):
        for line in iter(self.pipeReader.readline, ''):
            logger.log(self.level, line.strip('\n'))
        self.pipeReader.close()

    def close(self):
        os.close(self.fdWrite)


class Shell:

    @staticmethod
    def to_str(*args: str):
        arr = []
        for a in args:
            if " " in a or "!" in a:
                a = "'" + a + "'"
            arr.append(a)
        return " ".join(arr)

    @staticmethod
    def expandvars(*args):
        arr = []
        for a in args:
            if isinstance(a, str):
                a = expandvars(a)
            arr.append(a)
        return tuple(arr)

    @staticmethod
    def run(*args: str, expand=False, **kwargs) -> int:
        logger.info("$ " + Shell.to_str(*args))
        if expand:
            args = Shell.expandvars(*args)
        out = subprocess.call(args, **kwargs)
        if out != 0:
            logger.error("# exit code %s", out)
        return out

    @staticmethod
    def safe_get(*args, **kwargs) -> int:
        try:
            return Shell.get(*args, **kwargs)
        except subprocess.CalledProcessError:
            pass
        return None

    @staticmethod
    def get(*args: str, expand=True, **kwargs) -> str:
        logger.info("$ " + Shell.to_str(*args))
        if expand:
            args = Shell.expandvars(*args)
        with LogPipe(logging.ERROR) as logpipe:
            output = subprocess.check_output(args, stderr=logpipe)
        text: str = output.decode(sys.stdout.encoding)
        lines = len(list(ln for ln in re.split(r"\s+", text) if ln.strip()))
        logging.debug("> %s lines", lines)
        return text
