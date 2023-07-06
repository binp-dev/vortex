from __future__ import annotations
from typing import List

from pathlib import Path, PurePosixPath

from vortex.utils.run import run
from vortex.dst.base import Dst

import logging

logger = logging.getLogger(__name__)


class Fs(Dst):
    def __init__(self, path: Path):
        super().__init__()
        self.path = path

    def mkdir(
        self,
        dst: PurePosixPath,
        exist_ok: bool = False,
        recursive: bool = False,
    ) -> None:
        path = self.path / dst.relative_to(Path("/"))
        path.mkdir(exist_ok=exist_ok, parents=recursive)

    def store(
        self,
        src: Path,
        dst: PurePosixPath,
        recursive: bool = False,
        exclude: List[str] = [],
        include: List[str] = [],
    ) -> None:
        path = self.path / dst.relative_to(Path("/"))
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

    def store_mem(self, src_data: str, dst_path: PurePosixPath) -> None:
        path = self.path / dst_path.relative_to(Path("/"))
        logger.debug(f"Store {len(src_data)} chars to {path}")
        path.parent.mkdir(exist_ok=True, parents=True)
        logger.debug(src_data)
        with open(path, "w") as f:
            f.write(src_data)

    def name(self) -> str:
        return str(self.path)
