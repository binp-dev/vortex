from __future__ import annotations
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar, Generic

from pathlib import Path
from dataclasses import dataclass

from ferrite.utils.path import TargetPath
from ferrite.utils.log import LogLevel
from ferrite.remote.base import Device


@dataclass
class Context:
    target_path: Path
    device: Optional[Device] = None
    log_level: LogLevel = LogLevel.WARNING
    update: bool = False
    local: bool = False
    hide_artifacts: bool = False
    jobs: Optional[int] = None

    @property
    def capture(self) -> bool:
        return self.log_level > LogLevel.INFO


@dataclass
class Artifact:
    path: TargetPath
    cached: bool = False


# Task must be hashable, so any derived dataclass should use eq=False.
@dataclass(eq=False)
class Task:

    def __post_init__(self) -> None:
        self._name: Optional[str] = None

    def name(self) -> str:
        cls = self.__class__
        return self._name or f"<{cls.__module__}.{cls.__qualname__}>({hash(self):x})"

    def run(self, ctx: Context) -> None:
        raise NotImplementedError()

    def dependencies(self) -> List[Task]:
        return []

    def graph(self) -> Dict[Task, Set[Task]]:
        graph: Dict[Task, Set[Task]] = {}

        def fill_graph(task: Task) -> None:
            if task not in graph:
                deps = task.dependencies()
                graph[task] = set(deps)
                for dep in deps:
                    fill_graph(dep)
            else:
                # Check that task dependencies are the same.
                assert len(graph[task].symmetric_difference(set(task.dependencies()))) == 0

        fill_graph(self)
        return graph

    def run_with_dependencies(self, ctx: Context) -> None:
        deps = self.dependencies()
        assert isinstance(deps, list)

        for dep in deps:
            dep.run_with_dependencies(ctx)

        self.run(ctx)

    def artifacts(self) -> List[Artifact]:
        return []


class EmptyTask(Task):

    def run(self, ctx: Context) -> None:
        pass


class CallTask(Task):

    def __init__(self, func: Callable[[], None]) -> None:
        super().__init__()
        self.func = func

    def run(self, ctx: Context) -> None:
        self.func()


class TaskList(Task):

    def __init__(self, tasks: List[Task]) -> None:
        super().__init__()
        self.tasks = tasks

    def run(self, ctx: Context) -> None:
        pass

    def dependencies(self) -> List[Task]:
        return self.tasks

    def artifacts(self) -> List[Artifact]:
        return [art for task in self.tasks for art in task.artifacts()]


class TaskWrapper(Task):

    def __init__(self, inner: Optional[Task] = None, deps: List[Task] = []) -> None:
        super().__init__()
        self.inner = inner
        self.deps = deps

    def name(self) -> str:
        if self.inner is not None:
            return self.inner.name()
        else:
            return super().name()

    def run(self, ctx: Context) -> None:
        if self.inner is not None:
            self.inner.run(ctx)

    def dependencies(self) -> List[Task]:
        inner_deps = []
        if self.inner is not None:
            inner_deps = self.inner.dependencies()
        return inner_deps + self.deps

    def artifacts(self) -> List[Artifact]:
        return [
            *(self.inner.artifacts() if self.inner is not None else []),
            *[art for task in self.deps for art in task.artifacts()]
        ]


class Component:

    def tasks(self) -> Dict[str, Task]:
        tasks: Dict[str, Task] = {}
        for key, var in vars(self).items():
            if isinstance(var, Task):
                # Try to get task name
                postfix = "_task"
                if key.endswith(postfix):
                    key = key[:-len(postfix)]
                else:
                    raise RuntimeWarning(f"Cannot determine task name for {type(self).__qualname__}.{key}")
                if key.startswith("_"):
                    key = key[1:]

                assert (key not in tasks)
                tasks[key] = var

        return tasks

    def _update_names(self) -> None:
        for task_name, task in self.tasks().items():
            if hasattr(task, "_name") and task._name is not None:
                raise RuntimeError(f"Task has multiple names: '{task._name}' and '{task_name}'")
            task._name = f"{task_name}"


@dataclass
class DictComponent(Component):
    task_dict: Dict[str, Task]

    def tasks(self) -> Dict[str, Task]:
        return self.task_dict


class ComponentGroup(Component):

    def components(self) -> Dict[str, Component]:
        raise NotImplementedError()

    def tasks(self) -> Dict[str, Task]:
        tasks: Dict[str, Task] = {}
        for comp_name, comp in self.components().items():
            for task_name, task in comp.tasks().items():
                key = f"{comp_name}.{task_name}"
                assert key not in tasks
                tasks[key] = task
        return tasks


O = TypeVar("O", bound=Component, covariant=True)


@dataclass(eq=False)
class OwnedTask(Task, Generic[O]):
    owner: O
