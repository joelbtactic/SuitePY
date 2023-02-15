[![license](https://img.shields.io/github/license/sanchezfauste/SuitePY.svg?style=flat-square)](LICENSE)
[![readthedocs](https://readthedocs.org/projects/suitepy/badge/?version=latest&style=flat-square)](https://suitepy.readthedocs.io/en/latest/)
[![GitHub (pre-)release](https://img.shields.io/github/release/sanchezfauste/SuitePY/all.svg?style=flat-square)](https://github.com/sanchezfauste/SuitePY/releases/latest)

# SuitePY

Suite PY is a simple Python client for SuiteCRM API.

## How to prepare the environment on Linux (Debian)
In this section is described how to get the development environment ready on Debian based systems.

It's recommended to use `virtualenv` and `pip` packages. You can install this two dependencies runnig:
```bash
sudo apt-get update
sudo apt-get install virtualenv python-pip
```

Once you have `virtualenv` and `pip` tools ready it's time to prepare the virtual environment to run the application.  
Following we create a virtual environment and install all Python dependencies:
```bash
cd SuitePY
virtualenv env
source env/bin/activate
pip install -r requirements.txt
```

## PDF Templates support
To be able to use get_pdf_template method, you need to install a custom WebService on your SuiteCRM instance:

1. Download zip of [latest SuitePY-service release](https://github.com/sanchezfauste/SuitePY-service/releases/latest) and install it using Module Loader.
	1.1 For Suitecrm versions 7.10 or superior, uncompress zip and find manifest.php, then compress all files in the dir creating the new module you have to install. 
2. Edit `suitepy.ini` config file and change the `url` parameter to `https://crm.example.com/custom/service/suitepy/rest.php`.
