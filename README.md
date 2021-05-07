# DataSentics Python package skeleton

# Local Environment Setup

The following software needs to be installed first:
  * [Miniconda package manager](https://docs.conda.io/en/latest/miniconda.html)
  * [Git for Windows](https://git-scm.com/download/win) or standard Git in Linux (_apt-get install git_)

Clone the repo now and prepare the package environment:

* On **Windows**, use [Git Bash](docs/git-bash.png).
* On **Linux/Mac**, the use standard console

```bash
$ git clone git@github.com:DataSentics/package-example.git
$ cd package-example
$ ./env-init.sh
```

After the environment setup is complete, activate the Conda environment:

```bash
$ conda activate [projectRoot]/.venv
```


# Contribution

## Semantic Commit Messages

See how a minor change to your commit message style can make you a better programmer.

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