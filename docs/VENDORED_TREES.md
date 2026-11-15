# Vendored Trees

## `tools/llama.cpp`

A clone of `https://github.com/ggml-org/llama.cpp`, pinned to the commit recorded in
`patches/`. It is excluded from this repository by `.gitignore` (`tools/llama.cpp/`),
so **local edits inside it are invisible to `git status` at the repo root.**

### The rule

Never leave the vendored tree dirty. Export every change as a patch:

```powershell
git -C tools/llama.cpp diff > patches/<name>.patch
```

Then commit the patch. Restore on a fresh machine:

```powershell
git clone https://github.com/ggml-org/llama.cpp tools/llama.cpp
git -C tools/llama.cpp checkout <pinned-sha>
git -C tools/llama.cpp apply ../patches/<name>.patch
```

### Upstream rules are not project rules

`tools/llama.cpp/AGENTS.md` and `tools/llama.cpp/CLAUDE.md` are **ggml-org contributor
policy**. They govern pull requests to llama.cpp — PR etiquette, C++ complexity limits,
maintainer expectations. They do **not** govern this project.

The rules that apply here are in the repo-root `AGENTS.md`. An agent that reads the
vendored file and starts following upstream PR policy for Strata work is misreading its
scope.

### Current patches

| Patch | Purpose |
|---|---|
| `0001-qwen25-coder-0.5b-pruned-hash.patch` | Registers the Project Strata pruned Qwen 2.5 Coder 0.5B 32k model hash so `convert_hf_to_gguf.py` maps it to the `qwen2` architecture. |

### Reimage note

The vendored tree is re-clonable and is **not** backed up as history. Only `patches/`
matters. If `tools/llama.cpp` is missing after a reimage, the patch is the source of truth.
