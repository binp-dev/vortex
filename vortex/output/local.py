from __future__ import annotations
from typing import List

from pathlib import Path, PurePosixPath

from vortex.utils.run import run
from vortex.output.base import Output

import logging

logger = logging.getLogger(__name__)


class Local(Output):
    def __init__(self, path: Path):
        super().__init__()
        self.path = path

    def name(self) -> str:
        return str(self.path)

    def _full_path(self, path: PurePosixPath) -> Path:
        return self.path / path.relative_to(PurePosixPath("/"))

    def mkdir(
        self,
        path: PurePosixPath,
        exist_ok: bool = False,
        recursive: bool = False,
    ) -> None:
        self._full_path(path).mkdir(exist_ok=exist_ok, parents=recursive)

    def copy(
        self,
        src: Path,
        dst: PurePosixPath,
        recursive: bool = False,
        exclude: List[str] = [],
        include: List[str] = [],
    ) -> None:
        path = self._full_path(dst)
        path.parent.mkdir(exist_ok=True, parents=True)
        if not recursive:
            assert len(exclude) == 0, "'exclude' is not supported"
            run(["cp", "-f", src, path])
        else:
            run(
                [
                    "rsync",
                    "-rlpt",
                    *["--include=" + mask for mask in include],
                    *["--exclude=" + mask for mask in exclude],
                    "--progress",
                    f"{src}/",
                    f"{path}",
                ]
            )

    def store(self, data: bytes, path: PurePosixPath) -> None:
        full_path = self._full_path(path)
        logger.debug(f"Store {len(data)} bytes to {full_path}")
        full_path.parent.mkdir(exist_ok=True, parents=True)
        logger.debug(f"{data!r}")
        with open(full_path, "wb") as f:
            f.write(data)

    def link(self, path: PurePosixPath, target: PurePosixPath) -> None:
        self._full_path(path).symlink_to(target)
