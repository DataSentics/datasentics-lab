import os
import binascii
import re

from datetime import datetime
from pathlib import Path
from pyspark.sql.utils import IllegalArgumentException


class DBPath:
    """
    A Utility class for working with DataBricks API paths directly and in a unified manner.

    The Design is inspired by pathlib.Path

    >>> path = DBPath('abfss://...')
    >>> path = DBPath('dbfs:/...')
    >>> path = DBPath('file:/...')
    >>> path = DBPath('s3:/...')
    >>> path = DBPath('s3a:/...')
    >>> path = DBPath('s3n:/...')

    Initialization

    ```
    >>> from dslab import DBPath

    Provide spark session for dbutils instance
    >>> DBPath.set_spark_session(spark)

    set FileStore base download url for your dbx workspace
    >>> DBPath.set_base_download_url('https://adb-1234.5.azuredatabricks.net/files/')
    ```

    PROPERTIES:

    path - the whole path
    name - just the filename (last part of path)
    parent - the parent (DBPath)
    children - sorted list of children files (list(DBPath)), empty list for non-folders
    in_local, in_dbfs, in_filestore, in_lake, in_bucket - predicates for location of file


    BASE METHODS:

    exists() - returns True if file exists
    is_dir() - returns True if file exists and is a directory
    ls() - prints human readable list of contained files for folders, with file sizes
    tree(max_depth=5) - prints the directory structure, up to `max_depth`
    cp(destination, recurse=False) - same as dbutils.fs.cp(str(self), str(destination), recurse)
    rm(recurse=False) - same as dbutils.fs.rm(str(self), recurse)
    mkdirs() - same as dbutils.fs.mkdirs(str(self))
    iterdir() - sorted generator over files (also DBPath instances) - similar to Path.iterdir()
    reiterdir(regex) - sorted generator over files (DBPath) that match `bool(re.findall(regex, file))`

    IO METHODS:

    open(method='rt', encoding='utf-8') - context manager for working with any DB API file locally
    read_text(encoding='utf-8') - reads the file as text and returns contents
    read_bytes() - reads the file as bytes and returns contents
    write_text(text) - writes text to the file
    write_bytes(bytedata) - writes bytes to the file
    download_url() - for FileStore records returns a direct download URL
    make_download_url() - copies a file to FileStore and returns a direct download URL
    backup() - creates a backup copy in the same folder, named by following convention
        {filename}[.extension] -> {filename}_YYYYMMDD_HHMMSS[.extension]
    restore(timestamp) - restore a previous backup of this file by passing backup timestamp string (`'YYYYMMDD_HHMMSS'`)

    CLASS METHODS:

    set_spark_session(spark) - necessary to call upon initialization
    clear_tmp_download_cache() - clear all files created using `make_download_url()`
    temp_file - context manager that returns a temporary DBPath
    - set_base_download_url - call once upon initialization, sets base url for filestore direct downloads
      (e.g. 'https://adb-1234.5.azuredatabricks.net/files/')
    - set_protocol_temp_path - call once upon initialization for each filesystem you want to create temp files/dirs in
      ('dbfs' and 'file' are set by default).

    """

    ### CONSTANTS

    _CACHE_PREFIX = "DBPath_cache_"
    _KNOWN_PROTOCOLS = ["dbfs", "file", "abfss", "s3", "s3a", "s3n"]
    _KNOWN_PROTOCOL_REGEX = "^(" + "|".join(_KNOWN_PROTOCOLS) + "):.*$"

    ### CLASS LEVEL VARIABLES

    _BASE_DOWNLOAD_URL = None
    _dbutils = None

    ### INIT

    def __init__(self, path):
        """
        Create a DataBricks Path.

        Parameters
        ----------
        path : str or DBPath
            DB API path, e.g. 'file:/tmp/abc', 'dbfs:/FileStore/file.txt', 'abfss://lakepath/folder'
        """

        path = str(path)

        if path.startswith("/"):
            path = "file:" + path

        if not re.match(self._KNOWN_PROTOCOL_REGEX, path):
            raise ValueError(f"Unknown protocol for path {path}. Known protocols: {self._KNOWN_PROTOCOLS}")

        self._path = path

    ### OVERRIDDEN FUNCTIONS

    def __str__(self):
        return self.path

    def __repr__(self):
        return f"DBPath('{self.path}')"

    def __truediv__(self, path):
        if self.path.endswith("/"):
            return DBPath(self.path + path)
        else:
            return DBPath(self.path + "/" + path)

    def __cmp__(self, other):
        return self.path.__cmp__(other.path)

    def __lt__(self, other):
        return self.path < other.path

    ### PROPERTIES

    @property
    def path(self):  # makes sure path has immutable interface
        return self._path

    @property
    def name(self):
        return self._path_parts[-1]

    @property
    def protocol(self):
        return self._parts[0]

    @property
    def protocol_separator(self):
        return self._parts[1]

    def _join(self, path_parts):
        return self.protocol + self.protocol_separator + "/".join(path_parts)

    @property
    def parent(self):
        if len(self._path_parts) == 1:
            raise ValueError(f"Cannot get parent, path {self.path} is a root folder.")
        return DBPath(self._join(self._path_parts[:-1]))

    @property
    def children(self):
        return list(self.iterdir()) if self.is_dir() else []

    @property
    def _parts(self):
        #  for dbfs:/FileStore/file.txt returns ['dbfs', ':/',  'FileStore/file.txt']
        separator_match = list(re.finditer("(:/+)", self.path))[0]

        start, end = separator_match.span()

        protocol = self.path[:start]
        path = self.path[end:]
        separator = separator_match.group()

        return protocol, separator, path

    @property
    def _path_parts(self):
        # for dbfs:/FileStore/file.txt returns ['FileStore', 'file.txt']
        return list(filter(len, self._parts[2].split("/")))

    @property
    def in_local(self):
        return self.protocol == "file"

    @property
    def in_dbfs(self):
        return self.protocol == "dbfs"

    @property
    def in_filestore(self):
        return self.protocol == "dbfs" and self._path_parts[0] == "FileStore"

    @property
    def in_lake(self):
        return self.protocol == "abfss"

    @property
    def in_bucket(self):
        return bool(re.match("^s3[na]?$", self.protocol))

    @property
    def dbutils(self):
        if self._dbutils is not None:
            return self._dbutils

        raise ValueError("Spark session has not been assigned yet. Call DBUtils.set_spark_session(spark) in your " "initialization.")

    ### BASE METHODS
    def exists(self):
        """
        Returns
        -------
        bool
            True if path exists
        """
        try:
            self.dbutils.fs.ls(self.path)
            return True
        except Exception as e:
            return False

    def is_dir(self):
        """
        Returns
        -------
        bool
            True if path is a directory
        """
        if not self.exists():
            return False

        ls = self.dbutils.fs.ls(self.path)
        return not (len(ls) == 1 and ls[0].path == self.path)

    def ls(self):
        """
        Prints out contents of a folder (with file sizes) if path is a directory,
        or the file name and size of the file otherwise.
        """

        print(f"ls {self.path}")
        records = self.dbutils.fs.ls(self.path)
        max_name_len = max([len(record.name) for record in records])

        template = f"{{name:<{max_name_len + 10}}}{{size:>10}}"

        print(template.format(name="File", size="Size   "))

        for record in records:
            if record.size < 1024:
                print(template.format(name=record.name, size=f"{record.size / 1024 ** 0:.2f} B "))
            elif record.size < 1024 ** 2:
                print(template.format(name=record.name, size=f"{record.size / 1024 ** 1:.2f} KB"))
            elif record.size < 1024 ** 3:
                print(template.format(name=record.name, size=f"{record.size / 1024 ** 2:.2f} MB"))
            else:
                print(template.format(name=record.name, size=f"{record.size / 1024 ** 3:.2f} GB"))

    @staticmethod
    def _tree(file, indent="", remaining_depth=5):
        print(f"{indent} - {file.name}")
        if file.is_dir():
            if remaining_depth == 0:
                print(" (*collapsed)", end="")

            for child in file.iterdir():
                DBPath._tree(child, indent + "   ", remaining_depth - 1)

    def tree(self, max_depth=5):
        """
        Prints out the hierarchical directory structure up to `max_depth` layers

        Parameters
        ----------
        max_depth : int
            the maximum depth to which print out the directory structure
        """
        self._tree(self, remaining_depth=max_depth)

    def cp(self, destination, recurse=False):
        """
        Copies the path - same as `dbutils.fs.cp(str(self.path), str(destination), recurse=recurse)`

        - if path is a file and destination is a non-existing or existing file, the
          file gets copied with the new name.
        - if path is a file and destination is an existing folder, the file gets
          copied into the folder with its original name.
        - if path is a folder and destination is a non-existing file, the folder gets
          copied and renamed to match the non-existing file which is now the folder
        - if path is a folder and destination is an existing folder, the path
          gets copied to the existing folder as a subfolder with its original name


        Parameters
        ----------
        destination : str or DBPath
            destination path
        recurse : bool
            set True to copy directories
        """
        self.dbutils.fs.cp(self.path, str(destination), recurse=recurse)

    def mkdirs(self):
        """
        Creates directories - same as `dbutils.fs.mkdirs(str(self.path))`
        """

        self.dbutils.fs.mkdirs(self.path)

    def rm(self, recurse=False):
        """
        Removes file or directory - same as `dbutils.fs.rm(str(self.path), recurse=recurse)`

        Parameters
        ----------
        recurse : bool
            set True to remove non-empty directories
        """
        self.dbutils.fs.rm(self.path, recurse=recurse)

    def iterdir(self):
        """
        If this is a folder, returns a sorted generator over contained files (DBPath instances).

        Returns
        -------
        generator(DBPath)
            sorted generator over contained files
        """
        if not self.is_dir():
            raise ValueError(f"Not a directory: {self.path}")

        dbpaths = [DBPath(record.path) for record in self.dbutils.fs.ls(self.path)]

        for path in sorted(dbpaths):
            yield path

    def reiterdir(self, regex):
        """
        If this is a folder, returns a generator over contained files (DBPath instances) which match
        `bool(re.findall(regex, filename)) == True`

        Parameters
        ----------
        regex : str or Pattern
            pattern to match file against

        Returns
        -------
        generator(DBPath)
            sorted generator over contained files that match provided `regex`
        """

        for file in self.iterdir():
            if re.findall(regex, file.name):
                yield file

    ### I/O FUNCTIONS

    def download_url(self):
        """
        For FileStore records, returns direct download URL

        Returns
        -------
        str
            direct download URL
        """
        if self._BASE_DOWNLOAD_URL is None:
            raise ValueError(f"You have to set a download URL for your DataBricks workspace. use DBPath.")

        if self.is_dir():
            raise ValueError(f"path has to be a file, this path is a directory.")

        if not self.in_filestore:
            raise ValueError(
                f'path has to start with "dbfs:/FileStore/". Use .make_download_url() for automatic copy to FileStore and link.'
            )

        return self._BASE_DOWNLOAD_URL + self.path.replace("dbfs:/FileStore/", "")

    def _make_tmp_folder_name(self):
        return self._CACHE_PREFIX + _randstr(10)

    def make_download_url(self):
        """
        For any file, copies it to filestore and returns a direct download URL

        Note
        ----
        The files are always saved in dbfs:/FileStore/tmp/ with a fixed prefix.
        To remove all the files created this way, call `DBPath.clear_tmp_download_cache()`

        Returns
        -------
        str
            download URL

        """
        """
        Copy file to FileStore and return a direct download URL
        """
        if self.is_dir():
            raise ValueError(f"path has to be a file, this path is a directory.")

        if self.in_filestore:
            return self.download_url()

        path = DBPath("dbfs:/FileStore/tmp")
        path.mkdirs()
        path /= self._make_tmp_folder_name()
        path.mkdirs()
        path /= self.name
        self.cp(path)
        return path.download_url()

    def open(self, mode="rt", encoding="utf-8"):
        """
        acts as a wrapper around native Python open().
        Allows directly reading and writing to any file with DBAPI path.

        Parameters
        ----------
        mode : str
            r/w/t + b/t (same as in open())
        encoding : str
            same as in open()

        Returns
        -------
        _DBOpenContextManager
            a context manager, that returns a local file handle, changes are synchronized on __exit__
        """
        return _DBOpenContextManager(self.dbutils, self.path, mode=mode, encoding=encoding)

    def read_text(self, encoding=None):
        """
        Reads the text contents of the path

        Parameters
        ----------
        encoding : str
            as in open()

        Returns
        -------
        str
            text contents of the file
        """
        with self.open("rt", encoding) as f:
            return f.read()

    def read_bytes(self):
        """
        Reads the binary contents of the path

        Returns
        -------
        bytes
            binary contents of the file
        """
        with self.open("rb", None) as f:
            return f.read()

    def write_text(self, text, encoding=None):
        """
        Writes text to path.

        Parameters
        ----------
        text : str
            contents to be written
        encoding : str
            as in open()
        """
        with self.open("wt", encoding) as f:
            f.write(text)

    def write_bytes(self, bytedata):
        """
        Writes bytes to path.

        Parameters
        ----------
        bytedata : bytes
            contents to be written

        """
        with self.open("wb", None) as f:
            f.write(bytedata)

    def backup(self):
        """
        backs up the file/folder on path, using following convention (adds timestamp):

        {filename}.extension -> {filename}_{YYYYMMDD_HHMMSS}.extension

        the file/folder is copied with the new name.

        Returns
        -------
        DBPath
            the path of the backed-up file
        """
        if not self.exists():
            print("file for backup doesn't exist, skipping backup.")
            return

        split = self.name.split(".")
        suffix = f'_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        if len(split) > 1:  # has extension
            prefix = ".".join(split[:-1])
            extension = split[-1]
            out_path = prefix + suffix + "." + extension
        else:
            out_path = self.path + suffix

        print(f"backing up file {self.path}->{out_path}")
        self.dbutils.fs.cp(self.path, out_path, recurse=True)

        return DBPath(out_path)

    def restore(self, timestamp, overwrite=False):
        """
        Restores the path from a backup with a given timestamp. Leaves the backup intact.

        Parameters
        ----------
        timestamp : str
            identifying timestamp of the backup, format: 'YYYYMMDD_HHMMSS'
        overwrite : bool
            set True to overwrite existing path
        """

        backup_path = self.parent / (self.name + "_" + timestamp)
        if not backup_path.exists():
            raise FileNotFoundError(f"path {backup_path} doesn't exist.")

        if self.exists() and not overwrite:
            raise ValueError(f"File on restore path {self.path} exists. Set overwrite=True to delete before restore.")

        print(f"restoring backup from {timestamp} to {self}.")

        self.rm(True)
        backup_path.cp(self, True)

    ### CLASS METHODS

    @classmethod
    def set_base_download_url(cls, url):
        """
        Set base URL for downloads (this URL points to the dbfs:/FileStore/ root).

        Parameters
        ----------
        url : str
             e.g. 'https://adb-123456789.10.azuredatabricks.net/files/'

        """
        cls._BASE_DOWNLOAD_URL = url

    @classmethod
    def set_spark_session(cls, spark):
        """
        This has to be called before using DBPath in scripts, necessary to create dbutils instance.

        Parameters
        ----------
        spark : SparkSession
            spark session
        """
        from pyspark.dbutils import DBUtils

        cls._dbutils = DBUtils(spark)

    @classmethod
    def clear_tmp_download_cache(cls):
        """
        Delete all files in dbfs:/FileStore/tmp that were created using .create_download_url()
        """
        path = DBPath("dbfs:/FileStore/tmp/")
        for file in path.reiterdir(f"^{re.escape(cls._CACHE_PREFIX)}.*"):
            print(f"clearing " + str(file))
            file.rm(recurse=True)

    @classmethod
    def temp_file(cls, protocol="dbfs"):
        """
        Creates a path in tmp folder of given filesystem and returns a context manager that deletes
        this path after the context manager exits.

        Take note that this file does not get created for you, only its path.

        You can use this to create temporary files or directories.

        e.g.

        with DBPath.temp_file('file') as dbpath:
            ...

        Parameters
        ----------
        protocol : str
            by default `'file'` or `'dbfs'`, for others, add default temp paths using `DBPath.set_protocol_temp_path()`

        Returns
        -------
        _DBTempContextManager
            a context manager that returns a temporary DBPath. Upon exiting the context manager,
            the path gets removed.
        """
        return _DBTempContextManager(protocol)

    @classmethod
    def set_protocol_temp_path(cls, protocol, path):
        """
        sets the base temp path for a given protocol to be used with `DBPath.temp_file()`,
        e.g. for `protocol=='dbfs'`, `path=':/tmp/'`, so `protocol + path == 'dbfs:/tmp/'`

        Parameters
        ----------
        protocol : str
            protocol for which to set up a temp path
        path : str
            path that follows immediately after protocol name, e.g. ':/tmp/'

        """
        _DBTempContextManager.set_protocol_temp_path(protocol, path)


class _DBOpenContextManager:
    """
    ContextManager that wraps open() to work with data lake paths and dbapi paths in general
    """

    def __init__(self, dbutils, dbpath, mode, encoding):
        self.dbutils = dbutils
        self.dbpath = dbpath
        self.mode = mode
        self.encoding = encoding
        self.localpath = "/tmp/" + _randstr(30)

    def __enter__(self):
        self.dbutils.fs.mkdirs("file:/tmp/")

        if "r" in self.mode or "a" in self.mode:
            self.dbutils.fs.cp(self.dbpath, "file:" + self.localpath, recurse=True)
            _remove_crc_files(self.localpath)

        self.open_ctx = open(self.localpath, mode=self.mode, encoding=self.encoding)
        return self.open_ctx.__enter__()

    def __exit__(self, *args):
        retval = self.open_ctx.__exit__(*args)

        if not args[0] and ("a" in self.mode or "w" in self.mode):
            self.dbutils.fs.cp("file:" + self.localpath, self.dbpath, recurse=True)

        self.dbutils.fs.rm("file:" + self.localpath, recurse=True)

        return retval


class _DBTempContextManager:
    """
    ContextManager that creates a temporary path - it doesn't create any files
    """

    _TMP_PATHS = {"dbfs": ":/tmp/", "file": ":/tmp/"}

    @classmethod
    def set_protocol_temp_path(cls, protocol, path):
        """
        sets the base temp path for a given protocol,
        e.g. for protocol=='dbfs', path=':/tmp/', so protocol + path == 'dbfs:/tmp/'
        """
        cls._TMP_PATHS[protocol] = path

    def __init__(self, protocol="dbfs"):
        self.protocol = protocol
        self.temppath = DBPath(protocol + self._TMP_PATHS[protocol] + _randstr(30))

    def __enter__(self):
        return self.temppath

    def __exit__(self, *args):
        if self.temppath.exists():
            self.temppath.rm(recurse=True)

        if args[0]:
            return


def _remove_crc_files(path):
    """
    Removes all HDFS checksum files in folder. This is necessary when you want
    to copy a folder from HDFS to local, modify files and copy it back.
    If the .crc files stay, the copy back fails because of checksum mismatch.
    """
    path = Path(path)
    path_crc = path.parent / ("." + path.name + ".crc")

    if path_crc.exists():
        os.remove(path_crc)

    if path.is_dir():
        for file in path.iterdir():
            if file.exists() and not file.name.endswith(".crc"):
                _remove_crc_files(file)


def _randstr(n):
    return binascii.b2a_hex(os.urandom(n // 2)).decode("utf-8")
