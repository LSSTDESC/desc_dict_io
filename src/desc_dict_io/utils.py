import os
import pathlib
import contextlib
import shutil


def is_path(p):
    """
    Decide whether the input is likely to be a path instead of a file object.

    Returns True if the parameter is a pathlib.Path object or a string, False
    otherwise

    Parameters
    ----------
    p: Any
        Object which may be a path or not

    Returns
    -------
    bool

    """
    return isinstance(p, (str, pathlib.Path))


@contextlib.contextmanager
def open_hdf(hdf_file, mode):
    """Open an HDF file, or if a file is provided, simply return it"""
    import h5py  # pylint: disable=import-outside-toplevel

    if is_path(hdf_file):
        f = h5py.File(hdf_file, mode)
        try:
            yield f
        finally:
            f.close()
    else:
        yield hdf_file


@contextlib.contextmanager
def open_fits(fits_file, mode):
    """Open a FITS file, or if a file is already provided simply return it"""
    import fitsio  # pylint: disable=import-outside-toplevel

    if is_path(fits_file):
        exists = os.path.exists(fits_file)

        # By default the "w" mode in FITSIO is r/w.  We have to explicitly remove
        # first if we want to do a proper write and the file already exists.
        if mode == "w":
            mode = "rw"
            if exists:
                shutil.remove(fits_file)
        f = fitsio.FITS(fits_file, mode=mode)

        try:
            yield f
        finally:
            f.close()
    else:
        yield fits_file


@contextlib.contextmanager
def open_file(file, mode):
    """Open a regular file, or if a file is already provided simply return it"""

    if is_path(file):
        if mode in ["r+"] and not os.path.exists(file):
            f = open(file, "w+", encoding="utf-8")
        else:
            f = open(file, mode=mode, encoding="utf-8")

        try:
            yield f
        finally:
            f.close()
    else:
        yield file


@contextlib.contextmanager
def open_pickle(file, mode):
    """Open a regular file, or if a file is already provided simply return it"""

    if is_path(file):
        if mode in ["r+b"] and not os.path.exists(file):
            f = open(file, "w+b")
        else:
            f = open(file, mode=mode, encoding="utf-8")

        try:
            yield f
        finally:
            f.close()
    else:
        yield file
