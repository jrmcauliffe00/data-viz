# Lazy imports

[PEP 810](https://peps.python.org/pep-0810/) added `lazy import` so a file can keep its imports at the top and still load a module only when that run touches it. The point is startup and memory on the commands that do not need every library, not a faster call once the library is used.

The notebook is `import_cost.ipynb`. It writes `import_cost.png`.

## Result from the saved run

One program imports `asyncio`, `csv`, `ssl`, `urllib.request`, `numpy`, `matplotlib`, and the California extract. Then it runs one command. On this machine, with Python 3.15.0rc2, the eager version loads the whole toolkit first, so every command costs the same. The lazy version loads only the name the command uses.

| Command | Eager time | Lazy time | Eager memory | Lazy memory |
|---|---:|---:|---:|---:|
| `--help` | 200 ms | 0 ms | 66 MB | 20 MB |
| csv dialects | 205 ms | 0.8 ms | 66 MB | 20 MB |
| read extract | 204 ms | 25 ms | 66 MB | 28 MB |
| load matplotlib | 202 ms | 156 ms | 66 MB | 53 MB |

`--help` is the case the feature is for: the imports are written down, and this invocation needs none of them. The matplotlib command is still cheaper under lazy imports, by about 46 ms and 13 MB, because the extract, urllib, and asyncio never load. The two extract reads agreed: 4,886 rows, 59.6% with matching birth- and death-state labels. That share is a checksum on this Wikidata extract, not a claim about residents.

A re-run will move the decimals. The notebook prints the claim only when the eager commands stay within 15% of each other, `--help` is slower and larger when the imports are eager, and the lazy matplotlib command is still lighter than the eager one.

## How to run

`python3` on this machine is 3.14, and 3.14 cannot parse the `lazy` keyword. The notebook has to run on 3.15 or newer, with numpy and matplotlib installed. Those two packages are part of the measurement, not only the plotting stack.

```bash
cd lazy-imports
uv venv --python 3.15.0rc2 .venv
uv pip install -r requirements.txt
```

Open the notebook from this directory with that environment and run all cells. `../data/California.csv` has to be present.

3.15.0 final shipped the same day this was written. `uv` still only indexed 3.15.0rc2, which already has [PEP 810](https://peps.python.org/pep-0810/). Any later 3.15 build works the same way.

## Why this is not a profiler

cProfile reports where CPU time went inside a process that already chose to do the work. An unused lazy import never loads the module, so a profile of that path is empty. It also cannot show the memory the process held.

Each trial is a new interpreter. The child times the import and the command. Peak resident memory is `ru_maxrss` (bytes on macOS), the high-water mark of the process. One warmup trial per condition is discarded so the page cache is warm. Nine trials are kept. The bars and marks are medians, because a single scheduling spike would pull a mean.

## What is compared

`bench/eager_app.py` and `bench/lazy_app.py` list the same imports. The only difference is the `lazy` keyword. Each process then runs one command: `--help`, csv dialects, the California extract, or matplotlib. The keyword has to be a real statement, so the two files are copies rather than one file that calls `importlib`.

## Tradeoffs

**Not two environment builds, and not cloned repositories.** Creating a virtualenv, or cloning a project and installing it, times downloads and compilation. Lazy import does not change that. It changes a later process that has the imports written at the top and may not use all of them. Numpy and matplotlib stand in for the heavy libraries in that list.

**A small stand-in, not Django or a notebook server.** The pattern is the one those programs hit: one import block, many commands, and a given invocation uses a slice of it. The numbers are this toolkit on this machine.

**In-process time, not wall time.** Starting the interpreter costs about the same on every trial. The bars leave that constant out. Memory is `ru_maxrss`, the high-water mark of the process, not a trace of individual allocations.

**Explicit `lazy` only.** `-X lazy_imports=all` makes every import lazy and is a different experiment. `__lazy_modules__` is the form that stays valid on 3.14, where it is ignored.

**Failures move.** A missing module is raised at startup for the eager import and at first use for the lazy import.

**The California label match is coarser than the state-deaths rates.** A row counts only when both labels are present and equal. Do not compare the 59.6% figure with the maps in `state-deaths/`.
