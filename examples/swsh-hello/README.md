# swsh-hello

The smallest useful sw plugin. It adds `sw hello` with two commands:

```bash
sw hello world --name Ada          # hello, Ada
sw hello world --json              # {"greeting": "hello, world"}
sw hello project                   # hello, <project> on <space>   (uses your profile)
sw hello project --raw             # the whoami response, untouched
```

Install it into the environment sw runs from:

```bash
# from a swsh checkout with its venv
.venv/bin/pip install -e examples/swsh-hello

# or alongside a uv-installed sw
uv tool install swsh --with ./examples/swsh-hello
```

`sw plugins list` should then show it as `loaded`.

To write your own, copy this directory, rename the package, and change the
entry-point name in `pyproject.toml`: that name is the command. Import only from
`swsh.plugin`; the rest of `swsh` is not a stable API.
