from __future__ import annotations
from typing import Sequence, Mapping, List, Dict, Optional, Callable

import os
import sys
from subprocess import Popen, PIPE, STDOUT, CalledProcessError
from pathlib import Path
from enum import Enum
from time import time, sleep

RunError = CalledProcessError

import logging

logger = logging.getLogger(__name__)


class RunMode(Enum):
    NORMAL = 0
    DEBUGGER = 1
    PROFILER = 2


def run(
    args: Sequence[str | Path],
    cwd: Optional[Path] = None,
    env: Mapping[str, str | Path] = {},
    *,
    capture: bool = False,
    quiet: bool = False,
    timeout: Optional[float] = None,
    mode: RunMode = RunMode.NORMAL,
    alive: Callable[[], bool] = lambda: True,
) -> Optional[str]:
    x_args = [str(a) for a in args]
    if mode == RunMode.DEBUGGER:
        x_args = ["gdb", "-batch", "-ex", "run", "-ex", "bt", "-args"] + x_args
    elif mode == RunMode.PROFILER:
        x_args = ["perf", "record"] + x_args
    else:
        assert mode == RunMode.NORMAL

    x_env = {**dict(os.environ), **{k: str(v) for k, v in env.items()}}

    stdout = None
    if capture or quiet:
        stdout = PIPE
    stderr = None
    if quiet:
        stderr = STDOUT

    logger.debug(f"Starting process: {x_args}, cwd={cwd}, env={env}")
    done = False
    proc = Popen(
        x_args,
        cwd=cwd,
        env=x_env,
        stdout=stdout,
        stderr=stderr,
    )

    try:
        start = time()
        while alive():
            sleep(0.1)
            ret = proc.poll()
            if ret is not None:
                if ret != 0:
                    raise CalledProcessError(ret, x_args)
                done = True
                break
            if timeout is not None and timeout < time() - start:
                raise TimeoutError
    except:
        if capture or quiet:
            assert proc.stdout is not None
            sys.stdout.buffer.write(proc.stdout.read())
            assert proc.stderr is not None
            sys.stderr.buffer.write(proc.stderr.read())
        raise

    if not done:
        proc.terminate()
        logger.debug(f"Process terminated: {x_args}")

    if capture:
        assert proc.stdout is not None
        return proc.stdout.read().decode("utf-8")
    else:
        return None


def capture(
    args: List[str | Path],
    cwd: Optional[Path] = None,
    env: Mapping[str, str] = {},
) -> str:
    result = run(args, cwd, env=env, capture=True)
    assert result is not None
    return result.strip()
