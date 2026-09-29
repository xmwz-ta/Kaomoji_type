# Third-party data notices

The kaomojikan data in `data/upstream/kaomojikan/kaomoji.json`, its converted subset
in `data/web_collections.json`, and the derived entries in `data/kaomoji.json` and
`rime/kaomoji_data.lua` originate from
[kaomojikan/kaomoji-data](https://github.com/kaomojikan/kaomoji-data), revision
`60c92ea4e85279ad42ff525e9a40464ebeb1003e`.

Copyright (c) 2026 kaomojikan. Licensed under the MIT License.
The complete notice is retained in [data/upstream/kaomojikan/LICENSE](data/upstream/kaomojikan/LICENSE)
and embedded in the generated Lua data installed by this project.

Changes: single-line filtering, normalized deduplication, mapping Japanese labels
to project emotion/topic IDs, and addition of Chinese trigger phrases. Original
source IDs and a pinned snapshot are retained for provenance.
