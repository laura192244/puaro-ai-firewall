# Third-Party Notices

## AISecurity / sentinel-core

Puaro's Firewall step (`app/firewall.py`) optionally uses the public `sentinel-core`
Python package, from:

- Repository: https://github.com/DmitrL-dev/AISecurity
- Pinned commit: `dd432e0baed808f539780bb21d94737617b40429`
- Subdirectory: `sentinel-core`
- License: Apache License 2.0
- Copyright 2024-2025 Dmitry Labintsev

We use it exclusively through its published Python binding,
`EngineRegistry().analyze_patterns(text)`, the same pinned entry point used by that
project's own Guard Lab tool. We did not copy, vendor, or modify any of its source
code — Puaro depends on it as an ordinary installed package, and falls back to a
small original regex rule set (`app/firewall.py`) if the native package is not
installed for the current platform.

Distillation detection, decoy generation, Model DNA (HMAC trap phrases), the clone
stand-in, and collective immunity are Puaro's own original work and are **not**
part of the AISecurity repository.

Per that project's own documentation, its detection-accuracy figures are historical
and have not been independently revalidated, and its demo/test corpus is small and
synthetic. Puaro does not quote or rely on any of those figures anywhere in this
repository, its README, its UI, or its `make eval` output.

A copy of the Apache License 2.0 is available at:
http://www.apache.org/licenses/LICENSE-2.0

## Python dependencies

The following open-source packages are used as ordinary pip dependencies
(see `requirements.txt`); each retains its own license, unmodified:

| Package | License |
|---|---|
| fastapi | MIT |
| uvicorn | BSD-3-Clause |
| pydantic | MIT |
| httpx | BSD-3-Clause |
| datasketch | MIT |
| pytest | MIT |

No source code from any of the above is included in this repository; they are
installed via `pip install -r requirements.txt`.
