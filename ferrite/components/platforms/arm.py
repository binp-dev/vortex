from __future__ import annotations

from pathlib import Path

from ferrite.components.compiler import Target, GccCross
from ferrite.components.rust import RustcCross
from ferrite.components.platforms.base import AppPlatform


class ArmAppToolchain(GccCross):

    def __init__(self, name: str, target_dir: Path) -> None:
        super().__init__(
            name=name,
            target=Target("arm", "none", "linux", "gnueabihf"),
            target_dir=target_dir,
            dir_name="gcc-arm-10.2-2020.11-x86_64-arm-none-linux-gnueabihf",
            archive="gcc-arm-10.2-2020.11-x86_64-arm-none-linux-gnueabihf.tar.xz",
            urls=[
                "https://gitlab.inp.nsk.su/psc/storage/-/raw/master/toolchains/gcc-arm-10.2-2020.11-x86_64-arm-none-linux-gnueabihf.tar.xz",
                "https://developer.arm.com/-/media/Files/downloads/gnu-a/10.2-2020.11/binrel/gcc-arm-10.2-2020.11-x86_64-arm-none-linux-gnueabihf.tar.xz",
            ],
        )


class ArmAppRustc(RustcCross):

    def __init__(self, postfix: str, target_dir: Path, gcc: GccCross):
        super().__init__(postfix, Target.from_str("armv7-unknown-linux-gnueabihf"), target_dir, gcc)


class ArmAppPlatform(AppPlatform):

    def __init__(self, name: str, target_dir: Path) -> None:
        gcc = ArmAppToolchain(name, target_dir)
        super().__init__(gcc, ArmAppRustc(name, target_dir, gcc))


class Aarch64AppToolchain(GccCross):

    def __init__(self, name: str, target_dir: Path) -> None:
        super().__init__(
            name=name,
            target=Target("aarch64", "none", "linux", "gnu"),
            target_dir=target_dir,
            dir_name="gcc-arm-10.2-2020.11-x86_64-aarch64-none-linux-gnu",
            archive="gcc-arm-10.2-2020.11-x86_64-aarch64-none-linux-gnu.tar.xz",
            urls=[
                "https://gitlab.inp.nsk.su/psc/storage/-/raw/master/toolchains/gcc-arm-10.2-2020.11-x86_64-aarch64-none-linux-gnu.tar.xz",
                "https://developer.arm.com/-/media/Files/downloads/gnu-a/10.2-2020.11/binrel/gcc-arm-10.2-2020.11-x86_64-aarch64-none-linux-gnu.tar.xz",
            ],
        )


class Aarch64AppRustc(RustcCross):

    def __init__(self, postfix: str, target_dir: Path, gcc: GccCross):
        super().__init__(postfix, Target.from_str("aarch64-unknown-linux-gnu"), target_dir, gcc)


class Aarch64AppPlatform(AppPlatform):

    def __init__(self, name: str, target_dir: Path) -> None:
        gcc = Aarch64AppToolchain(name, target_dir)
        super().__init__(gcc, Aarch64AppRustc(name, target_dir, gcc))