FROM ubuntu:18.04
ENV LANG='C.UTF-8' LC_ALL='C.UTF-8'
LABEL Version=0.0.1 maintainer='comewel, integeruser'

RUN apt-get update && apt-get install -y \
    build-essential gdb nano vim wget \
    python python-pip libssl-dev libffi-dev

RUN wget -O ~/.gdbinit-gef.py -q https://github.com/hugsy/gef/raw/master/gef.py && \
    echo source ~/.gdbinit-gef.py >> ~/.gdbinit

RUN pip install pwntools
