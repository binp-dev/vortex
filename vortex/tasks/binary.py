from __future__ import annotations

from dataclasses import dataclass

from vortex.utils.path import TargetPath
from vortex.utils.run import run

from .base import Context, Component, task


@dataclass
class DynamicLib(Component):
    lib_dir: TargetPath
    lib_name: str

    @property
    def lib_file(self) -> str:
        return f"lib{self.lib_name}.so"

    @property
    def lib_path(self) -> TargetPath:
        return self.lib_dir / self.lib_file

    @task
    def build(self, ctx: Context) -> None:
        raise NotImplementedError()


@dataclass
class Executable(Component):
    exec_dir: TargetPath
    exec_name: str

    @property
    def exec_path(self) -> TargetPath:
        return self.exec_dir / self.exec_name

    @task
    def build(self, ctx: Context) -> None:
        raise NotImplementedError()

    @task
    def run(self, ctx: Context) -> None:
        self.build(ctx)
        run([ctx.target_path / self.exec_path], quiet=ctx.capture)
