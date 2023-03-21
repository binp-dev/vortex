from __future__ import annotations
from typing import Any, Optional

from vortex.utils.run import run as basic_run
from vortex.tasks.base import Context

import logging

logger = logging.getLogger(__name__)


def run(ctx: Context, *args: Any, **kws: Any) -> Optional[str]:
    assert "alive" not in kws
    return basic_run(*args, alive=lambda: ctx._running, **kws)
