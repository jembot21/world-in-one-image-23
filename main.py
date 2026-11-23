"""Render the supplied newspaper to MAKEFUN_OUTPUT_DIR/entry.png.

Python 3.12 or 3.13. Offline assets belong beside this file:
vendor/pillow-*-cp312/cp313-*-*linux*x86_64.whl and assets/fonts/*.ttf.
Only the wheel bootstrap uses temporary files; they are removed on exit.
No downloads, system fonts, cached bytecode, or auxiliary output files.
"""

from __future__ import annotations

import atexit
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from functools import lru_cache


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent


def load_pillow():
    """Import installed Pillow, or unpack a compatible local wheel offline."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        return Image, ImageDraw, ImageFont
    except ImportError:
        runtime_tag = f"cp{sys.version_info.major}{sys.version_info.minor}"
        wheels = sorted(
            (wheel for wheel in (ROOT / "vendor").glob("*.whl")
             if wheel.is_file()
             and wheel.name.lower().startswith("pillow-")
             and len(wheel.name.split("-")) >= 5
             and "linux" in wheel.name.split("-")[-1]
             and "x86_64" in wheel.name.split("-")[-1]),
            key=lambda wheel: (
                runtime_tag not in wheel.name.split("-")[-3].split("."),
                wheel.name,
            ),
        )
        if not wheels:
            raise RuntimeError(
                f"Pillow is unavailable. Place a {runtime_tag} Linux x86-64 "
                "Pillow wheel in vendor/ beside main.py."
            ) from None

        failures = []
        for wheel in wheels:
            # Prefer the exact cp tag, then try remaining local wheels in a
            # stable order. A different tag can work for an ABI-stable wheel.
            # Never assume that cp312 and cp313 native extensions interchange.
            for name in list(sys.modules):
                if name == "PIL" or name.startswith("PIL."):
                    del sys.modules[name]
            extracted = tempfile.TemporaryDirectory(prefix="makefun-pillow-")
            destination = Path(extracted.name)
            try:
                with zipfile.ZipFile(wheel) as archive:
                    for member in archive.infolist():
                        if not (destination / member.filename).resolve().is_relative_to(
                            destination.resolve()
                        ):
                            raise RuntimeError("Unsafe path in the local Pillow wheel.")
                    archive.extractall(destination)
                sys.path.insert(0, str(destination))
                from PIL import Image, ImageDraw, ImageFont
            except (ImportError, OSError, zipfile.BadZipFile) as error:
                failures.append(f"{wheel.name}: {error}")
                if str(destination) in sys.path:
                    sys.path.remove(str(destination))
                extracted.cleanup()
                continue
            atexit.register(extracted.cleanup)
            return Image, ImageDraw, ImageFont

        raise RuntimeError(
            f"No vendored Pillow wheel could load on {runtime_tag}. "
            f"Supply a compatible Linux x86-64 wheel in vendor/. "
            f"Attempted: {'; '.join(failures)}"
        ) from None


Image, ImageDraw, ImageFont = load_pillow()

SIZE = 1024
SCALE = 3  # Render at 3x for smooth print-like type and illustrations.
PAPER = "#f6f0e1"
INK = "#191815"
RED = "#ab2525"
WHITE = "#ffffff"
MARGIN = 32
GRID_TOP = 198
ROW_HEIGHT = 292
COLUMN_WIDTH = 240

FONT_CANDIDATES = {
    "headline": (
        "serif-bold.ttf", "LiberationSerif-Bold.ttf",
        "DejaVuSerifCondensed-Bold.ttf", "DejaVuSerif-Bold.ttf",
        "NotoSerif-Bold.ttf", "LibreBaskerville-Bold.ttf",
        "SourceSerif4-Bold.ttf", "SourceSerifPro-Bold.ttf",
        "headlines.ttf",
    ),
    "body": (
        "sans.ttf", "LiberationSans-Regular.ttf", "DejaVuSans.ttf",
        "NotoSans-Regular.ttf", "SourceSans3-Regular.ttf",
        "SourceSansPro-Regular.ttf", "Roboto-Regular.ttf", "body.ttf",
    ),
    "label": (
        "sans-bold.ttf", "LiberationSans-Bold.ttf", "DejaVuSans-Bold.ttf",
        "NotoSans-Bold.ttf", "SourceSans3-Bold.ttf",
        "SourceSansPro-Bold.ttf", "Roboto-Bold.ttf", "labels.ttf",
    ),
}


def find_fonts():
    paths = {}
    directory = ROOT / "assets" / "fonts"
    for role, candidates in FONT_CANDIDATES.items():
        paths[role] = next(
            (directory / name for name in candidates
             if (directory / name).is_file()),
            None,
        )
        if paths[role] is None:
            raise RuntimeError(
                f"Missing {role} TTF in assets/fonts/. "
                f"Supply one of: {', '.join(candidates)}"
            )
    return paths


@dataclass
class TextBlock:
    font: object
    lines: list[str]
    bounds: list[tuple[int, int, int, int]]
    gap: int
    height: int


class Newspaper:
    def __init__(self, font_paths):
        self.image = Image.new("RGB", (SIZE * SCALE, SIZE * SCALE), PAPER)
        self.draw = ImageDraw.Draw(self.image)
        self.font_paths = font_paths

    @lru_cache(maxsize=256)
    def font(self, role, size):
        return ImageFont.truetype(
            str(self.font_paths[role]), round(size * SCALE),
            layout_engine=ImageFont.Layout.BASIC,
        )

    @staticmethod
    def points(points):
        return [(round(x * SCALE), round(y * SCALE)) for x, y in points]

    def line(self, points, fill=INK, width=1):
        self.draw.line(self.points(points), fill=fill,
                       width=max(1, round(width * SCALE)), joint="curve")

    def rectangle(self, box, fill=None, outline=None, width=1):
        self.draw.rectangle(
            [round(value * SCALE) for value in box], fill=fill, outline=outline,
            width=max(1, round(width * SCALE)),
        )

    def ellipse(self, box, fill=None, outline=None, width=1):
        self.draw.ellipse(
            [round(value * SCALE) for value in box], fill=fill, outline=outline,
            width=max(1, round(width * SCALE)),
        )

    def polygon(self, points, fill=INK):
        self.draw.polygon(self.points(points), fill=fill)

    def arc(self, box, start, end, fill=INK, width=2):
        self.draw.arc([round(value * SCALE) for value in box], start, end,
                      fill=fill, width=max(1, round(width * SCALE)))

    def bounds(self, text, font):
        return self.draw.textbbox((0, 0), text, font=font)

    def width(self, text, font):
        left, _, right, _ = self.bounds(text, font)
        return right - left

    def wrap(self, text, font, width):
        """Wrap at words, preserving the full wording without truncation."""
        lines = []
        current = ""
        for word in text.split():
            if self.width(word, font) > width:
                return None
            candidate = f"{current} {word}" if current else word
            if current and self.width(candidate, font) > width:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
        return lines

    def fit(self, text, role, box, maximum, max_lines=1, gap=3):
        x0, y0, x1, y1 = box
        width, height = round((x1 - x0) * SCALE), round((y1 - y0) * SCALE)
        for size in range(maximum, 0, -1):
            font = self.font(role, size)
            lines = self.wrap(text, font, width) if max_lines > 1 else [text]
            if not lines or len(lines) > max_lines:
                continue
            bounds = [self.bounds(line, font) for line in lines]
            total = sum(bottom - top for _, top, _, bottom in bounds)
            total += round(gap * SCALE) * (len(lines) - 1)
            if total <= height and all(
                right - left <= width for left, _, right, _ in bounds
            ):
                return TextBlock(font, lines, bounds, round(gap * SCALE), total)
        raise ValueError(f"Text cannot fit its assigned box: {text!r}")

    def text(self, text, role, box, maximum, max_lines=1, fill=INK,
             align="left", valign="top", gap=3):
        block = self.fit(text, role, box, maximum, max_lines, gap)
        x0, y0, x1, y1 = [round(value * SCALE) for value in box]
        y = y0 + ((y1 - y0 - block.height) // 2 if valign == "center" else 0)
        for line, (left, top, right, bottom) in zip(block.lines, block.bounds):
            x = x0 + ((x1 - x0 - (right - left)) // 2 if align == "center" else 0)
            self.draw.text((x - left, y - top), line, font=block.font, fill=fill)
            y += bottom - top + block.gap

    def tracked_text(self, text, box, maximum=30, tracking=3):
        """Fit and center the date, measuring every letter and its bearings."""
        x0, y0, x1, y1 = [round(value * SCALE) for value in box]
        for size in range(maximum, 0, -1):
            font = self.font("label", size)
            bounds = [self.bounds(character, font) for character in text]
            advances = [self.draw.textlength(character, font=font)
                        for character in text]
            step = tracking * SCALE
            offsets = [0.0]
            for advance in advances[:-1]:
                offsets.append(offsets[-1] + advance + step)
            left = min(offset + bound[0] for offset, bound in zip(offsets, bounds))
            right = max(offset + bound[2] for offset, bound in zip(offsets, bounds))
            top = min(bound[1] for bound in bounds)
            bottom = max(bound[3] for bound in bounds)
            if right - left <= x1 - x0 and bottom - top <= y1 - y0:
                x = x0 + (x1 - x0 - (right - left)) / 2 - left
                y = y0 + (y1 - y0 - (bottom - top)) / 2 - top
                for character, offset in zip(text, offsets):
                    self.draw.text((round(x + offset), round(y)), character,
                                   font=font, fill=INK)
                return
        raise ValueError("Date does not fit.")

    def masthead(self, data):
        self.line([(MARGIN, 26), (SIZE - MARGIN, 26)])
        self.text(data["masthead_title"], "headline", (32, 39, 992, 119),
                  73, align="center", valign="center")
        self.line([(MARGIN, 132), (SIZE - MARGIN, 132)], width=4)
        self.tracked_text(data["date_line"], (94, 145, 930, 183), maximum=32)
        self.rectangle((60, 159, 69, 168), fill=RED)
        self.rectangle((955, 159, 964, 168), fill=RED)
        self.line([(MARGIN, 194), (SIZE - MARGIN, 194)])

    def stories(self, data):
        for column in range(1, 4):
            x = MARGIN + COLUMN_WIDTH * column
            self.line([(x, GRID_TOP + 3), (x, GRID_TOP + ROW_HEIGHT * 2 - 4)])
        self.line([(MARGIN, GRID_TOP + ROW_HEIGHT),
                   (SIZE - MARGIN, GRID_TOP + ROW_HEIGHT)])
        for index, story in enumerate(data["lead_stories"]):
            column, row = index % 4, index // 4
            x, y = MARGIN + column * COLUMN_WIDTH, GRID_TOP + row * ROW_HEIGHT
            self.illustration(story["icon"], x + 20, y + 9)
            self.text(story["headline"], "headline",
                      (x + 13, y + 119, x + COLUMN_WIDTH - 13, y + 206),
                      32, max_lines=3, gap=4)
            self.text(story["summary"], "body",
                      (x + 13, y + 214, x + COLUMN_WIDTH - 13, y + ROW_HEIGHT - 11),
                      15, max_lines=6, gap=3)

    def numbers(self, data):
        self.rectangle((MARGIN, 795, SIZE - MARGIN, 839), fill=RED)
        self.text(" · ".join(data["numbers_strip"]), "label",
                  (MARGIN + 14, 803, SIZE - MARGIN - 14, 831), 20,
                  fill=WHITE, align="center", valign="center")

    def briefs(self, data):
        self.line([(MARGIN, 855), (SIZE - MARGIN, 855)], width=2)
        self.text(data["briefs_heading"], "label", (32, 865, 992, 892), 24)
        # Read down each column: four items left, three right.
        for index, brief in enumerate(data["briefs"]):
            column, row = divmod(index, 4)
            x, y = MARGIN + column * 490, 907 + row * 24
            self.rectangle((x, y + 4, x + 5, y + 9), fill=RED)
            self.text(brief, "body", (x + 14, y, x + 470, y + 18), 15)

    def illustration(self, icon, x, y):
        art = Illustration(self, x, y)
        painter = getattr(art, icon, None)
        if icon not in {
            "climate", "corvette", "flats", "markets",
            "tanker", "capitol", "factory", "spychief",
        } or painter is None:
            raise ValueError(f"Unknown illustration key: {icon!r}")
        painter()

    def finish(self):
        return self.image.resize((SIZE, SIZE), Image.Resampling.LANCZOS)


class Illustration:
    """Eight compact, hand-drawn emblems in a fixed 200 x 104 area."""
    def __init__(self, page, x, y):
        self.page, self.x, self.y = page, x, y

    def points(self, points):
        return [(self.x + x, self.y + y) for x, y in points]

    def box(self, box):
        x0, y0, x1, y1 = box
        return (self.x + x0, self.y + y0, self.x + x1, self.y + y1)

    def line(self, points, fill=INK, width=2):
        self.page.line(self.points(points), fill, width)

    def rect(self, box, fill=None, outline=INK, width=2):
        self.page.rectangle(self.box(box), fill, outline, width)

    def ellipse(self, box, fill=None, outline=INK, width=2):
        self.page.ellipse(self.box(box), fill, outline, width)

    def polygon(self, points, fill=INK):
        self.page.polygon(self.points(points), fill)

    def waves(self, y):
        for offset in (0, 8):
            points = [(x, y + offset + (3 if (x // 10) % 2 else 0))
                      for x in range(10, 191, 10)]
            self.line(points, width=1.5)

    def flame(self, x, y, size=1):
        points = [(0, 28), (-10, 21), (-11, 11), (-5, 1), (-3, 10),
                  (3, -10), (8, 1), (6, 9), (13, 5), (12, 20), (6, 27)]
        self.polygon([(x + px * size, y + py * size) for px, py in points], RED)
        self.polygon([(x, y + 24 * size), (x - 4 * size, y + 17 * size),
                      (x + 3 * size, y + 7 * size), (x + 5 * size, y + 18 * size)],
                     PAPER)

    def climate(self):
        self.ellipse((19, 14, 103, 98), fill=PAPER, width=3)
        self.ellipse((43, 14, 79, 98), width=1.5)
        self.line([(20, 56), (102, 56)], width=1.5)
        self.page.arc(self.box((23, 23, 99, 69)), 192, 348, width=1.5)
        self.page.arc(self.box((23, 45, 99, 89)), 12, 168, width=1.5)
        self.polygon([(27, 35), (41, 31), (48, 39), (40, 49), (32, 46)])
        self.polygon([(66, 60), (84, 64), (79, 79), (68, 87), (62, 74)])
        self.rect((110, 34, 121, 78), fill=PAPER)
        self.ellipse((105, 71, 126, 92), fill=RED, outline=INK)
        self.line([(115.5, 49), (115.5, 80)], RED, width=4)
        for yy in (42, 52, 62):
            self.line([(122, yy), (128, yy)], width=1)
        self.rect((131, 9, 189, 44), fill=PAPER)
        self.polygon([(137, 43), (137, 54), (150, 44)])
        self.line([(144, 20), (156, 20)], width=1.5)
        self.line([(168, 30), (180, 30)], width=1.5)
        self.line([(162, 9), (157, 22), (167, 29), (160, 44)], RED, width=3)

    def corvette(self):
        self.polygon([(16, 67), (185, 67), (161, 84), (36, 84)])
        self.polygon([(60, 65), (68, 47), (108, 47), (119, 65)])
        self.rect((76, 40, 96, 49), fill=INK)
        self.line([(84, 40), (84, 21), (101, 29)], width=2)
        self.line([(71, 34), (97, 34)], width=2)
        self.rect((137, 57, 153, 66), fill=INK)
        self.line([(146, 57), (175, 54)], width=3)
        self.line([(50, 74), (154, 74)], PAPER, width=1)
        self.waves(88)
        # Quadcopter, with four rotors clear of the ship's mast.
        self.line([(144, 17), (172, 31)], width=2)
        self.line([(144, 31), (172, 17)], width=2)
        self.rect((153, 20, 163, 28), fill=INK)
        for xx, yy in ((144, 17), (172, 31), (144, 31), (172, 17)):
            self.ellipse((xx - 6, yy - 2, xx + 6, yy + 2), width=1)

    def flats(self):
        self.rect((38, 12, 163, 95), fill=PAPER, width=3)
        self.rect((34, 9, 167, 17), fill=INK)
        for xx in (49, 73, 97, 121, 145):
            for yy in (26, 47, 68):
                self.rect((xx, yy, xx + 10, yy + 12), fill=INK, outline=None)
        self.polygon([(113, 38), (163, 46), (163, 95), (130, 95),
                      (118, 77), (125, 65), (110, 54)])
        self.line([(108, 15), (98, 31), (110, 40), (100, 56),
                   (113, 68), (105, 95)], PAPER, width=5)
        self.line([(108, 15), (98, 31), (110, 40), (100, 56),
                   (113, 68), (105, 95)], width=2)
        self.polygon([(164, 85), (176, 97), (156, 97)])
        self.polygon([(125, 94), (137, 100), (116, 100)])
        self.line([(26, 100), (182, 100)], width=1.5)

    def markets(self):
        self.line([(22, 12), (22, 91), (188, 91)], width=2)
        for yy in (29, 49, 69):
            self.line([(23, yy), (180, yy)], width=0.65)
        for xx in (59, 96, 133, 170):
            self.line([(xx, 91), (xx, 95)], width=1)
        self.line([(28, 21), (51, 31), (73, 24), (95, 50),
                   (117, 43), (140, 69), (159, 62), (182, 82)], width=4)
        self.line([(157, 17), (157, 44)], RED, width=5)
        self.polygon([(147, 38), (167, 38), (157, 52)], RED)

    def tanker(self):
        # Two narrowing shorelines suggest the Strait of Hormuz.
        self.line([(12, 15), (36, 29), (47, 42), (69, 45)], width=2)
        self.line([(188, 14), (166, 23), (157, 37), (135, 43)], width=2)
        self.polygon([(22, 65), (184, 65), (166, 84), (37, 84)])
        self.rect((34, 42, 52, 64), fill=INK)
        self.rect((40, 31, 48, 42), fill=INK)
        self.rect((35, 46, 44, 50), fill=PAPER, outline=None)
        for xx in (70, 98, 126, 154):
            self.rect((xx, 52, xx + 20, 64), fill=PAPER)
            self.line([(xx + 3, 57), (xx + 17, 57)], width=1)
        self.line([(52, 73), (158, 73)], PAPER, width=1)
        self.flame(106, 22, 0.8)
        self.waves(89)

    def capitol(self):
        self.rect((26, 89, 174, 95), fill=INK)
        self.rect((34, 81, 166, 88), fill=INK)
        self.polygon([(31, 49), (100, 30), (169, 49)])
        self.rect((36, 49, 164, 56), fill=INK)
        self.ellipse((77, 10, 123, 54), fill=PAPER, width=2.5)
        self.rect((76, 33, 124, 49), fill=PAPER)
        self.line([(100, 10), (100, 3)], width=2)
        self.line([(100, 4), (112, 4), (112, 10), (101, 10)], RED, width=2)
        for xx in (44, 65, 86, 107, 128, 149):
            self.rect((xx, 57, xx + 7, 81), fill=INK)
        self.rect((145, 10, 180, 39), fill=PAPER)
        self.line([(152, 24), (160, 31), (174, 17)], RED, width=4)

    def factory(self):
        self.rect((34, 24, 45, 58), fill=INK)
        self.rect((62, 14, 74, 58), fill=INK)
        self.line([(30, 23), (48, 23)], width=2)
        self.line([(59, 13), (77, 13)], width=2)
        self.polygon([(24, 93), (24, 57), (55, 43), (55, 57),
                      (88, 43), (88, 57), (120, 43), (120, 57),
                      (156, 49), (176, 61), (176, 93)])
        for xx in (36, 61, 86, 111):
            self.rect((xx, 69, xx + 13, 82), fill=PAPER, outline=None)
        self.rect((145, 74, 162, 93), fill=PAPER, outline=None)
        self.flame(143, 30, 1)
        self.flame(169, 37, 0.65)
        self.line([(15, 96), (188, 96)], width=1.5)

    def spychief(self):
        self.ellipse((50, 2, 150, 102), fill=PAPER, width=3)
        self.ellipse((56, 8, 144, 96), width=1)
        # An actual five-point star, above the silhouette bust in the badge.
        star = []
        for index in range(10):
            angle = -math.pi / 2 + index * math.pi / 5
            radius = 15 if index % 2 == 0 else 6.5
            star.append((100 + math.cos(angle) * radius,
                         29 + math.sin(angle) * radius))
        self.polygon(star)
        self.ellipse((86, 43, 114, 70), fill=INK, outline=None)
        self.polygon([(93, 65), (107, 65), (109, 74), (125, 80),
                      (122, 88), (78, 88), (75, 80), (91, 74)])


def read_content():
    with (ROOT / "stories.json").open(encoding="utf-8") as source:
        data = json.load(source)
    for key, count in (("lead_stories", 8), ("numbers_strip", 5), ("briefs", 7)):
        if len(data[key]) != count:
            raise ValueError(f"stories.json must contain exactly {count} {key}.")
    return data


def main():
    data = read_content()
    page = Newspaper(find_fonts())
    page.masthead(data)
    page.stories(data)
    page.numbers(data)
    page.briefs(data)
    output = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
    output.mkdir(parents=True, exist_ok=True)
    page.finish().save(output / "entry.png", format="PNG", compress_level=9,
                       optimize=False, pnginfo=None)


if __name__ == "__main__":
    main()
