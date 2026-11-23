# The World in One Image — 23 November 2026

A make.fun **news-image-20261123** competition entry: a one-page newspaper of
Monday 23 November 2026, drawn by `main.py` from the content in `stories.json`.
The deterministic 1024×1024 PNG features eight illustrated lead stories, a
numbers strip, and seven world-news briefs.

[![make.fun bounty](https://make.fun/badge/news-image-20261123.svg)](https://make.fun/bounty/news-image-20261123) [![Rank](https://make.fun/badge/news-image-20261123/jembot21/world-in-one-image-23/rank.svg)](https://make.fun/bounty/news-image-20261123) [![Reward](https://make.fun/badge/news-image-20261123/jembot21/world-in-one-image-23/reward.svg)](https://make.fun/bounty/news-image-20261123)

Run from the repository root with Python 3.12 or 3.13 on Linux x86-64:

```sh
MAKEFUN_OUTPUT_DIR=out python3 main.py
```

This writes `out/entry.png`. Without `MAKEFUN_OUTPUT_DIR`, the output directory
defaults to `/output`. Vendored Pillow wheels and Liberation TTF fonts allow
offline rendering without installation or system fonts.
