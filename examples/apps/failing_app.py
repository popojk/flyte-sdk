"""A minimal app whose process runs a simple Python program that raises.

Useful for exercising how a crashing app surfaces (logs, failure status,
crash-loop behavior) rather than serving real traffic. The `command` overrides
the container entrypoint and runs an inline Python program that prints a line
and then throws an exception, so the process exits non-zero right away.
"""

import flyte
import flyte.app

image = flyte.Image.from_debian_base(python_version=(3, 12))

# Inline Python program: log a message, then raise.
program = 'print("about to fail", flush=True); raise RuntimeError("boom: intentional failure")'

app_env = flyte.app.AppEnvironment(
    name="failing-app",
    image=image,
    # `command` overrides the entrypoint entirely; this app does not serve a port,
    # it just runs the program and exits with an exception.
    command=["python", "-c", program],
    resources=flyte.Resources(cpu="1", memory="512Mi"),
)


if __name__ == "__main__":
    flyte.init_from_config()
    d = flyte.deploy(app_env)
    print(d[0])
