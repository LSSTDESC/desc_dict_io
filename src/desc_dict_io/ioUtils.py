import pickle
import pathlib
import collections
import warnings

from io import TextIOWrapper

from ruamel import yaml

from . import utils
from . import errors
from .types import FileType, get_file_type


class DictHandler:

    @classmethod
    def _read_get(cls, filename, group, item=None, comments_section="comments"):
        """Read one or more items from a file

        Parameters
        ----------
        filename: str
            The file we are reading from

        group: str
            The name of the group we are reading from

        item: tuple(str, str) or None
            The particular item we are reading

        comments_section: str
            Where the comments are stored

        Returns
        -------
        the_dict, comments : dict[tuple[str, str], Any], list[str]
        """
        raise NotImplementedError()

    @classmethod
    def read(cls, filename, group, comments_section="comments"):
        """Read a file into a dictionary and associated list of comments

        Parameters
        ----------
        filename: str
            The file we are reading from

        group: str
            The name of the group we are reading from

        comments_section: str
            Where the comments are stored

        Returns
        -------
        the_dict, comments : dict[tuple[str, str], Any], list[str]
        """
        return cls._read_get(filename, group, item=None, comments_section=comments_section)

    @classmethod
    def get(cls, filename, group, section, key):
        """Read one or more items from a file

        Parameters
        ----------
        filename: str
            The file we are reading from

        group: str
            The name of the group we are reading from

        section : str
            Section header for the item we want

        key: str
            Specific get for the item we want

        Returns
        -------
        value: Any
            The value of the requested item
        """
        return cls._read_get(filename, group, (section, key))

    @classmethod
    def write(cls, the_dict, filename, group, comments=None, comments_section='comments'):
        """
        Write to a file

        Parameters
        ----------
        the_dict: dict
            dictionary to write

        filename: str or writeable object
            File to write to

        group: str
            Where in the file to write the dict

        comments: list[str] | None
            Comments to write along with dict

        comments_section: str
            Where to write the comments
        """
        raise NotImplementedError()



class HdfHandler(DictHandler):

    @classmethod
    def _read_get(cls, filename, group, item=None, comments_section="comments"):

        with utils.open_hdf(filename, "r") as f:
            # If the whole group section is missing, e.g.
            # because the file was not generated with which_group at all,
            # then raise the appropriate error
            if group not in f.keys():
                raise errors.DictIOMissingSection(
                    f"HDF File is missing {group} section"
                )

            # Othewise get the group.  Dict is stored in its
            # attributes of subgroups
            g = f[group]

            # If we are being called from read_hdf then we want to read everything
            if item is None:
                d = {}
                comments = []
                # Go to all the (category) subgroups
                for section in g.keys():
                    sg = g[section]
                    if section == comments_section:
                        for val in sg.attrs.values():
                            comments.append(val)
                    else:
                        # and read all the attributes in each one
                        for key, val in sg.attrs.items():
                            d[section, key] = val
                return d, comments

            # Otherwise just read the one requested item
            section, key = item
            if section not in g.keys():
                raise errors.DictIOMissingItem(f"{section}/{key}")

            # Will be None if not present
            value = g[section].attrs.get(key)
            if value is None:
                raise errors.DictIOMissingItem(item)
            return value

    @classmethod
    def write(cls, the_dict, filename, group, comments=None, comments_section='comments'):

        with utils.open_hdf(filename, "a") as f:
            # Group may or may not exist already
            if group in f.keys():
                g = f[group]
            else:
                g = f.create_group(group)

            # Write each category to a subgroup
            for (section, key), value in the_dict.items():
                # Create subgroup if it does not exist already
                if section not in g.keys():
                    subg = g.create_group(section)
                else:
                    subg = g[section]

                # Write values to subgroup attributes
                subg.attrs[key] = value

            if comments is not None:
                if comments_section not in g.keys():
                    subg = g.create_group(comments_section)
                else:
                    subg = g[comments_section]

                for i, comment in enumerate(comments):
                    subg.attrs[f"comment_{i}"] = comment



class FitsHandler(DictHandler):

    @classmethod
    def _read_get(cls, filename, group, item=None, comments_section="comments"):

        with utils.open_fits(filename, "r") as f:
            try:
                ext = f[group]
            except OSError as err:
                raise errors.DictIOMissingSection(
                    f"Fits file is missing HDU {group}"
                ) from err
            # We may be called from the get or read methods.
            # In the former case we will be given a specific item
            # to get, which we split here
            if item is not None:
                target_sec, target_key = item

            # Read the entire header. A bit wasteful if we only want a single
            # item from it, but this shouldn't be a performance bottleneck.
            hdr = ext.read_header()

            comments = [
                k["value"].strip() for k in hdr.records() if k["name"] == "COMMENT"
            ]

            # Remove sone of the standard FITS comments put in everything
            # by CFITSIO.
            try:
                comments.remove(
                    "FITS (Flexible Image Transport System) format is defined in 'Astronomy"
                )
                comments.remove(
                    "and Astrophysics', volume 376, page 359; bibcode: 2001A&A...376..359H"
                )
            except ValueError:
                pass
            # We have recorded items in trios of KEY0, SEC0, VAL0, 1, 2 etc.
            # so count how many keys we have
            indices = [k[3:] for k in hdr if k.upper().startswith("KEY")]
            indices = [k for k in indices if k and k[0] in "0123456789"]

            # We will collect the number of lines for each multi-line
            # item, so we can patch together later.
            multiline_indices = collections.defaultdict(int)
            d = {}

            # split these keys into multi-line and normal keys
            for index in indices:
                if "_" in index:
                    orig_index, _ = index.split("_", 1)
                    multiline_indices[orig_index] += 1
                else:
                    # Handle the normal keys just by reading them
                    sec = hdr[f"SEC{index}"]
                    val = hdr[f"VAL{index}"]
                    key = hdr[f"KEY{index}"]
                    # If this is called from get_ then return
                    # if we have found the desired object
                    if item is not None:
                        if (sec == target_sec) and (key == target_key):
                            return val
                    # Otherwise just build up all the items
                    else:
                        d[sec, key] = val

            # Now deal with all the multiline ones we found.
            # we recorded the number of entries for each of them
            for index, n in multiline_indices.items():
                vals = []
                # sec and key should be the same for them all
                sec = hdr[f"SEC{index}_0"]
                key = hdr[f"KEY{index}_0"]

                # reassemble into a multi-line text
                for i in range(n):
                    vals.append(hdr[f"VAL{index}_{i}"])
                val = "\n".join(vals)

                # Check if the target is this multiline item
                if item is not None:
                    if (sec == target_sec) and (key == target_key):
                        return val
                else:
                    d[sec, key] = val

            # If we were not asked for a specific item then return
            # the entire thing
            if item is None:
                return d, comments

            # If we were asked for an item then if we've got this far
            # then we've failed.
            raise errors.DictIOMissingItem(
                f"Missing item {target_sec} {target_key}"
            )


    @classmethod
    def write(cls, the_dict, filename, group, comments=None, comments_section="comments"):

        with utils.open_fits(filename, "rw") as f:

            # Create the group if it doesn't exist
            if group in f:
                ext = f[group]
            else:
                f.create_image_hdu(extname=group)
                f.update_hdu_list()
                ext = f[group]

            # Helper local function to write a key.
            # To maintain case we store items as a trio
            # of keys specifying category, key, and value
            def write_key(s, k, v, i):
                ext.write_key(f"SEC{i}", s)
                ext.write_key(f"KEY{i}", k)
                ext.write_key(f"VAL{i}", v)

            # Write the keys we have one by one
            for i, ((section, key), value) in enumerate(the_dict.items()):
                # FITS header items can't contain newlines, so we break up
                # any text with newlines into separate entries which we patch
                # together again when loading
                if isinstance(value, str) and "\n" in value:
                    values = value.split("\n")
                    # There's some kind of bug in CFITSIO that lets you write
                    # but not read certain text that includes new lines when the
                    # key is longer than 8 characters.  This avoids that because
                    # our keys are always shorter than this in this case
                    if len(values) > 999:
                        warnings.warn(
                            f"Cannot write very long item {section}/{key} to FITS (>999 lines).  Truncating."
                        )
                        values = values[:999]
                    for j, v in enumerate(values):
                        write_key(section, key, v, f"{i}_{j}")
                # or if it's any other item we just put it in directly
                else:
                    write_key(section, key, value, i)

            if comments is not None:
                for comment in comments:
                    ext.write_comment(comment)


class YamlHandler(DictHandler):

    @classmethod
    def _make_yml(cls, the_dict, comments, comments_section='comments'):
        # internal method to make a dictionary from
        # this instance suitable to dump to yml
        d = {}
        for (sec, key), val in the_dict.items():
            if sec not in d:
                d[sec] = {}
            d[sec][key] = val
        if comments is not None:
            d[comments_section] = comments[:]
        return d

    @classmethod
    def _read_get(cls, filename, group, item=None, comments_section='comments'):
        y = yaml.YAML()

        with utils.open_file(filename, "r") as f:
            # Read the whole file
            data = y.load(f)
            try:
                d = data[group]
            except KeyError as err:
                raise errors.DictIOMissingSection(
                    f"Yaml file is missing {group} section"
                ) from err
            if item is not None:
                try:
                    return d[item[0]][item[1]]
                except KeyError as err:
                    raise errors.DictIOMissingItem(
                        f"Yaml file is {group} missing {item}"
                    ) from err

            # Pull out the different sections
            # into a dict for provenance and a list
            # for comments
            out = {}
            com = []
            for section, sub in d.items():
                if section == comments_section:
                    com = sub[:]
                else:
                    for key, value in sub.items():
                        out[section, key] = value
            return out, com

    @classmethod
    def write(cls, the_dict, filename, group, comments=None, comments_section='comments'):
        # Create the YAML loader.  The default instance
        # of this preserves comments in the YAML if present,
        # which means we can run this code on existing
        # commented yaml without destroying it
        y = yaml.YAML()

        write_dict = cls._make_yml(the_dict, comments, comments_section)

        if utils.is_path(filename) or "r" in filename.mode:
            with utils.open_file(filename, "r+") as f:

                # record curent position (in case this is a pre-opened file)
                # and load the yaml from the start
                s = f.tell()
                f.seek(0)
                try:
                    d = y.load(f)
                except UnicodeDecodeError:
                    d = None

                # if file was empty before:
                if d is None:
                    d = {}
                elif not isinstance(d, yaml.comments.CommentedMap):
                    # go back to where we started but complain that this is
                    # not a dict-type yaml file
                    f.seek(s)
                    raise errors.DictIOFileSchemeUnsupported(
                        "DictIO only supports yaml files containing a dictionary as the top level object"
                    )

                # replace existing completely if present.  We re-write
                # the whole file contents after the prov.  Could avoid but not really needed
                # as ruamel should maintain comments.
                d[group] = write_dict
                f.seek(0)
                y.dump(d, f)
                f.truncate()
        else:
            # file opened in write-only mpde
            y.dump(write_dict, f)


class PickleHandler(DictHandler):

    @classmethod
    def _read_get(cls, filename, group, item=None, comments_section="comments"):

        #f = utils.open_file(filename, "r")
        #s = f.tell()
        f = open(filename, "rb")
        s = f.tell()

        try:
            n = 0
            while True:
                try:
                    item = pickle.load(f)
                    n += 1
                except Exception:
                    break
            if n == 0:
                raise errors.DictIOError(f"Nothing readable found in file {filename}")
            if (
                (not isinstance(item, list))
                or (len(item) != 3)
                or (item[0] != group)
            ):
                raise errors.DictIOMissingSection(f"No {group} found in file {filename}")
            _, d, c = item
        finally:
            if utils.is_path(filename):
                f.close()
            else:
                f.seek(s)
        return d, c

    @classmethod
    def get(cls, filename, group, section, key):
        d, _com = cls._read_get(filename, group)
        try:
            return d[section, key]
        except KeyError as err:
            raise errors.DictIOMissingItem(f"{section},{key}") from err

    @classmethod
    def write(cls, the_dict, filename, group, comments=None, comments_section='comments'):
        if comments is None:
            comments = []

        if utils.is_path(filename) or "r" in filename.mode:
            with utils.open_pickle(filename, "r+b") as f:
                # jump to the end of the file
                f.seek(0, 2)
                # save the pickle info
                pickle.dump([group, the_dict, comments], f)

        else:
            # filed opened in write-only mode already
            pickle.dump(
                [group, the_dict, comments], filename
            )


class HandlerFactory:

    handlers = {
        FileType.yaml_file: YamlHandler,
        FileType.fits_file: FitsHandler,
        FileType.hdf5_file: HdfHandler,
        FileType.pickle_file: PickleHandler,
    }

    @classmethod
    def get_handler(cls, suffix: str):
        try:
            file_type = get_file_type(suffix)
        except KeyError:
            return None
        return cls.handlers[file_type]

    @classmethod
    def read(cls, filename, group, comments_section="comments"):
        """Read one or more items from a file

        Parameters
        ----------
        filename: str
            The file we are reading from

        group: str
            The name of the group we are reading from

        comments_section:
             Where the comments are stored

        Returns
        -------
        the_dict, comments : dict[tuple[str, str], Any], list[str]
        """
        if isinstance(filename, TextIOWrapper):
            p = pathlib.Path(filename.name)
        else:
            p = pathlib.Path(filename)

        handler = cls.get_handler(p.suffix)

        if handler is None:
            handler = YamlHandler
            filename = p.parent / (p.name + ".provenance.yaml")

        return handler.read(filename, group, comments_section=comments_section)

    @classmethod
    def get(cls, filename, group, section, key):
        """Read one or more items from a file

        Parameters
        ----------
        filename: str
            The file we are reading from

        group: str
            The name of the group we are reading from

        section : str
            Section header for the item we want

        key: str
            Specific get for the item we want

        Returns
        -------
        value: Any
            The value of the requested item
        """

        p = pathlib.Path(filename)
        if not p.exists():
            raise errors.DictIOMissingFile(filename)

        handler = cls.get_handler(p.suffix)
        if handler is None:
            raise errors.DictIOFileTypeUnknown(filename)
        return handler.get(filename, group, section, key)

    @classmethod
    def write(cls, the_dict, f, group, comments=None, comments_section='comments', suffix=None):
        """
        Write dict to a named file, guessing the file type from its suffix.

        Parameters
        ----------
        the_dict: dict
            dictionary to write

        f: str or writeable object
            File to write to

        group: str
            Where in the file to write the dict

        comments: list[str] | None
            Comments to write along with dict

        comments_section: str
            Where to write the comments

        suffix: str
            Must be supplied if f is a file-like object
        """
        # String or path
        if utils.is_path(f):
            f = pathlib.Path(f)
            suffix = f.suffix
        elif suffix is None:
            raise ValueError("Must supply suffix if open file is supplied")

        # If passed a directory, make a provenance file in that directory
        if suffix == "" and isinstance(f, pathlib.Path) and f.is_dir():
            p = f.parent / (f.name + f".{group}.yaml")
            return YamlHandler.write(the_dict, p, group, comments=comments, comments_section=comments_section)

        if suffix and not suffix.startswith("."):
            suffix = "." + suffix

        handler = cls.get_handler(suffix)

        # If we do not know how to write to this file type
        # then just put a file next to it.
        if handler is None:
            p = f.parent / (f.name + f".{group}.yaml")
            return YamlHandler.write(the_dict, p, group, comments=comments, comments_section=comments_section)

        return handler.write(the_dict, f, group, comments=comments, comments_section=comments_section)


read = HandlerFactory.read

get = HandlerFactory.get

write = HandlerFactory.write
