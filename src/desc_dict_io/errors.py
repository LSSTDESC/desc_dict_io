class DictIOError(Exception):
    pass


class DictIOKeyError(KeyError):
    pass


class DictIOFileTypeUnknown(DictIOError):
    pass


class DictIOFileSchemeUnsupported(DictIOError):
    pass


class DictIOMissingFile(DictIOError):
    pass


class DictIOMissingSection(DictIOKeyError):
    pass


class DictIOMissingItem(DictIOKeyError):
    pass
