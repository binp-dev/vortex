from __future__ import annotations
from typing import List, Any

import shutil
import re
from pathlib import Path, PurePosixPath

from vortex.utils.path import TargetPath
from vortex.utils.files import substitute
from vortex.tasks.base import task, Context
from vortex.tasks.epics.base import EpicsProject
from vortex.tasks.epics.epics_base import AbstractEpicsBase, EpicsBaseCross, EpicsBaseHost
from vortex.tasks.process import run


class AbstractIoc(EpicsProject):
    def __init__(self, ioc_dir: Path, target_dir: TargetPath, epics_base: AbstractEpicsBase, **kws: Any):
        super().__init__(ioc_dir, target_dir, epics_base.cc, deploy_path=PurePosixPath("/opt/ioc"))
        self.epics_base = epics_base

    @property
    def name(self) -> str:
        raise NotImplementedError()

    @property
    def arch(self) -> str:
        return self.epics_base.arch

    def _configure(self, ctx: Context) -> None:
        build_path = ctx.target_path / self.build_dir
        install_path = ctx.target_path / self.install_dir
        substitute(
            [("^\\s*#*(\\s*EPICS_BASE\\s*=).*$", f"\\1 {ctx.target_path / self.epics_base.install_dir}")],
            build_path / "configure/RELEASE",
        )
        substitute(
            [("^\\s*#*(\\s*INSTALL_LOCATION\\s*=).*$", f"\\1 {install_path}")],
            build_path / "configure/CONFIG_SITE",
        )
        install_path.mkdir(exist_ok=True)

    def _post_install(self, ctx: Context) -> None:
        shutil.rmtree(
            ctx.target_path / self.install_dir / "iocBoot",
            ignore_errors=True,
        )
        shutil.copytree(
            ctx.target_path / self.build_dir / "iocBoot",
            ctx.target_path / self.install_dir / "iocBoot",
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("Makefile"),
        )

    @task
    def build(self, ctx: Context) -> None:
        self.epics_base.build(ctx)
        super().build(ctx, clean=True)
        self._post_install(ctx)

    @task
    def deploy(self, ctx: Context) -> None:
        self.epics_base.deploy(ctx)
        super().deploy(ctx)

    @task
    def run(self, ctx: Context, addr_list: List[str] = []) -> None:
        raise NotImplementedError()


class IocHost(AbstractIoc):
    def __init__(self, ioc_dir: Path, target_dir: TargetPath, epics_base: EpicsBaseHost):
        super().__init__(ioc_dir, target_dir, epics_base)

    @task
    def run(self, ctx: Context, addr_list: List[str] = []) -> None:
        self.build(ctx)

        name = self.name
        epics_base_dir = ctx.target_path / self.epics_base.install_dir
        ioc_dir = ctx.target_path / self.install_dir
        arch = self.arch

        binary = ioc_dir / "bin" / arch / name
        script = ioc_dir / f"iocBoot/ioc{name}/st.cmd"
        args = [binary, script]
        cwd = script.parent
        lib_dirs = [epics_base_dir / "lib" / arch, ioc_dir / "lib" / arch]
        env = {
            **(
                {
                    "EPICS_CA_AUTO_ADDR_LIST": "NO",
                    "EPICS_CA_ADDR_LIST": ",".join(addr_list),
                }
                if len(addr_list) > 0
                else {}
            ),
            "LD_LIBRARY_PATH": ":".join([str(p) for p in lib_dirs]),
        }

        run(ctx, args, cwd=cwd, env=env)


class IocCross(AbstractIoc):
    def __init__(self, ioc_dir: Path, target_dir: TargetPath, epics_base: EpicsBaseCross):
        super().__init__(ioc_dir, target_dir, epics_base)
        self.epics_deploy_path = epics_base.deploy_path

    def _configure(self, ctx: Context) -> None:
        super()._configure(ctx)
        substitute(
            [("^\\s*#*(\\s*CROSS_COMPILER_TARGET_ARCHS\\s*=).*$", f"\\1 {self.arch}")],
            ctx.target_path / self.build_dir / "configure/CONFIG_SITE",
        )

    def _post_deploy(self, ctx: Context) -> None:
        assert ctx.device is not None
        boot_dir = ctx.target_path / self.install_dir / "iocBoot"
        for ioc_name in [path.name for path in boot_dir.iterdir()]:
            ioc_dirs = boot_dir / ioc_name
            if not ioc_dirs.is_dir():
                continue
            env_path = ioc_dirs / "envPaths"
            if not env_path.is_file():
                continue
            with open(env_path, "r") as f:
                text = f.read()
            text = re.sub(r'(epicsEnvSet\("TOP",)[^\n]+', f'\\1"{self.deploy_path}")', text)
            text = re.sub(r'(epicsEnvSet\("EPICS_BASE",)[^\n]+', f'\\1"{self.epics_deploy_path}")', text)
            ctx.device.store_mem(text, self.deploy_path / "iocBoot" / ioc_name / "envPaths")
