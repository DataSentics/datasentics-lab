# datasentics-lab

dslab is a fully open-source package that simplifies everyday tasks for data scientists that rely on Databricks. 
It contains experimental code primarily developed and maintained by DataSentics.

All contributions and contributors are very welcome!

## Installation

Pyspark is the only dependency that needs to be preinstalled.

The package is available on PyPI:

```
pip install datasentics-lab
```

## Utilities

### DBPath

`DBPath` is a QoL utility that simplifies and unifies files handling in Databricks.

It's design and API is inspired by `pathlib.Path`.

#### Showcase

```python
from dslab.dbpath import DBPath

DBPath.set_spark_session(spark)  # used to initialize dbutils instance

path = DBPath('dbfs:/FileStore/')

path.ls() # lists files in directory in human-readable format

path.tree(max_depth=2) # prints indented directory tree

file = path / 'tmp' / 'my_file'

with file.open('wt') as f:
    f.write('It really is this simple!')
    
print(file.read_text())

file.write_text('And this is even easier!')

print(file.read_text())

print(f'{file} exists: {file.exists()}, is dir: {file.is_dir()}, is in filestore: {file.in_filestore}')
```

And that is just a taste! See full list of features below vvvv.

#### Features

```
from dslab.dbpath import DBPath
help(DBPath)
```

```
A Utility class for working with DataBricks API paths directly and in a unified manner.

The Design is inspired by pathlib.Path

>>> path = DBPath('abfss://...')
>>> path = DBPath('dbfs:/...')
>>> path = DBPath('file:/...')
>>> path = DBPath('s3:/...')
>>> path = DBPath('s3a:/...')
>>> path = DBPath('s3n:/...')


INITIALIZATION:

>>> from dslab import DBPath

Provide spark session for dbutils instance
>>> DBPath.set_spark_session(spark)

set FileStore base download url for your dbx workspace
>>> DBPath.set_base_download_url('https://adb-1234.5.azuredatabricks.net/files/')


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
tree(max_depth=5, max_files_per_dir=50) - prints the directory structure, up to `max_depth` and 
        `max_files_per_dir` files in each directory
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
```

## Feedback

All feedback is extremely welcome, please raise an issue on github or contact me at adam.volny@datasentics.com

## Contribution

Contributions, extensions are welcome, don't hesitate to post a PR and we will discuss adding the feature.

### Local Environment Setup

The following software needs to be installed first:
  * [Miniconda package manager](https://docs.conda.io/en/latest/miniconda.html)
  * [Git for Windows](https://git-scm.com/download/win) or standard Git in Linux (_apt-get install git_)

Clone the repo now and prepare the package environment:

* On **Windows**, use [Git Bash](docs/git-bash.png).
* On **Linux/Mac**, the use standard console

```bash
$ git clone git@github.com:DataSentics/datasentics-lab.git
$ cd datasentics-lab
$ ./env-init.sh
```

After the environment setup is complete, activate the Conda environment:

```bash
$ conda activate ./.venv
```

### Semantic Commit Messages

We decided to use semantic commit messages for easier long-term maintenance.

We're looking forward to your contributions!

Format: `<type>(<scope>): <subject>`

`<scope>` is optional

## Example

```
feat: add hat wobble
^--^  ^------------^
|     |
|     +-> Summary in present tense.
|
+-------> Type: chore, docs, feat, fix, refactor, style, or test.
```

More Examples:

- `feat`: (new feature for the user, not a new feature for build script)
- `fix`: (bug fix for the user, not a fix to a build script)
- `docs`: (changes to the documentation)
- `style`: (formatting, missing semi colons, etc; no production code change)
- `refactor`: (refactoring production code, eg. renaming a variable)
- `test`: (adding missing tests, refactoring tests; no production code change)
- `cicd`: (updating workflows; no production code change)
- `release`: (changing version in pyproject.toml and commit message: "release: vMAJOR.MINOR.PATCH")

References:

- https://www.conventionalcommits.org/
- https://seesparkbox.com/foundry/semantic_commit_messages
- http://karma-runner.github.io/1.0/dev/git-commit-msg.html