Install Docker
---

See https://docs.docker.com/install/linux/docker-ce/ubuntu/

Install Miniconda3
---

See https://www.anaconda.com/rpm-and-debian-repositories-for-miniconda/

Install stackless python
---

See https://github.com/stackless-dev/stackless/wiki/Download

Install pycharm
---

* apt-get install pycharm-community

Setup pycharm interpreter
---

* Go to settings, Project Interpreter
* create a new interpreter, click on the "use conda" tab
* Add the path to conda bin (/opt/conda/bin/conda)

Setup pycharm plugins
---
* Install Docker plugin
* Install Makefile plugin
* restart pycharm

Setup the conda environment
---
* in a terminal:
* source /opt/conda/etc/profile.d/conda.sh
* conda activate HavokMud-redux
* conda config --add channels stackless
* conda install stackless
* conda update python
* conda install boto3 jinja2
* pip install ansicolors python-statemachine
