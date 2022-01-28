from __future__ import annotations
from typing import Any, Dict, List, Optional

import shutil
import re
import logging
import time
from pathlib import Path, PurePosixPath

from ferrite.utils.files import substitute
from ferrite.components.base import Component, Task, FinalTask, Context
from ferrite.components.toolchain import Toolchain, HostToolchain, CrossToolchain
from ferrite.remote.base import Device, Connection
from ferrite.components.epics.base import EpicsBuildTask, EpicsDeployTask, epics_arch
from ferrite.components.epics.epics_base import EpicsBase, EpicsBaseCross


class IocBuildTask(EpicsBuildTask):

    def __init__(
        self,
        src_dir: Path,
        build_dir: Path,
        install_dir: Path,
        deps: List[Task],
        epics_base_dir: Path,
        toolchain: Toolchain,
    ):
        super().__init__(
            src_dir,
            build_dir,
            install_dir,
            clean=True,
            deps=deps,
        )
        self.epics_base_dir = epics_base_dir
        self.toolchain = toolchain

    def _configure(self) -> None:
        arch = epics_arch(self.epics_base_dir, self.toolchain)
        substitute(
            [("^\\s*#*(\\s*EPICS_BASE\\s*=).*$", f"\\1 {self.epics_base_dir}")],
            self.build_dir / "configure/RELEASE",
        )
        if not isinstance(self.toolchain, HostToolchain):
            substitute(
                [("^\\s*#*(\\s*CROSS_COMPILER_TARGET_ARCHS\\s*=).*$", f"\\1 {arch}")],
                self.build_dir / "configure/CONFIG_SITE",
            )
        substitute(
            [("^\\s*#*(\\s*INSTALL_LOCATION\\s*=).*$", f"\\1 {self.install_dir}")],
            self.build_dir / "configure/CONFIG_SITE",
        )
        self.install_dir.mkdir(exist_ok=True)

    def _install(self) -> None:
        shutil.copytree(
            self.build_dir / "iocBoot",
            self.install_dir / "iocBoot",
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("Makefile"),
        )


class IocDeployTask(EpicsDeployTask):

    def __init__(
        self,
        install_dir: Path,
        deploy_dir: PurePosixPath,
        epics_deploy_path: PurePosixPath,
        deps: List[Task] = [],
    ):
        super().__init__(
            install_dir,
            deploy_dir,
            deps,
        )
        self.epics_deploy_path = epics_deploy_path

    def _post(self, ctx: Context) -> None:
        assert ctx.device is not None
        boot_dir = self.install_dir / "iocBoot"
        for ioc_name in [path.name for path in boot_dir.iterdir()]:
            ioc_dir = boot_dir / ioc_name
            if not ioc_dir.is_dir():
                continue
            env_path = ioc_dir / "envPaths"
            if not env_path.is_file():
                continue
            with open(env_path, "r") as f:
                text = f.read()
            text = re.sub(r'(epicsEnvSet\("TOP",)[^\n]+', f'\\1"{self.deploy_dir}")', text)
            text = re.sub(r'(epicsEnvSet\("EPICS_BASE",)[^\n]+', f'\\1"{self.epics_deploy_path}")', text)
            ctx.device.store_mem(text, self.deploy_dir / "iocBoot" / ioc_name / "envPaths")


class IocRemoteRunner:

    def __init__(
        self,
        device: Device,
        deploy_path: PurePosixPath,
        epics_deploy_path: PurePosixPath,
        arch: str,
    ):
        super().__init__()
        self.device = device
        self.deploy_path = deploy_path
        self.epics_deploy_path = epics_deploy_path
        self.arch = arch
        self.proc: Optional[Connection] = None

    def __enter__(self) -> None:
        self.proc = self.device.run(
            [
                "bash",
                "-c",
                "export {}; export {}; cd {} && {} {}".format(
                    f"TOP={self.deploy_path}",
                    f"LD_LIBRARY_PATH={self.epics_deploy_path}/lib/{self.arch}:{self.deploy_path}/lib/{self.arch}",
                    f"{self.deploy_path}/iocBoot/iocPSC",
                    f"{self.deploy_path}/bin/{self.arch}/PSC",
                    "st.cmd",
                ),
            ],
            wait=False,
        )
        assert self.proc is not None
        time.sleep(1)
        logging.info("IOC started")

    def __exit__(self, *args: Any) -> None:
        logging.info("terminating IOC ...")
        assert self.proc is not None
        self.proc.close()
        logging.info("IOC terminated")


class IocRunTask(FinalTask):

    def __init__(self, owner: Ioc):
        super().__init__()
        self.owner = owner

    def run(self, ctx: Context) -> None:
        assert ctx.device is not None
        assert isinstance(self.owner.epics_base, EpicsBaseCross)
        with IocRemoteRunner(
            ctx.device,
            self.owner.deploy_path,
            self.owner.epics_base.deploy_path,
            self.owner.epics_base.arch(),
        ):
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass

    def dependencies(self) -> List[Task]:
        assert isinstance(self.owner.epics_base, EpicsBaseCross)
        return [
            self.owner.epics_base.deploy_task,
            self.owner.deploy_task,
        ]


class Ioc(Component):

    def _build_deps(self) -> List[Task]:
        deps = [self.epics_base.tasks()["build"]]
        if isinstance(self.toolchain, CrossToolchain):
            deps.append(self.toolchain.download_task)
        return deps

    def _make_build_task(self) -> IocBuildTask:
        return IocBuildTask(
            self.src_path,
            self.paths["build"],
            self.paths["install"],
            self._build_deps(),
            self.epics_base.paths["build"],
            self.toolchain,
        )

    def __init__(
        self,
        name: str,
        ioc_dir: Path,
        target_dir: Path,
        epics_base: EpicsBase,
        toolchain: Toolchain,
    ):
        super().__init__()

        self.name = name
        self.src_path = ioc_dir
        self.epics_base = epics_base
        self.toolchain = toolchain

        self.names = {
            "build": f"{self.name}_build_{self.toolchain.name}",
            "install": f"{self.name}_install_{self.toolchain.name}",
        }
        self.paths = {k: target_dir / v for k, v in self.names.items()}
        self.deploy_path = PurePosixPath("/opt/ioc")

        self.build_task = self._make_build_task()

        if isinstance(self.epics_base, EpicsBaseCross):
            self.deploy_task = IocDeployTask(
                self.paths["install"],
                self.deploy_path,
                self.epics_base.deploy_path,
                [self.build_task],
            )
            self.run_task = IocRunTask(self)

    def tasks(self) -> Dict[str, Task]:
        tasks: Dict[str, Task] = {"build": self.build_task}
        if isinstance(self.toolchain, CrossToolchain):
            tasks.update({
                "deploy": self.deploy_task,
                "run": self.run_task,
            })
        return tasks
