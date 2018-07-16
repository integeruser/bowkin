FROM arm64v8/ubuntu
ENV LANG='C.UTF-8' LC_ALL='C.UTF-8'
RUN apt-get update && apt-get install -y \
    build-essential gdb nano tmux vim wget \
    python python-pip \
    && \
    wget -O ~/.gdbinit-gef.py -q https://github.com/hugsy/gef/raw/master/gef.py && \
    echo source ~/.gdbinit-gef.py >> ~/.gdbinit \
    && \
    apt-get update && apt-get install -y libssl-dev libffi-dev && pip2 install pwntools
