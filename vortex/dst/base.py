from __future__ import annotations
from typing import List, Optional

from pathlib import Path, PurePosixPath


class Connection:
    def close(self) -> None:
        raise NotImplementedError()


class Dst:
    def name(self) -> str:
        raise NotImplementedError()

    def mkdir(
        self,
        path: PurePosixPath,
        exist_ok: bool = False,
        recursive: bool = False,
    ) -> None:
        raise NotImplementedError()

    def store(
        self,
        local_path: Path,
        remote_path: PurePosixPath,
        recursive: bool = False,
        exclude: List[str] = [],
        include: List[str] = [],
    ) -> None:
        raise NotImplementedError()

    def store_mem(self, src_data: str, dst_path: PurePosixPath) -> None:
        raise NotImplementedError()


class Device(Dst):
    def run(self, args: List[str], wait: bool = False) -> Optional[Connection]:
        raise NotImplementedError()

    def reboot(self) -> None:
        raise NotImplementedError()
