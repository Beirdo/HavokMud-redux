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

* wget https://download.jetbrains.com/toolbox/jetbrains-toolbox-1.16.6319.tar.gz -O /tmp/jetbrains-toolbox.tar.gz
* mkdir -p ~/bin
* tar -C /tmp -xvf jetbrains-toolbox.tar.gz
* mv /tmp/jetbrains-toolbox-1.16.6319/jetbrains-toolbox ~/bin/
* ~/bin/jetbrains-toolbox &
* install pycharm community edition

Setup pycharm interpreter
---

* Go to settings, Project Interpreter
* create a new interpreter, click on the "use conda" tab
* Add the path to conda bin (/opt/conda/bin/conda)

Setup pycharm plugins
---
* Install Docker plugin
* Install Makefile plugin
* Install .ignore plugin
* restart pycharm

Setup the conda environment
---
* in a terminal:
* source /opt/conda/etc/profile.d/conda.sh
* conda init
* source ~/.bashrc
* conda create --name HavokMud-redux
* conda activate HavokMud-redux
* ```
  cat >> ~/.bashrc << EOF

  conda activate HavokMud-redux
  EOF

* conda config --add channels stackless
* conda install stackless
* conda update python
* pip install ansicolors python-statemachine dnspython

Setup localstack for testing
---
* pip install localstack
* localstack start  (runs in Docker)

Setup screen
---
* apt-get install screen
