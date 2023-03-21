from __future__ import annotations
from typing import List, Optional

import shutil
from pathlib import Path
from dataclasses import dataclass

from vortex.utils.path import TargetPath
from vortex.utils.run import run, RunError
from vortex.tasks.base import task, Component, Context

import logging

logger = logging.getLogger(__name__)


def clone(path: Path, remote: str, branch: Optional[str] = None, clean: bool = False, quiet: bool = False) -> bool:
    if path.exists():
        # FIXME: Pull if update available
        logger.info(f"Repo '{remote}' is cloned already")
        return False
    try:
        path.parent.mkdir(exist_ok=True, parents=True)
        run(
            ["git", "clone", remote, path.name],
            cwd=path.parent,
            env={"GIT_TERMINAL_PROMPT": "0"},
            quiet=quiet,
        )
        if branch:
            run(["git", "checkout", branch], cwd=path, quiet=quiet)
        run(["git", "submodule", "update", "--init", "--recursive"], cwd=path, quiet=quiet)
    except RunError:
        if path.exists():
            shutil.rmtree(path)
        raise
    if clean:
        shutil.rmtree(path / ".git")
    return True


@dataclass
class RepoSource:
    remote: str
    branch: Optional[str]

    def __repr__(self) -> str:
        return f"'{self.remote}'" + f", branch '{self.branch}'" if self.branch is not None else ""


@dataclass
class RepoList(Component):
    path: TargetPath
    sources: List[RepoSource]

    @task
    def clone(self, ctx: Context) -> None:
        last_error = None
        for source in self.sources:
            try:
                clone(ctx.target_path / self.path, source.remote, source.branch, clean=True, quiet=ctx.capture)
                return
            except RunError as e:
                last_error = e
                logger.warning(f"Failed to clone {source}: {e}")
                continue
        if last_error is not None:
            raise last_error


class Repo(RepoList):
    def __init__(self, dst_dir: TargetPath, remote: str, branch: Optional[str] = None):
        super().__init__(dst_dir, [RepoSource(remote, branch)])
