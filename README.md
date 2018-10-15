# bowkin
`bowkin` is a tool for patching binaries to use **specific versions of glibc** (the GNU C standard library).


## Requisites
[PatchELF](https://nixos.org/patchelf.html), and a bunch of Python 3 packages:
```
$ pip3 install -r requirements.txt
```

## Usage
Suppose you're pwning a CTF challenge, for which you were given a binary and the libc used in remote:
```
$ ls
challenge  libc.so.6
```
```
$ file ./challenge
challenge: ELF 64-bit LSB shared object, x86-64, version 1 (SYSV), dynamically linked, interpreter /lib64/ld-linux-x86-64.so.2, for GNU/Linux 3.2.0, BuildID[sha1]=35bf0d5549463ce1bf1c7040060ee9e70f6a5f98, not stripped
$ strings ./libc.so.6 | grep ubuntu
GNU C Library (Ubuntu GLIBC 2.23-0ubuntu10) stable release version 2.23, by Roland McGrath et al.
<https://bugs.launchpad.net/ubuntu/+source/glibc/+bugs>.
```
For the sake of example, the binary just [prints the version of libc it uses during execution](https://sourceware.org/glibc/wiki/FAQ#How_can_I_find_out_which_version_of_glibc_I_am_using_in_the_moment.3F):
```
$ ./challenge
2.27
```
which is the version of the libc used by my system (Ubuntu 18.04) at the time of writing.
```
$ ldd ./challenge
        linux-vdso.so.1 (0x00007ffdb0bfe000)
        libc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (0x00007f0fc82c9000)
        /lib64/ld-linux-x86-64.so.2 (0x00007f0fc88bc000)
$ strings /lib/x86_64-linux-gnu/libc.so.6 | grep ubuntu
GNU C Library (Ubuntu GLIBC 2.27-3ubuntu1) stable release version 2.27.
<https://bugs.launchpad.net/ubuntu/+source/glibc/+bugs>.
```

So, let's use `bowkin` to make the binary use the libc provided for the challenge.
1. First, identify the library:
```
$ ./bowkin.py identify /example/libc.so.6
{
    "architecture": "amd64",
    "buildID": "b5381a457906d279073822a5ceb24c4bfef94ddb",
    "distro": "ubuntu",
    "filepath": "libcs/ubuntu/xenial/libc-amd64-2.23-0ubuntu10.so",
    "release": "xenial",
    "version": "2.23-0ubuntu10"
}
```
It's a match!

2. Second, patch the binary to use `libc-amd64-2.23-0ubuntu10.so`:
```
$ ./bowkin-patchelf.py /example/challenge libcs/ubuntu/xenial/libc-amd64-2.23-0ubuntu10.so
Copy libcs/ubuntu/xenial/ld-amd64-2.23-0ubuntu10.so, libcs/ubuntu/xenial/libc-amd64-2.23-0ubuntu10.so and libcs/ubuntu/xenial/libc-dbg-amd64-2.23-0ubuntu10.so to /example? (y/[N]) y
Copy /example/challenge to /example/challenge-2.23-0ubuntu10 and patch the latter? (y/[N]) y
warning: working around a Linux kernel bug by creating a hole of 2093056 bytes in ‘/example/challenge-2.23-0ubuntu10’
Done.
```
Annnnd, that's it! `bowkin` patched `challenge` to `challenge-2.23-0ubuntu10` and copied the necessary files (the libc to use, its dynamic loader, the debug symbols) to the same directory of the binary:
```
$ ls
challenge  challenge-2.23-0ubuntu10  ld-amd64-2.23-0ubuntu10.so  libc-2.23.so  libc-amd64-2.23-0ubuntu10.so  libc.so.6
```
Let's test it:
```
$ ./challenge-2.23-0ubuntu10
2.23
```
The patched binary works flawlessly also with `pwntools`'s `gdb.attach()` and `gdb.debug()`:
```python
$ cat expl.py
#!/usr/bin/env python2
# -*- coding: utf-8 -*-
from pwn import *

context(arch="amd64", os="linux")

binary = ELF("./challenge-2.23-0ubuntu10")

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
```
$ python ./expl.py
[*] '/example/challenge-2.23-0ubuntu10'
    Arch:     amd64-64-little
    RELRO:    Full RELRO
    Stack:    No canary found
    NX:       NX enabled
    PIE:      PIE enabled
[+] Starting local process '/usr/bin/gdbserver': pid 9852
[*] running in new terminal: /usr/bin/gdb -q  "/example/challenge-2.23-0ubuntu10" -x "/tmp/pwnuZ8Iad.gdb"
[*] Switching to interactive mode
```
...in another tmux window...
```
Breakpoint 1, 0x000055f4ad88f69e in main ()
gef➤  vmmap
Start              End                Offset             Perm Path
0x000055f4ad88f000 0x000055f4ad890000 0x0000000000000000 r-x /example/challenge-2.23-0ubuntu10
0x000055f4ada8f000 0x000055f4ada90000 0x0000000000000000 r-- /example/challenge-2.23-0ubuntu10
0x000055f4ada90000 0x000055f4ada91000 0x0000000000001000 rw- /example/challenge-2.23-0ubuntu10
0x000055f4ada91000 0x000055f4ada93000 0x0000000000202000 rw- /example/challenge-2.23-0ubuntu10
0x00007ff879d07000 0x00007ff879ec7000 0x0000000000000000 r-x /example/libc-amd64-2.23-0ubuntu10.so
0x00007ff879ec7000 0x00007ff87a0c7000 0x00000000001c0000 --- /example/libc-amd64-2.23-0ubuntu10.so
0x00007ff87a0c7000 0x00007ff87a0cb000 0x00000000001c0000 r-- /example/libc-amd64-2.23-0ubuntu10.so
0x00007ff87a0cb000 0x00007ff87a0cd000 0x00000000001c4000 rw- /example/libc-amd64-2.23-0ubuntu10.so
0x00007ff87a0cd000 0x00007ff87a0d1000 0x0000000000000000 rw-
0x00007ff87a0d1000 0x00007ff87a0f7000 0x0000000000000000 r-x /example/ld-amd64-2.23-0ubuntu10.so
0x00007ff87a2f3000 0x00007ff87a2f6000 0x0000000000000000 rw-
0x00007ff87a2f6000 0x00007ff87a2f7000 0x0000000000025000 r-- /example/ld-amd64-2.23-0ubuntu10.so
0x00007ff87a2f7000 0x00007ff87a2f8000 0x0000000000026000 rw- /example/ld-amd64-2.23-0ubuntu10.so
0x00007ff87a2f8000 0x00007ff87a2f9000 0x0000000000000000 rw-
0x00007ffe8d97f000 0x00007ffe8d9a0000 0x0000000000000000 rw- [stack]
0x00007ffe8d9c0000 0x00007ffe8d9c3000 0x0000000000000000 r-- [vvar]
0x00007ffe8d9c3000 0x00007ffe8d9c5000 0x0000000000000000 r-x [vdso]
0xffffffffff600000 0xffffffffff601000 0x0000000000000000 r-x [vsyscall]
gef➤  c
Continuing.
```
...back to the first tmux window...
```
2.23

Child exited with status 0
[*] Process '/usr/bin/gdbserver' stopped with exit code 0 (pid 9856)
[*] Got EOF while reading in interactive
```
