FROM ubuntu:18.04
ENV LANG='C.UTF-8' LC_ALL='C.UTF-8'
LABEL Version=0.0.1 maintainer="comewel, integeruser"

# RUN apt-get update && apt-get install -y --no-install-recommends apt-utils

RUN apt-get update && apt-get install -y \
    build-essential \
    gdb \
    wget \
    python2.7 python-dev git libssl-dev libffi-dev

RUN wget https://bootstrap.pypa.io/get-pip.py && python get-pip.py

RUN pip install --upgrade pip && pip install --upgrade pwntools

RUN wget -O ~/.gdbinit-gef.py -q https://github.com/hugsy/gef/raw/master/gef.py && \
    echo source ~/.gdbinit-gef.py >> ~/.gdbinit

# WORKDIR /opt
# RUN apt-get install wget xz-utils -y
# RUN wget "https://ftp.gnu.org/gnu/gdb/gdb-8.1.tar.xz"
# RUN tar xf gdb-8.1.tar.xz

# WORKDIR /opt/gdb-8.1
# RUN ./configure && make && make install
