from __future__ import annotations
from typing import Dict, List, Tuple, Optional

import argparse
from dataclasses import dataclass
from pathlib import Path
from colorama import init as colorama_init, Style

from vortex.tasks.base import Context, Task, Component
from vortex.utils.log import LogLevel
from vortex.tasks.base import Runner
from vortex.dst.base import Dst
from vortex.dst.local import Fs
from vortex.dst.ssh import SshDevice

import logging


def _make_task_tree(tasks: List[str]) -> List[str]:
    output: List[str] = []
    groups: Dict[str, List[str]] = {}
    for task in tasks:
        spl = task.split(".", 1)
        if len(spl) == 1:
            key = spl[0]
            assert key not in groups
            groups[key] = []
        elif len(spl) == 2:
            key, value = spl
            if key in groups:
                values = groups[key]
                assert values is not []
                values.append(value)
            else:
                groups[key] = [value]

    def sort_key(x: Tuple[str, List[str]]) -> Tuple[int, Tuple[str, ...]]:
        p = (x[0], *x[1])
        return (len(p), p)

    for key, values in sorted(groups.items(), key=sort_key):
        if len(values) == 0:
            output.append(f"{Style.BRIGHT}{key}{Style.NORMAL}")
        else:
            subtree = _make_task_tree(values)
            output.append(f"{Style.BRIGHT}{key}.{subtree[0]}{Style.NORMAL}")
            output.extend([f"{Style.DIM}{key}.{Style.NORMAL}{value}" for value in subtree[1:]])

    return output


def _available_tasks_text(comp: Component) -> str:
    return "\n".join(
        [
            "Available tasks:",
            *[(" " * 2) + task for task in _make_task_tree(list(comp.tasks().keys()))],
        ]
    )


def add_parser_args(parser: argparse.ArgumentParser, comp: Component) -> None:
    colorama_init()

    parser.formatter_class = argparse.RawTextHelpFormatter

    parser.add_argument(
        "task",
        type=str,
        metavar="<task>",
        help="\n".join(
            [
                "Task you want to run.",
                _available_tasks_text(comp),
            ]
        ),
    )
    parser.add_argument(
        *["-t", "--target-dir"],
        type=str,
        default=None,
        help="Path to directory to place build artifacts.",
    )
    parser.add_argument(
        "--no-deps",
        action="store_true",
        help="Run only specified task without dependencies.",
    )
    parser.add_argument(
        *["-d", "--dst"],
        type=str,
        metavar="<path>",
        default=None,
        help="Location in local file system to deploy files.",
    )
    parser.add_argument(
        "--device",
        type=str,
        metavar="<address>[:port]",
        default=None,
        help="\n".join(
            [
                "Device to deploy and run tests.",
                "Requirements:",
                "+ Debian Linux running on the device (another distros are not tested).",
                "+ SSH server running on the device on the specified port (or 22 if the port is not specified).",
                "+ Possibility to log in to the device via SSH by user 'root' without password (e.g. using public key).",
            ]
        ),
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Update external dependencies (toolchains, locked dependencies, etc.).",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Store cache locally (for rustup, cargo, etc.).",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        metavar="<N>",
        default=None,
        help="Number of parallel process to build. By default automatically determined value is used.",
    )
    parser.add_argument(
        "--log-level",
        type=int,
        choices=[int(v) for v in LogLevel],
        default=None,
        help="\n".join(
            [
                "Set log level.",
                "  0 - Trace",
                "  1 - Debug",
                "  2 - Info",
                "  3 - Warning (since this level task output is captured and displayed only in case of error)",
                "  4 - Error",
                "Default value is 3 (warning).",
            ]
        ),
    )


class ReadRunParamsError(RuntimeError):
    pass


@dataclass
class RunParams:
    task: Task
    context: Context
    no_deps: bool


def _find_task_by_args(comp: Component, args: argparse.Namespace) -> Task:
    task_name = args.task
    try:
        task = comp.tasks()[task_name]
    except KeyError:
        raise ReadRunParamsError("\n".join([f"Unknown task '{task_name}'.", _available_tasks_text(comp)]))

    return task


def _make_context_from_args(args: argparse.Namespace, target_dir: Path) -> Context:
    if args.target_dir is not None:
        target_dir = Path(args.target_dir).resolve()

    assert args.dst is None or args.device is None, "Cannot set both --dst and --device"
    dst: Optional[Dst]
    if args.dst:
        dst = Fs(Path(args.dst))
    elif args.device:
        dst = SshDevice(args.dst)
    else:
        dst = None

    log_level = LogLevel(args.log_level) if args.log_level is not None else LogLevel.WARNING

    return Context(
        target_dir,
        dst=dst,
        log_level=log_level,
        update=args.update,
        local=args.local,
        jobs=args.jobs,
    )


def read_run_params(args: argparse.Namespace, comp: Component, target_dir: Path) -> RunParams:
    try:
        task = _find_task_by_args(comp, args)
    except ReadRunParamsError as e:
        print(e)
        exit(1)

    context = _make_context_from_args(args, target_dir)

    return RunParams(task, context, no_deps=args.no_deps)


def setup_logging(params: RunParams, modules: List[str]) -> None:
    logging.basicConfig(format="[%(levelname)s] %(message)s", level=logging.WARNING, force=True)
    if not params.context.capture:
        level = params.context.log_level.level()
        for mod in modules:
            logging.getLogger(mod).setLevel(level)


def run_with_params(params: RunParams) -> None:
    Runner(params.task).run(params.context, no_deps=params.no_deps)
