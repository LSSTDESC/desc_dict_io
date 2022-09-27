from .ioUtils import HandlerFactory

def find_version():
    """Find the version"""
    # setuptools_scm should install a
    # file _version alongside this one.
    from . import _version
    return _version.version

try:
    __version__ = find_version()
except ImportError: # pragma: no cover
    __version__ = "unknown"


read_get = HandlerFactory.read_get

get = HandlerFactory.get

write = HandlerFactory.write
