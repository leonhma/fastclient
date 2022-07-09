# python_package_automation

This is a template that contains workflows to automatically perform testing, publish release assets and push them to pypi on release, issue templates, workflow cleanup, and some quality-of-life for python packages.

<!--cut-->
## How to use this template

### Setup

* First, think of a name for your package. Make sure it's not yet taken on pypi and testpypi.
* Second, click 'use this template' in the upper right corner
* Name your repository the name you have just thought of (non alphanumeric characters will automatically be replaced with undescores, while combining multiple consecutive illegal character into a single underscore), set a description and choose a license. This will enable the setup workflow to automatically fill in some of the details in the package files.
* You should now see a job 'setup' pop up (after ca. 10 sec, you might have to refresh the page). Wait for it to finish and move on.
<!--cut-->

## Automated distribution on release

* Sign up for an account at testpypi and pypi
* Under account settings (in your pypi account) select API tokens and create a new one with the **permission to upload to the entire account**.
* Go to the settings page in your repo and select secrets, click 'add secret' and paste your token from testpypi into a secret named 'TEST_PYPI_PASSWD' and the one from pypi to 'PYPI_PASSWD'.
* You are now able to create a release. Choose a tag name that contains only alphanumericals, underscores and dots. If you select 'This is a prerelease', your package will only be uploaded to testpypi, if you don't, it will be uploaded to both testpypi and pypi.

## ReadTheDocs

If you want to host your documentation on ReadTheDocs, everything is already set up for you. Just go to [readthedocs.org](readthedocs.org), create a new project, and fill in some details. (Pro tip: Link your GitHub with RTD and choose to generate previews for pull-requests.

All documentation is written using reStructuredText files, and converted to html by Sphinx. Sphinx by default has the `napoleon`, `autodoc`, `intersphinx` and `coverage` extensions enabled.

For the Sphinx-generated documentation preview to work, you'll have to click `Use docutils` in the bottom status bar and select `Sphinx` while editing a `.rst` file. Now you can press `Ctrl+Shift+P` and select `reStructuredText: Open Preview (to the Side)`.

## Automatic unittesting

* If you're familiar with the python testing framework `unittest`, this is for you.
* Write your test like you normally would. With every push, your tests are run against the code you wrote. If your project depends on libraries, you can add a `requirements.txt` file at the root level, or just let `setup.py` do it's thing.

## FOSSA analysis

If you want to use FOSSA to analyze your code for license violations, vulnerabilities and quality management (coming soon), you can include a fossa api key in your secrets as `FOSSA_API_KEY`.

## Some extra stuff

* Tests are automatically skipped if no tests are found
* Tests have to be in files following the pattern `test*.py`
* If the code changes are from a pull-request, a comment in the discussion about the test results will be made
* Take a look at [shields.io](shields.io) and search for 'github'. You'll get an idea of what badges in your readme can be used for!
* You can use the placeholder `[vermin]` in your release notes. It will dynamically be replaced with the version requirements of this package.
* For codespaces users: It might take some time for the config to be loaded successfully. After loading into the codespace for the first time, just lean back for a minute, don't touch anything and then hit refresh.
