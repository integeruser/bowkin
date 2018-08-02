# bowkin
`bowkin` is a tool for creating and spawning Docker containers preconfigured with `gdb`, `pwntools` and **specific versions of libc**, to make the debugging (and exploiting) of binaries faster and less painful.

The tool is very much a **work in progress** and likely to change considerably as it matures.

## Requisites
[Docker](https://www.docker.com/), and required dependencies:
```
$ pip3 install -r requirements.txt
```

## Usage
0. Download some libcs and loaders:
```
$ ./bowkin.py fetch
Processing: libc6_2.19-0ubuntu6.14_i386.deb
Processing: libc6_2.19-0ubuntu6.14_amd64.deb
. . .
```
1. Identify an unknown libc:
```
$ ./bowkin.py identify ./libc.so.6
[
    {
        "architecture": "amd64",
        "distro": "ubuntu",
        "filepath": "libcs/ubuntu/trusty/libc-amd64-2.19-0ubuntu6.14.so",
        "release": "trusty",
        "version": "2.19-0ubuntu6.14"
    }
]
```
2. Spawn a Docker container for working with a specific libc:
```
$ ./bowkin-dickerize.py run bases/ubuntu-amd64.dockerfile libcs/ubuntu/trusty/libc-amd64-2.19-0ubuntu6.14.so --share ~/Downloads/
Error: No such object: bowkin-ubuntu-amd64
Sending build context to Docker daemon  3.072kB
Step 1/3 : FROM amd64/ubuntu
latest: Pulling from amd64/ubuntu
c64513b74145: Pull complete
01b8b12bad90: Pull complete
. . .
Successfully tagged bowkin-ubuntu-amd64-ubuntu-libc-amd64-2.19-0ubuntu6.14:latest
Error: No such container: bowkin-ubuntu-amd64-ubuntu-libc-amd64-2.19-0ubuntu6.14
root@9fd52a4fa74c:/home#
root@1ec1293f9fda:/home# cd share/
root@1ec1293f9fda:/home/share# ls
expl.py  test.c
```
```
root@1ec1293f9fda:/home/share# cat test.c
#include <stdio.h>
#include <gnu/libc-version.h>
int main (void) { puts (gnu_get_libc_version ()); return 0; }
root@1ec1293f9fda:/home/share# gcc -o test ./test.c
root@1ec1293f9fda:/home/share# ./test
2.27
root@1ec1293f9fda:/home/share# LD_PRELOAD=/env/lib/x86_64-linux-gnu/libc.so.6 /env/lib64/ld-linux-x86-64.so.2 ./test
2.19
root@1ec1293f9fda:/home/share# chroot /env /home/share/test
2.19
```
```
root@1ec1293f9fda:/home/share# gdb -q
GEF for linux ready, type `gef' to start, `gef config' to configure
65 commands loaded for GDB 8.1.0.20180409-git using Python engine 3.6
[*] 5 commands could not be loaded, run `gef missing` to know why.
gef➤  set exec-wrapper chroot /env
gef➤  file /home/share/test
Reading symbols from /home/share/test...(no debugging symbols found)...done.
gef➤  r
Starting program: /home/share/test
2.19
[Inferior 1 (process 28) exited normally]
```
```
root@1ec1293f9fda:/home/share# cat expl.py
#!/usr/bin/env python2
from pwn import *

# gdb.debug() was patched during container build to start gdb with chroot as wrapper

argv = ['/home/share/test']  # put your binary in a /home subdirectory and specify the full path

io = gdb.debug(args=argv, gdbscript='''\
    continue
''')
io.interactive()
root@1ec1293f9fda:/home/share# tmux
root@1ec1293f9fda:/home/share# python2 ./expl.py
[+] Starting local process '/usr/bin/gdbserver': pid 72
[*] running in new terminal: /usr/bin/gdb -q  "/home/share/test" -x "/tmp/pwnkJ_XOg.gdb"
[*] Switching to interactive mode
Remote debugging from host 127.0.0.1
2.19

Child exited with status 0
[*] Got EOF while reading in interactive
```
