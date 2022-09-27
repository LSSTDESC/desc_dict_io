

class DictIOError(Exception):
    pass


class DictIOFileTypeUnknown(DictIOError):
    pass


class DictIOFileSchemeUnsupported(DictIOError):
    pass


class DictIOMissingFile(DictIOError):
    pass


class DictIOMissingSection(DictIOError):
    pass


class DictIOMissingItem(DictIOError):
    pass
