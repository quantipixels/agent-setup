# Setup standard

The phase brief defines the repository layout. Use POSIX sh entry scripts and Python 3.11+ standard library for file work. No third-party Python packages.

Tools use `latest`, as the brief requires. CI actions use immutable commit hashes. `last-good.lock` is rollback evidence, never an install source.

Unlike ordinary product scripts, these steps install tools because setup is the product. Mise automatic install is off; the setup step owns explicit installs. A dry run must not apply files or install dependencies. Mise itself can create cache metadata before a task; track that separately from step writes.

Never store credentials, history, sessions, plugin caches or MCP OAuth data. Keep personal instructions in `examples/`. Preserve host-added JSON and TOML keys. Stop on malformed live files and file conflicts; never discard them to make doctor pass.
