FROM base/archlinux
ENV LANG='C.UTF-8'

RUN pacman -Sy && pacman --noconfirm -S \
    gdb nano tmux vim wget \
    python2 python2-pip

RUN wget -O ~/.gdbinit-gef.py -q https://github.com/hugsy/gef/raw/master/gef.py && \
    echo source ~/.gdbinit-gef.py >> ~/.gdbinit

RUN pacman --noconfirm -S python2-capstone python2-psutil && pip2 install pwntools
