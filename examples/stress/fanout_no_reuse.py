import asyncio

import flyte

env = flyte.TaskEnvironment(
    name="large_fanout_no_reuse",
    resources=flyte.Resources(cpu=1, memory="1Gi"),
    image=flyte.Image.from_debian_base(),
)


@env.task
async def noop(x: int) -> int:
    return x


@env.clone_with(name="fanout_main", depends_on=[env]).task
async def no_reuse_concurrency(n: int = 50) -> int:
    coros = [noop(i) for i in range(n)]
    results = await asyncio.gather(*coros)
    return sum(results)


if __name__ == "__main__":
    flyte.init_from_config()
    runs = []
    for i in range(1):
        run = flyte.run(no_reuse_concurrency, n=20000)
        runs.append(run.url)
    print(runs)
