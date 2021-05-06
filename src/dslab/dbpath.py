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

    path = DBPath('abfss://...')
    path = DBPath('dbfs:/...')
    path = DBPath('file:/...')

    Initialization

    ```
    from dbpathlib import DBPath

    # provide spark session for dbutils instance
    DBPath.set_spark_session(spark)

    # set FileStore base download url for your dbx workspace
    DBPath.set_base_download_url('https://adb-1234.5.azuredatabricks.net/files/')
    ```


    PROPERTIES:

    - path - the whole path
    - name - just the filename (last part of path)
    - parent - the parent (DBPath)
    - children - sorted list of children files (list(DBPath)), empty list for non-folders
    - in_local, in_dbfs, in_filestore, in_lake - predicates for location of file


    BASE METHODS:

    - exists - returns True if file exists
    - is_dir - returns True if file exists and is a directory
    - ls - human friendly print out of contained files for folders, including file sizes
    - tree - print recursively directory structure
    - cp, rm, mkdirs - wrappers around dbutils functions, same interface
    - iterdir - sorted generator over files (also DBPath instances)
    - reiterdir - sorted generator over files that match regexp (also DBPath instances)


    IO METHODS:

    - read_text - reads the file as text and returns contents
    - read_bytes - reads the file as bytes and returns contents
    - write_text - writes text to the file
    - write_bytes - writes bytes to the file
    - download_url - for FileStore records returns a direct download URL
    - make_download_url - copies a file to FileStore and returns a direct download URL
    - backup - creates a backup copy in the same folder, named as
      {filename}[.extension] -> {filename}_YYYYMMDD_HHMMSS[.extension]
    - restore - restore a previous backup of this file by passing backup timestamp string ('YYYYMMDD_HHMMSS')

    CLASS METHODS:

    - clear_tmp_download_cache - clear all files created using make_download_url
    - temp_file - context manager that returns a temporary DBPath
    - set_base_download_url - call once upon initialization, sets base url for filestore direct downloads
      (e.g. 'https://adb-1234.5.azuredatabricks.net/files/')
    - set_spark_session - call once upon initialization for getting dbutils instance
    - set_protocol_temp_path - call once upon initialization for each filesystem you want to create temp files/dirs in
      ('dbfs' and 'file' are set by default).

    """

    ### CONSTANTS

    _CACHE_PREFIX = 'DBPath_cache_'

    ### CLASS LEVEL VARIABLES

    _BASE_DOWNLOAD_URL = None
    _dbutils = None

    ### INIT

    def __init__(self, path):
        """
        Create a DataBricks Path.

        @param path: DB API path, e.g. 'file:/tmp/abc', 'dbfs:/FileStore/file.txt', 'abfss://lakepath/folder'
        @dtype str
        """
        self._path = str(path)

    ### OVERRIDDEN FUNCTIONS

    def __str__(self):
        return self.path

    def __repr__(self):
        return f'DBPath(\'{self.path}\')'

    def __truediv__(self, path):
        if self.path.endswith('/'):
            return DBPath(self.path + path)
        else:
            return DBPath(self.path + '/' + path)

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
        return self.protocol + self.protocol_separator + '/'.join(path_parts)

    @property
    def parent(self):
        if len(self._path_parts) == 1:
            raise ValueError(f'Cannot get parent, path {self.path} is a root folder.')
        return DBPath(self._join(self._path_parts[:-1]))

    @property
    def children(self):
        return list(self.iterdir()) if self.is_dir() else []

    @property
    def _parts(self):
        # for dbfs:/FileStore/file.txt returns ['dbfs', ':/',  'FileStore/file.txt']
        separator_match = list(re.finditer('(:/+)', self.path))[0]

        start, end = separator_match.span()

        protocol = self.path[:start]
        path = self.path[end:]
        separator = separator_match.group()

        return protocol, separator, path

    @property
    def _path_parts(self):
        # for dbfs:/FileStore/file.txt returns ['FileStore', 'file.txt']
        return list(filter(len, self._parts[2].split('/')))

    @property
    def in_local(self):
        return self.protocol == 'file'

    @property
    def in_dbfs(self):
        return self.protocol == 'dbfs'

    @property
    def in_filestore(self):
        return self.protocol == 'dbfs' and self._path_parts[0] == 'FileStore'

    @property
    def in_lake(self):
        return self.protocol == 'abfss'

    @property
    def dbutils(self):
        if self._dbutils is not None:
            return self._dbutils

        raise ValueError(
            'Spark session has not been assigned yet. Call DBUtils.set_spark_session(spark) in your initialization.')

    ### BASE METHODS

    def exists(self):
        try:
            self.dbutils.fs.head(self.path)
            return True
        except IllegalArgumentException as e:  # this is thrown for folders
            return True
        except Exception as e:
            if re.findall(re.escape('java.io.FileNotFoundException:'), str(e)):
                return False
            else:
                raise e

    def is_dir(self):
        if not self.exists():
            return False

        ls = self.dbutils.fs.ls(self.path)
        return not (len(ls) == 1 and ls[0].path == self.path)

    def ls(self):
        print(f'ls {self.path}')
        records = self.dbutils.fs.ls(self.path)
        max_name_len = max([len(record.name) for record in records])

        template = f'{{name:<{max_name_len + 10}}}{{size:>10}}'

        print(template.format(name='File', size='Size   '))

        for record in records:
            if record.size < 1024:
                print(template.format(name=record.name, size=f'{record.size / 1024 ** 0:.2f} B '))
            elif record.size < 1024 ** 2:
                print(template.format(name=record.name, size=f'{record.size / 1024 ** 1:.2f} KB'))
            elif record.size < 1024 ** 3:
                print(template.format(name=record.name, size=f'{record.size / 1024 ** 2:.2f} MB'))
            else:
                print(template.format(name=record.name, size=f'{record.size / 1024 ** 3:.2f} GB'))

    @staticmethod
    def _tree(file, indent=''):
        print(f'{indent} - {file.name}')
        if file.is_dir():
            for child in file.iterdir():
                DBPath._tree(child, indent + '   ')

    def tree(self):
        self._tree(self)

    def cp(self, destination, recurse=False):
        self.dbutils.fs.cp(self.path, str(destination), recurse=recurse)

    def mkdirs(self):
        self.dbutils.fs.mkdirs(self.path)

    def rm(self, recurse=False):
        self.dbutils.fs.rm(self.path, recurse=recurse)

    def iterdir(self):
        """
        If this is a folder, returns a sorted generator over contained files (DBPath instances)
        """
        if not self.is_dir():
            raise ValueError(f'Not a directory: {self.path}')

        dbpaths = [DBPath(record.path) for record in self.dbutils.fs.ls(self.path)]

        for path in sorted(dbpaths):
            yield path

    def reiterdir(self, regexp):
        """
        If this is a folder, returns a generator over contained files (DBPath instances) that match regexp
        """
        for file in self.iterdir():
            if re.findall(regexp, file.name):
                yield file

    ### I/O FUNCTIONS

    def download_url(self):
        """
        For FileStore records, returns direct download URL
        """
        if self._BASE_DOWNLOAD_URL is None:
            raise ValueError(f'You have to set a download URL for your DataBricks workspace. use DBPath.')

        if self.is_dir():
            raise ValueError(f'path has to be a file, this path is a directory.')

        if not self.in_filestore:
            raise ValueError(
                f'path has to start with "dbfs:/FileStore/". Use .make_download_url() for automatic copy to FileStore and link.')

        return self._BASE_DOWNLOAD_URL + self.path.replace('dbfs:/FileStore/', '')

    def _make_tmp_folder_name(self):
        return self._CACHE_PREFIX + randstr(10)

    def make_download_url(self):
        """
        Copy file to FileStore and return a direct download URL
        """
        if self.is_dir():
            raise ValueError(f'path has to be a file, this path is a directory.')

        if self.in_filestore:
            return self.download_url()

        path = DBPath('dbfs:/FileStore/tmp')
        path.mkdirs()
        path /= self._make_tmp_folder_name()
        path.mkdirs()
        path /= self.name
        self.cp(path)
        return path.download_url()

    def open(self, mode='rt', encoding='utf-8'):
        """
        returns a context manager wrapper around open(). Allows directly
        reading and writing to any file with DBAPI path.

        @param mode: r/w/t + b/t
        @dtype str
        @param encoding as with open()
        @dtype str

        @return open context manager that
        @dtype ContextManager
        """
        return _DBOpenContextManager(self.dbutils, self.path, mode=mode, encoding=encoding)

    def read_text(self, encoding=None):
        with self.open('rt', encoding) as f:
            return f.read()

    def read_bytes(self):
        with self.open('rb', None) as f:
            return f.read()

    def write_text(self, text, encoding=None):
        with self.open('wt', encoding) as f:
            f.write(text)

    def write_bytes(self, bytes):
        with self.open('wb', None) as f:
            f.write(bytes)

    def backup(self):
        """
        backs up the file/folder on path, using following convention (adds timestamp):

        {filename}.extension -> {filename}_{YYYYMMDD_HHMMSS}.extension

        the file/folder is copied with the new name.
        """
        if not self.exists():
            print('file for backup doesn\'t exist, skipping backup.')
            return

        split = self.name.split('.')
        suffix = f'_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        if len(split) > 1:  # has extension
            prefix = '.'.join(split[:-1])
            extension = split[-1]
            out_path = prefix + suffix + '.' + extension
        else:
            out_path = self.path + suffix

        print(f'backing up file {self.path}->{out_path}')
        self.dbutils.fs.cp(self.path, out_path, recurse=True)

        return DBPath(out_path)

    def restore(self, timestamp, overwrite=False):
        """
        Restores a path from backup. Leaves the backup intact.

        In order to overwrite existing data, you have to set overwrite=True

        timestamp='YYYYMMDD_HHMMSS'
        """

        backup_path = self.parent / (self.name + '_' + timestamp)
        if not backup_path.exists():
            raise FileNotFoundError(f'path {backup_path} doesn\'t exist.')

        if self.exists() and not overwrite:
            raise ValueError(
                f'File on restore path {self.path} exists. Set overwrite=True to delete before restore.')

        print(f'restoring backup from {timestamp} to {self}.')

        self.rm(True)
        backup_path.cp(self, True)

    ### CLASS METHODS

    @classmethod
    def set_base_download_url(cls, url):
        cls._BASE_DOWNLOAD_URL = url

    @classmethod
    def set_spark_session(cls, spark):
        from pyspark.dbutils import DBUtils
        cls._dbutils = DBUtils(spark)

    @classmethod
    def clear_tmp_download_cache(cls):
        path = DBPath('dbfs:/FileStore/tmp/')
        for file in path.reiterdir(f'^{re.escape(cls._CACHE_PREFIX)}.*'):
            print(f'clearing ' + str(file))
            file.rm(recurse=True)

    @classmethod
    def temp_file(cls, protocol='dbfs'):
        """
        Creates a file in tmp folder of given filesystem and returns a context manager

        @param filesystem: 'file' or 'dbfs' (for others, add default temp paths using set_protocol_temp_path)
        @dtype: str

        @return context manager

        with DBPath.temp_file('file') as dbpath:
            ....

        with DBPath.temp_file('dbfs') as dbpath:
            ....
        """
        return _DBTempContextManager(protocol)

    @classmethod
    def set_protocol_temp_path(cls, protocol, path):
        """
        sets the base temp path for a given protocol,
        e.g. for protocol=='dbfs', path=':/tmp/', so protocol + path == 'dbfs:/tmp/'
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
        self.localpath = '/tmp/' + randstr(30)

    def __enter__(self):
        self.dbutils.fs.mkdirs('file:/tmp/')

        if 'r' in self.mode or 'a' in self.mode:
            self.dbutils.fs.cp(self.dbpath, 'file:' + self.localpath, recurse=True)
            remove_crc_files(self.localpath)

        self.open_ctx = open(self.localpath, mode=self.mode, encoding=self.encoding)
        return self.open_ctx.__enter__()

    def __exit__(self, *args):
        retval = self.open_ctx.__exit__(*args)

        if not args[0] and ('a' in self.mode or 'w' in self.mode):
            self.dbutils.fs.cp('file:' + self.localpath, self.dbpath, recurse=True)

        self.dbutils.fs.rm('file:' + self.localpath, recurse=True)

        return retval


class _DBTempContextManager:
    """
    ContextManager that creates a temporary path - it doesn't create any files
    """
    _TMP_PATHS = {
        'dbfs': ':/tmp/',
        'file': ':/tmp/'
    }

    @classmethod
    def set_protocol_temp_path(cls, protocol, path):
        """
        sets the base temp path for a given protocol,
        e.g. for protocol=='dbfs', path=':/tmp/', so protocol + path == 'dbfs:/tmp/'
        """
        cls._TMP_PATHS[protocol] = path

    def __init__(self, protocol='dbfs'):
        self.protocol = protocol
        self.temppath = DBPath(protocol + self._TMP_PATHS[protocol] + randstr(30))

    def __enter__(self):
        return self.temppath

    def __exit__(self, *args):
        if self.temppath.exists():
            self.temppath.rm(recurse=True)

        if args[0]:
            return


def remove_crc_files(path):
    """
    Removes all HDFS checksum files in folder. This is necessary when you want
    to copy a folder from HDFS to local, modify files and copy it back.
    If the .crc files stay, the copy back fails because of checksum mismatch.
    """
    path = Path(path)
    path_crc = path.parent / ('.' + path.name + '.crc')

    if path_crc.exists():
        os.remove(path_crc)

    if path.is_dir():
        for file in path.iterdir():
            if file.exists() and not file.name.endswith('.crc'):
                remove_crc_files(file)


def randstr(n):
    return binascii.b2a_hex(os.urandom(n // 2)).decode('utf-8')
