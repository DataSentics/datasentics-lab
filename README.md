# DataSentics Python package skeleton

## 1. Local environment setup

The following software needs to be installed first:
  * [Miniconda package manager](https://docs.conda.io/en/latest/miniconda.html)
  * [Git for Windows](https://git-scm.com/download/win) or standard Git in Linux (_apt-get install git_)
  * [PyCharm 2019.2 Community](https://www.jetbrains.com/pycharm/download/)

Clone the repo now and prepare the package environment:

* On **Windows**, use [Git Bash](docs/git-bash.png).
* On **Linux/Mac**, the use standard console

```bash
$ git clone git@github.com:DataSentics/package-example.git
$ cd package-example
$ export POETRY_HTTP_BASIC_DATASENTICS_USERNAME="dummy"
$ export POETRY_HTTP_BASIC_DATASENTICS_PASSWORD="{DEVOPS_TOKEN}"
$ ./env-init.sh
```

After the environment setup is complete, activate the Conda environment:

```bash
$ conda activate [projectRoot]/.venv
```
