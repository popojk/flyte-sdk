"""Minimal HITL condition, for exercising the pause/signal round trip on the devbox.

Run it, note the run name it prints, then resolve the condition from another shell:

    flyte get condition <run-name>
    flyte signal condition <run-name> <action-name> yes

The task blocks in `cond.wait()` until then. A 30 minute timeout keeps a forgotten
run from pausing forever.
"""

import asyncio
import logging
from datetime import timedelta

import flyte

image = (
    flyte.Image.from_debian_base()
    .with_pip_packages("cryptography==44.0.3", "pyOpenSSL==25.1.0")
)

env = flyte.TaskEnvironment(
    name="hitl_demo",
    resources=flyte.Resources(cpu=1, memory="1Gi"),
    image=image,
)


@env.task
async def ask_human(item: str) -> str:
    cond = await flyte.new_condition.aio(
        "approve-item",
        prompt=f"Approve {item}? (yes/no)",
        data_type=str,
        description="Demo condition for exercising the signal path on the devbox.",
        timeout=timedelta(minutes=30),
    )
    print(f"waiting for a signal on '{item}' — action: {flyte.ctx().action}")
    answer = await cond.wait.aio()
    print(f"got: {answer!r}")
    return answer


@env.task(entrypoint=True)
async def main(item: str = "widget-42") -> str:
    answer = await ask_human(item=item)
    return f"{item} -> {answer}"


if __name__ == "__main__":
    flyte.init_from_config()
    run = flyte.with_runcontext(log_level=logging.INFO).run(main, item="widget-42")
    print(f"run name: {run.name}")
    print(f"resolve with: flyte signal condition {run.name} <action-name> yes")
