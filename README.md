# bowkin
`bowkin` is a tool for patching ELF binaries to use **specific versions of glibc** (the GNU C standard library).


## Requisites
The [`file`](https://en.wikipedia.org/wiki/File_(command)) command (may not be installed by default in some distro), [PatchELF](https://nixos.org/patchelf.html), and a couple of Python 3 packages:
```
$ pip3 install -r requirements.txt
```

## Installation
1. Clone this repository: `git clone https://github.com/integeruser/bowkin.git ~/.bowkin`
2. (Optional) For convenience, add `bowkin.py` and `bowkin-db.py` to the `PATH` (e.g. `ln -s ~/.bowkin/bowkin.py /usr/local/bin/bowkin` and `ln -s ~/.bowkin/bowkin-db.py /usr/local/bin/bowkin-db`)
3. Download a bunch of libcs: `bowkin-db bootstrap --ubuntu-only`


## Usage
Suppose you want to pwn a CTF challenge, for which you are given a binary and the libc used in remote by the orgs:
```bash
$ ls
challenge  libc.so.6
```
```bash
$ file ./challenge
challenge: ELF 64-bit LSB shared object, x86-64, version 1 (SYSV), dynamically linked, interpreter /lib64/ld-linux-x86-64.so.2, for GNU/Linux 3.2.0, BuildID[sha1]=35bf0d5549463ce1bf1c7040060ee9e70f6a5f98, not stripped
```
```bash
$ strings ./libc.so.6 | grep ubuntu
GNU C Library (Ubuntu GLIBC 2.23-0ubuntu10) stable release version 2.23, by Roland McGrath et al.
<https://bugs.launchpad.net/ubuntu/+source/glibc/+bugs>.
```
For the sake of example, `challenge` just [prints the version of libc it uses during execution](https://sourceware.org/glibc/wiki/FAQ#How_can_I_find_out_which_version_of_glibc_I_am_using_in_the_moment.3F),
```bash
$ ldd ./challenge
        linux-vdso.so.1 (0x00007ffdb0bfe000)
        libc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (0x00007f0fc82c9000)
        /lib64/ld-linux-x86-64.so.2 (0x00007f0fc88bc000)
```
```bash
$ strings /lib/x86_64-linux-gnu/libc.so.6 | grep ubuntu
GNU C Library (Ubuntu GLIBC 2.27-3ubuntu1) stable release version 2.27.
<https://bugs.launchpad.net/ubuntu/+source/glibc/+bugs>.
```
```bash
$ ./challenge
2.27
```
which in this case is the version used by Ubuntu 18.04 at the time of writing.

Let's use `bowkin` to force the binary to use the libc provided.
1. First, identify the library:
```bash
$ bowkin identify /example/libc.so.6
{
    "architecture": "amd64",
    "buildID": "b5381a457906d279073822a5ceb24c4bfef94ddb",
    "distro": "ubuntu",
    "realpath": "/opt/libcs/ubuntu/xenial/libc-amd64-2.23-0ubuntu10.so",
    "release": "xenial",
    "relpath": "ubuntu/xenial/libc-amd64-2.23-0ubuntu10.so",
    "version": "2.23-0ubuntu10"
}
```
2. Then, patch the binary to use the identified library:
```bash
$ bowkin patch /example/challenge /opt/libcs/ubuntu/xenial/libc-amd64-2.23-0ubuntu10.so
Copy:
- /opt/libcs/ubuntu/xenial/ld-amd64-2.23-0ubuntu10.so
- /opt/libcs/ubuntu/xenial/libc-amd64-2.23-0ubuntu10.so
to:
- /example/libs/
? (y/[N]) y

Copy:
- /opt/libcs/ubuntu/xenial/libc-amd64-2.23-0ubuntu10.so.debug
to:
- /example/libs/libc-2.23.so (this particular name is required by GDB to add debug symbols automatically)
? (y/[N]) y

Copy:
- /example/challenge
to:
- /example/challenge-2.23-0ubuntu10
and patch the latter? (y/[N]) y
warning: working around a Linux kernel bug by creating a hole of 2093056 bytes in ‘/example/challenge-2.23-0ubuntu10’
```
That's it! `bowkin` created the patched binary `challenge-2.23-0ubuntu10` and copied the necessary files (the libc to use, its dynamic loader, the debug symbols) into the same directory of the binary:
```bash
$ ls
challenge  challenge-2.23-0ubuntu10  libc.so.6  libs
$ ls libs/
ld-amd64-2.23-0ubuntu10.so  libc-2.23.so  libc-amd64-2.23-0ubuntu10.so
```
Let's test it:
```
$ ./challenge-2.23-0ubuntu10
2.23
```
The patched binary works flawlessly also with `pwntools`' `gdb.attach()` and `gdb.debug()`:
```python
$ cat expl.py
#!/usr/bin/env python2
# -*- coding: utf-8 -*-
from pwn import *

context(arch="amd64", os="linux")

binary = ELF("./challenge-2.23-0ubuntu10")
libc = ELF("libs/libc-amd64-2.23-0ubuntu10.so")

io = gdb.debug(
    args=[binary.path],
    terminal=["tmux", "new-window"],
    gdbscript="""\
        b main
        continue
    """,
)

io.interactive()
```
```bash
$ python ./expl.py
[*] '/example/challenge-2.23-0ubuntu10'
    Arch:     amd64-64-little
    RELRO:    Full RELRO
    Stack:    No canary found
    NX:       NX enabled
    PIE:      PIE enabled
[*] '/example/libs/libc-amd64-2.23-0ubuntu10.so'
    Arch:     amd64-64-little
    RELRO:    Partial RELRO
    Stack:    Canary found
    NX:       NX enabled
    PIE:      PIE enabled
[+] Starting local process '/usr/bin/gdbserver': pid 9852
[*] running in new terminal: /usr/bin/gdb -q  "/example/challenge-2.23-0ubuntu10" -x "/tmp/pwnuZ8Iad.gdb"
[*] Switching to interactive mode
```
...in another tmux window...
```bash
Breakpoint 1, 0x000055f4ad88f69e in main ()
gef➤  vmmap
Start              End                Offset             Perm Path
0x000055f4ad88f000 0x000055f4ad890000 0x0000000000000000 r-x /example/challenge-2.23-0ubuntu10
0x000055f4ada8f000 0x000055f4ada90000 0x0000000000000000 r-- /example/challenge-2.23-0ubuntu10
0x000055f4ada90000 0x000055f4ada91000 0x0000000000001000 rw- /example/challenge-2.23-0ubuntu10
0x000055f4ada91000 0x000055f4ada93000 0x0000000000202000 rw- /example/challenge-2.23-0ubuntu10
0x00007ff879d07000 0x00007ff879ec7000 0x0000000000000000 r-x /example/libs/libc-amd64-2.23-0ubuntu10.so
0x00007ff879ec7000 0x00007ff87a0c7000 0x00000000001c0000 --- /example/libs/libc-amd64-2.23-0ubuntu10.so
0x00007ff87a0c7000 0x00007ff87a0cb000 0x00000000001c0000 r-- /example/libs/libc-amd64-2.23-0ubuntu10.so
0x00007ff87a0cb000 0x00007ff87a0cd000 0x00000000001c4000 rw- /example/libs/libc-amd64-2.23-0ubuntu10.so
0x00007ff87a0cd000 0x00007ff87a0d1000 0x0000000000000000 rw-
0x00007ff87a0d1000 0x00007ff87a0f7000 0x0000000000000000 r-x /example/libs/ld-amd64-2.23-0ubuntu10.so
0x00007ff87a2f3000 0x00007ff87a2f6000 0x0000000000000000 rw-
0x00007ff87a2f6000 0x00007ff87a2f7000 0x0000000000025000 r-- /example/libs/ld-amd64-2.23-0ubuntu10.so
0x00007ff87a2f7000 0x00007ff87a2f8000 0x0000000000026000 rw- /example/libs/ld-amd64-2.23-0ubuntu10.so
0x00007ff87a2f8000 0x00007ff87a2f9000 0x0000000000000000 rw-
0x00007ffe8d97f000 0x00007ffe8d9a0000 0x0000000000000000 rw- [stack]
0x00007ffe8d9c0000 0x00007ffe8d9c3000 0x0000000000000000 r-- [vvar]
0x00007ffe8d9c3000 0x00007ffe8d9c5000 0x0000000000000000 r-x [vdso]
0xffffffffff600000 0xffffffffff601000 0x0000000000000000 r-x [vsyscall]
gef➤  c
Continuing.
```
...back to the first tmux window...
```bash
2.23

Child exited with status 0
[*] Process '/usr/bin/gdbserver' stopped with exit code 0 (pid 9856)
[*] Got EOF while reading in interactive
```

## Usage (cont.)
You can add glibc packages to the database with `bowkin-db add <package>`:
```bash
$ file ./usr/lib/libc-2.22.so
./usr/lib/libc-2.22.so: ELF 32-bit LSB pie executable Intel 80386, version 1 (GNU/Linux), dynamically linked, interpreter /usr/lib/ld-linux.so.2, BuildID[sha1]=faef9af5a88432766d76d7da2cf961c75b6e0e0b, for GNU/Linux 2.6.32, not stripped
$ bowkin identify ./usr/lib/libc-2.22.so
The supplied libc is not in the database.
```
```bash
$ bowkin-db add ./glibc-2.22-4-i686.pkg.tar.xz
[add]
Added: .../ld-i686-2.22-4.so
Added: .../libc-i686-2.22-4.so
[rebuild]
. . .
$ bowkin identify ./usr/lib/libc-2.22.so
{
    "architecture": "i686",
    "buildID": "faef9af5a88432766d76d7da2cf961c75b6e0e0b",
    "distro": null,
    "realpath": "/Users/fcagnin/Google Drive/bowkin-libcs/libcs/libc-i686-2.22-4.so",
    "release": null,
    "relpath": "libc-i686-2.22-4.so",
    "version": "2.22-4"
}
```
```bash
$ bowkin-db add ./libc6_2.23-0ubuntu10_amd64.deb
[add]
Added: .../ld-amd64-2.23-0ubuntu10.so
Added: .../libc-amd64-2.23-0ubuntu10.so
[rebuild]
. . .
$ bowkin-db add ./libc6-dbg_2.23-0ubuntu10_amd64.deb
[add]
Added: .../libc-amd64-2.23-0ubuntu10.so.debug
[rebuild]
. . .
```
