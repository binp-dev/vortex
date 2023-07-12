from __future__ import annotations
from typing import List, Optional

import time
from subprocess import Popen
from pathlib import Path, PurePosixPath

from vortex.utils.run import run, RunError
from vortex.utils.string import quote
from vortex.output.base import Connection, Output, Device

import logging

logger = logging.getLogger(__name__)


class SshConnection(Connection):
    def __init__(self, proc: Popen[bytes]) -> None:
        self.proc = proc

    def close(self) -> None:
        self.proc.terminate()


class SshOutput(Output):
    def __init__(
        self,
        host: str,
        path: PurePosixPath,
        port: Optional[int] = None,
        user: Optional[str] = None,
    ):
        super().__init__()

        self.host = host
        self.path = path
        self.user = user if user is not None else "root"
        self.port = port if port is not None else 22

    def name(self) -> str:
        return f"{self.user}@{self.host}:{self.port}{self.path}"

    def _prefix(self) -> List[str]:
        return ["ssh", "-p", str(self.port), f"{self.user}@{self.host}"]

    def _full_path(self, path: PurePosixPath) -> PurePosixPath:
        return self.path / path.relative_to(PurePosixPath("/"))

    def mkdir(
        self,
        path: PurePosixPath,
        exist_ok: bool = False,
        recursive: bool = False,
    ) -> None:
        run([*self._prefix(), f"mkdir {'-p' if exist_ok or recursive else ''} {self._full_path(path)}"])

    def copy(
        self,
        src: Path,
        path: PurePosixPath,
        recursive: bool = False,
        exclude: List[str] = [],
        include: List[str] = [],
    ) -> None:
        full_path = self._full_path(path)
        if not recursive:
            assert len(exclude) == 0 and len(include) == 0, "'exclude' and 'include' are not supported in non-recursive mode"
            run(["bash", "-c", f"test -f {src} && cat {src} | {' '.join(self._prefix())} 'cat > {full_path}'"])
        else:
            run(
                [
                    "rsync",
                    "-rlpt",
                    *["--include=" + mask for mask in include],
                    *["--exclude=" + mask for mask in exclude],
                    "--progress",
                    "--rsh",
                    f"ssh -p {self.port}",
                    f"{src}/",
                    f"{self.user}@{self.host}:{full_path}",
                ]
            )

    def store(self, data: bytes, path: PurePosixPath) -> None:
        logger.debug(f"Store {len(data)} bytes to {self.name()}{path}")
        logger.debug(f"{data!r}")
        run([*self._prefix(), f"cat > {self._full_path(path)}"], input=data)

    def link(self, path: PurePosixPath, target: PurePosixPath) -> None:
        run([*self._prefix(), f"ln -s {target} {self._full_path(path)}"])


class SshDevice(SshOutput, Device):
    def __init__(
        self,
        host: str,
        port: Optional[int] = None,
        user: Optional[str] = None,
    ):
        super().__init__(host, PurePosixPath("/"), port=port, user=user)

    def run(self, args: List[str], wait: bool = True) -> Optional[SshConnection]:
        argstr = " ".join([quote(a) for a in args])
        if wait:
            logger.info(f"SSH run {self.name()} {args}")
            run(self._prefix() + [argstr])
            return None
        else:
            logger.info(f"SSH popen {self.name()} {args}")
            return SshConnection(Popen(self._prefix() + [argstr]))

    def wait_online(self, attempts: int = 10, timeout: float = 10.0) -> None:
        time.sleep(timeout)
        for i in range(attempts - 1, -1, -1):
            try:
                self.run(["uname", "-a"])
            except RunError:
                if i > 0:
                    time.sleep(timeout)
                    continue
                else:
                    raise
            else:
                conn = True
                break

    def reboot(self) -> None:
        try:
            self.run(["reboot", "now"])
        except:
            pass

        logger.info("Waiting for device to reboot ...")
        self.wait_online()
        logger.info("Rebooted")
