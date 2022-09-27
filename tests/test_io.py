import tempfile
from dict_io import ioUtils, utils, errors

from pprint import pprint
import pytest
import datetime
import os
import random
import string
import h5py


@pytest.mark.parametrize(
    "file_type, opener", [
        ("hdf", utils.open_hdf),
        ("yml", utils.open_file),
        ("fits", utils.open_fits),
        ("pkl", utils.open_file),
    ]
)
def test_new(file_type, opener):
    p = {}
    p["sec", "aaa"] = "xxx"
    p["sec", "bbb"] = 123
    p["sec", "ccc"] = 3.14
    p["sec", "ddd"] = "cat"
    p["sec", "eee"] = 4.14

    with tempfile.TemporaryDirectory() as dirname:
        fname = os.path.join(dirname, f"test.{file_type}")
        file_id = ioUtils.write(p, fname, "provenance")

        assert os.path.exists(fname)

        q, _com = ioUtils.read_get(fname, "provenance")

        print(q)
        assert q["sec", "aaa"] == "xxx"
        assert q["sec", "bbb"] == 123
        assert q["sec", "ccc"] == 3.14

        # check the direct getter class methods work
        assert ioUtils.get(fname, "provenance", "sec", "ddd") == "cat"
        assert ioUtils.get(fname, "provenance", "sec", "eee") == 4.14

        with opener(fname, "r") as fin:
            assert fin
            with opener(fin, "r") as f2in:
                assert f2in

        with pytest.raises(errors.DictIOMissingFile):
            ioUtils.get(f"no_file.{file_type}", "missing", "sec", "ddd")
        with pytest.raises(errors.DictIOFileTypeUnknown):
            ioUtils.get("tests/test_io.py", "missing", "sec", "ddd")
        with pytest.raises(errors.DictIOMissingSection):
            ioUtils.get(fname, "missing", "sec", "ddd")
        with pytest.raises(errors.DictIOMissingSection):
            ioUtils.get(fname, "missing", "sec", "ddd")
        with pytest.raises(errors.DictIOMissingItem):
            ioUtils.get(fname, "provenance", "bob", "ddd")
        with pytest.raises(errors.DictIOMissingItem):
            ioUtils.get(fname, "provenance", "sec", "xxx")


                
def test_new_fits():
    file_type = "fits"
    p = {}
    p["sec", "aaa"] = "xxx"
    p["sec", "bbb"] = 123
    p["sec", "ccc"] = 3.14
    p["sec", "DDD"] = "cat"
    p["sec", "eee"] = 4.14

    with tempfile.TemporaryDirectory() as dirname:
        fname = os.path.join(dirname, f"test.{file_type}")

        # Write to now-closed
        file_id = ioUtils.write(p, fname, "provenance")

        assert os.path.exists(fname)

        q, r_comments = ioUtils.read_get(fname, "provenance")

        assert q["sec", "aaa"] == "xxx"
        assert q["sec", "bbb"] == 123
        assert q["sec", "ccc"] == 3.14

        # check the direct getters work
        assert ioUtils.get(fname, "provenance", "sec", "DDD") == "cat"
        assert ioUtils.get(fname, "provenance", "sec", "eee") == 4.14



def test_fits_multiline():
    file_type = "fits"
    p = {}
    p["sec", "aaa"] = "Two households;\nboth alike in dignity!"

    with tempfile.TemporaryDirectory() as dirname:
        fname = os.path.join(dirname, f"test.{file_type}")

        # Write to now-closed
        ioUtils.write(p, fname, "provenance")

        assert os.path.exists(fname)

        q, _com = ioUtils.read_get(fname, "provenance")

        assert p["sec", "aaa"] == q["sec", "aaa"]


def test_existing_hdf():

    p = {}
    p["sec", "aaa"] = "xxx"
    p["sec", "bbb"] = 123
    p["sec", "ccc"] = 3.14
    p["sec", "DDD"] = "cat"
    p["sec", "eee"] = 4.14

    comments = ["hopefully nothing else will break if I add this"]

    with tempfile.TemporaryDirectory() as dirname:
        fname = os.path.join(dirname, "test.hdf")
        fname2 = os.path.join(dirname, "test2.hdf")

        with utils.open_hdf(fname, "w") as f:
            f.create_group("cake")

        ioUtils.write(p, fname, "provenance", comments)
        ioUtils.write(p, fname2, "provenance", comments)

        q1 = ioUtils.read_get(fname, "provenance")
        q2 = ioUtils.read_get(fname2, "provenance")


def test_yml():
    import ruamel.yaml as yaml

    y = yaml.YAML()
    # check nothing is overridden
    d = {
        "cat": "good",
        "dog": "bad",
        "spoon": 45.6,
        "cow": -222,
    }
    p = {}
    p["sec", "aaa"] = "xxx"
    p["sec", "bbb"] = 123
    p["sec", "ccc"] = 3.14
    p["sec", "DDD"] = "cat"
    p["sec", "eee"] = 4.14

    comments = ["this is a test to check nothing else breaks"]
    
    with tempfile.TemporaryDirectory() as dirname:
        fname = os.path.join(dirname, "test.yml")
        y.dump(d, open(fname, "w"))

        ioUtils. write(p, fname, "provenance", comments)

        # check prov reads
        q = ioUtils.read_get(fname, "provenance")

        d2 = y.load(open(fname))
        d2.pop("provenance")
        assert d == d2



def test_unknown_file_type():
    p = {}
    p["sec", "aaa"] = "xxx"
    p["sec", "bbb"] = 123
    p["sec", "ccc"] = 3.14
    p["sec", "DDD"] = "cat"
    p["sec", "eee"] = 4.14
    
    with tempfile.TemporaryDirectory() as dirname:
        fname = os.path.join(dirname, "test.xyz")
        pname = os.path.join(dirname, "test.xyz.provenance.yaml")
        file_id = ioUtils.write(p, fname, "provenance")
        print(fname, pname)
        p2 = ioUtils.read_get(fname, "provenance")


def test_long():
    p = {}
    p["sec", "aaa"] = "xxx"
    p["sec", "bbb"] = 123
    p["sec", "ccc"] = 3.14
    p["sec", "DDD"] = "cat"
    p["sec", "eee"] = 4.14
    
    lines = []
    for i in range(1002):
        line = "".join(random.choice(string.printable) for i in range(100))
        lines.append(line)
    text = "\n".join(lines)
    p["section", "key"] = text

    with tempfile.TemporaryDirectory() as dirname:
        fname = os.path.join(dirname, "test.fits")
        with pytest.warns(UserWarning):
            ioUtils.write(p, fname, "provenance")
        q = ioUtils.read_get(fname, "provenance")


def test_comments():
    p = {}
    p["sec", "aaa"] = "xxx"
    p["sec", "bbb"] = 123
    p["sec", "ccc"] = 3.14
    p["sec", "DDD"] = "cat"
    p["sec", "eee"] = 4.14
    
    comments = [
        "Hello,",
        "My name is Inigo Montoya",
        "You killed my father",
        "Prepare to die",
    ]

    with tempfile.TemporaryDirectory() as dirname:
        for suffix in ["hdf", "fits"]:
            fname = os.path.join(dirname, f"test.{suffix}")
            ioUtils.write(p, fname, "provenance", comments=comments)
            q, r_comments = ioUtils.read_get(fname, "provenance")
            for c in comments:
                assert c in r_comments


if __name__ == "__main__":
    test_comments()
    #test_long()
