from __future__ import annotations
from typing import List

from pathlib import Path, PurePosixPath
from dataclasses import dataclass

from vortex.utils.path import TargetPath, prepend_if_target
from vortex.utils.files import substitute
from vortex.tasks.base import task, Context, Component
from vortex.tasks.git import RepoList, RepoSource
from vortex.tasks.compiler import Gcc, HOST_GCC
from vortex.tasks.epics.base import EpicsProject, epics_host_arch

import logging

logger = logging.getLogger(__name__)


@dataclass
class EpicsSource(Component):
    src_dir: Path | TargetPath
    prefix: TargetPath

    @task
    def clone(self, ctx: Context) -> None:
        pass


class EpicsRepo(RepoList, EpicsSource):
    def __init__(self, version: str, target_dir: TargetPath):
        prefix = target_dir / version
        path = prefix / "src"
        EpicsSource.__init__(self, path, prefix)
        RepoList.__init__(
            self,
            path,
            [
                RepoSource("https://gitlab.inp.nsk.su/epics/epics-base.git", f"binp-R{version}"),
                RepoSource("https://github.com/epics-base/epics-base.git", f"R{version}"),
            ],
        )


class AbstractEpicsBase(EpicsProject):
    def __init__(
        self,
        source: EpicsSource,
        target_dir: TargetPath,
        cc: Gcc,
    ) -> None:
        self.source = source
        super().__init__(
            self.source.src_dir,
            target_dir,
            cc,
            deploy_path=PurePosixPath("/opt/epics_base"),
        )

    def _configure_common(self, ctx: Context) -> None:
        defs = [
            ("BIN_PERMISSIONS", "755"),
            ("LIB_PERMISSIONS", "644"),
            ("SHRLIB_PERMISSIONS", "755"),
            ("INSTALL_PERMISSIONS", "644"),
        ]
        rules = [(f"^(\\s*{k}\\s*=).*$", f"\\1 {v}") for k, v in defs]
        logger.info(rules)
        substitute(
            rules,
            ctx.target_path / self.build_dir / "configure/CONFIG_COMMON",
        )

    def _configure_toolchain(self, ctx: Context) -> None:
        raise NotImplementedError()

    def _configure_install(self, ctx: Context) -> None:
        substitute(
            [("^\\s*#*(\\s*INSTALL_LOCATION\\s*=).*$", f"\\1 {ctx.target_path / self.install_dir}")],
            ctx.target_path / self.build_dir / "configure/CONFIG_SITE",
        )

    def _configure(self, ctx: Context) -> None:
        self._configure_common(ctx)
        self._configure_toolchain(ctx)
        self._configure_install(ctx)

    @task
    def build(self, ctx: Context) -> None:
        self.source.clone(ctx)
        super().build(ctx, clean=False)

    @property
    def deploy_blacklist(self) -> List[str]:
        return [
            *super().deploy_blacklist,
            # "**.a",
            # "/include",
            "/html",
            "/templates",
        ]

    @task
    def deploy(self, ctx: Context) -> None:
        self.build(ctx)
        super().deploy(ctx)


class EpicsBaseHost(AbstractEpicsBase):
    def __init__(self, source: EpicsSource, target_dir: TargetPath) -> None:
        super().__init__(source, target_dir, HOST_GCC)

    def _configure_toolchain(self, ctx: Context) -> None:
        substitute(
            [("^(\\s*CROSS_COMPILER_TARGET_ARCHS\\s*=).*$", "\\1")],
            ctx.target_path / self.build_dir / "configure/CONFIG_SITE",
        )


class EpicsBaseCross(AbstractEpicsBase):
    def _configure_toolchain(self, ctx: Context) -> None:
        cc = self.cc

        host_arch = epics_host_arch(prepend_if_target(ctx.target_path, self.source.src_dir))
        cross_arch = self.arch
        assert cross_arch != host_arch

        if cross_arch == "linux-arm" and host_arch.endswith("-x86_64"):
            host_arch = host_arch[:-3]  # Trim '_64'

        substitute(
            [("^(\\s*CROSS_COMPILER_TARGET_ARCHS\\s*=).*$", f"\\1 {cross_arch}")],
            ctx.target_path / self.build_dir / "configure/CONFIG_SITE",
        )
        substitute(
            [
                ("^(\\s*GNU_TARGET\\s*=).*$", f"\\1 {str(cc.target)}"),
                ("^(\\s*GNU_DIR\\s*=).*$", f"\\1 {ctx.target_path / cc.path}"),
                ("^(\\s*SHARED_LIBRARIES\\s*=).*$", f"\\1 YES"),
            ],
            ctx.target_path / self.build_dir / f"configure/os/CONFIG_SITE.{host_arch}.{cross_arch}",
        )

    @property
    def deploy_blacklist(self) -> List[str]:
        return [
            *super().deploy_blacklist,
            "/bin/*",
            "/lib/*",
        ]

    @property
    def deploy_whitelist(self) -> List[str]:
        return [
            *super().deploy_whitelist,
            f"/bin/{self.arch}",
            f"/lib/{self.arch}",
        ]
