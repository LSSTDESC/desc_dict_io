import enum

class FileType(enum.Enum):
    yaml_file = 0
    fits_file = 1
    hdf5_file = 2
    pickle_file = 3


file_suffixes = {
    FileType.yaml_file: [".yml", ".yaml"],
    FileType.fits_file: [".fits", ".fit"],
    FileType.hdf5_file: [".hdf", ".hdf5"],
    FileType.pickle_file: [".pkl", ".pickle"],
}

file_type_map = {}
for file_type, suffix_list in file_suffixes.items():
    for suffix_ in suffix_list:
        file_type_map[suffix_] = file_type

def get_default_suffix(f_type: FileType) -> str:
    return file_suffixes[f_type][0]

def get_file_type(suffix: str) -> FileType:
    return file_type_map[suffix]
