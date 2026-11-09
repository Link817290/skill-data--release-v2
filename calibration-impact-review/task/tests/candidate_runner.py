"""Private verifier bootstrap for an offline, unprivileged candidate process."""
import errno
import json
import os
import resource
import socket
import sys

import pyseccomp as seccomp


def main():
    ready = int(sys.argv[1])
    command = sys.argv[2:]
    try:
        if os.geteuid() != 0:
            raise RuntimeError("The private verifier must start this bootstrap as root")
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
        resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
        resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024**2, 32 * 1024**2))
        os.setgroups([])
        os.setresgid(65534, 65534, 65534)
        os.setresuid(65534, 65534, 65534)
        policy = seccomp.SyscallFilter(defaction=seccomp.ALLOW)
        policy.set_attr(seccomp.Attr.CTL_NNP, 1)
        for syscall in ("socket", "socketpair"):
            policy.add_rule(seccomp.ERRNO(errno.EPERM), syscall, seccomp.Arg(0, seccomp.NE, socket.AF_UNIX))
        policy.add_rule(seccomp.ERRNO(errno.EPERM), "io_uring_setup")
        policy.load()
        os.write(ready, json.dumps({"uid": os.getuid(), "network_filter_loaded": True}).encode())
        os.close(ready)
        os.execvpe(command[0], command, os.environ)
    except Exception as error:
        print("Candidate bootstrap failed: " + str(error), file=sys.stderr)
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
