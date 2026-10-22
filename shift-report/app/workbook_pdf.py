"""Readable, lossless cell-value rendering of the actual immutable XLSX bytes."""

import io
import math
import posixpath
import re
import threading
import zipfile
from functools import lru_cache
from pathlib import Path
from xml.etree import ElementTree as ET

import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFError, TTFont
from reportlab.pdfgen.canvas import Canvas

from domain import ControlledError, MAX_ATTACHMENTS, sha

NS = {
    "s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "p": "http://schemas.openxmlformats.org/package/2006/relationships",
    "d": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}
FONT = "WorkbookVera"
BOLD = "WorkbookVeraBold"
FONT_LOCK = threading.Lock()
SIZE, LEADING, PAD = 8, 11, 4
WIDTH, HEIGHT = landscape(A4)
LEFT, RIGHT, BOTTOM = 34, WIDTH - 24, 30
ROW_LABEL = 34
BLUE = colors.HexColor("#003B70")


def _fonts():
    with FONT_LOCK:
        if FONT not in pdfmetrics.getRegisteredFontNames():
            directory = Path(reportlab.__file__).parent / "fonts"
            pdfmetrics.registerFont(TTFont(FONT, str(directory / "Vera.ttf")))
            pdfmetrics.registerFont(TTFont(BOLD, str(directory / "VeraBd.ttf")))


def _text(value):
    # Excel escapes are decoded once: _x005F_x0041_ is literal "_x0041_", not A.
    value = re.sub(r"_x([0-9A-Fa-f]{4})_", lambda m: chr(int(m[1], 16)), value)
    value = value.encode("utf-16-le", "surrogatepass").decode("utf-16-le")
    for char in value:
        if char in "\n\r\t":
            continue
        if ord(char) < 32 or any(
                not pdfmetrics.getFont(font).face.charToGlyph.get(ord(char), 0)
                for font in (FONT, BOLD)):
            raise ControlledError("Workbook PDF contains an unsupported character/glyph")
    return value


def _xml(archive, name):
    raw = archive.read(name)
    if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
        raise ControlledError("Workbook XML declarations are not permitted")
    return ET.fromstring(raw)


def _relations(archive, source):
    directory, filename = posixpath.split(source)
    path = posixpath.join(directory, "_rels", filename + ".rels")
    if path not in archive.namelist():
        return {}
    result = {}
    for relation in _xml(archive, path):
        if relation.get("TargetMode") == "External":
            raise ControlledError("Workbook PDF cannot resolve external relationships")
        target = relation.attrib["Target"]
        resolved = posixpath.normpath(posixpath.join(directory, target))
        if (target.startswith("/") or "\\" in target or resolved.startswith("../")
                or relation.attrib["Id"] in result):
            raise ControlledError("Invalid workbook relationship")
        result[relation.attrib["Id"]] = (resolved, relation.attrib["Type"].rsplit("/", 1)[-1])
    return result


def _rich_text(element):
    if element is None:
        raise ControlledError("Workbook string is missing")
    return _text("".join(t.text or "" for t in element.findall("s:t", NS)
                         + element.findall("s:r/s:t", NS)))


def _column(reference):
    match = re.fullmatch(r"([A-Z]{1,3})([1-9][0-9]*)", reference)
    if not match:
        raise ControlledError("Invalid workbook cell coordinate")
    number = 0
    for char in match[1]:
        number = number * 26 + ord(char) - 64
    if number > 16384 or int(match[2]) > 1048576:
        raise ControlledError("Workbook cell exceeds Excel coordinates")
    return number - 1, int(match[2])


def column_name(number):
    result = ""
    number += 1
    while number:
        number, digit = divmod(number - 1, 26)
        result = chr(65 + digit) + result
    return result


def parse_workbook(data):
    """Return every explicitly populated/styled cell, all sheets in workbook order."""
    _fonts()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        if (len(names) != len(set(names))
                or sum(item.file_size for item in archive.infolist()) > 128 * 1024 * 1024):
            raise ControlledError("Workbook archive is duplicate or exceeds safe XML budget")
        shared = []
        if "xl/sharedStrings.xml" in names:
            shared = [_rich_text(item) for item in _xml(archive, "xl/sharedStrings.xml")]
        relations = _relations(archive, "xl/workbook.xml")
        result = []
        sheets = _xml(archive, "xl/workbook.xml").findall("s:sheets/s:sheet", NS)
        if not sheets:
            raise ControlledError("Workbook has no worksheets")
        seen = set()
        for sheet in sheets:
            name = _text(sheet.attrib["name"])
            source, kind = relations[sheet.attrib["{" + NS["r"] + "}id"]]
            if (kind != "worksheet" or name in seen or not 1 <= len(name) <= 31
                    or any(char in name for char in "[]:*?/\\")):
                raise ControlledError("Unsupported or duplicate workbook sheet")
            seen.add(name)
            root = _xml(archive, source)
            widths = {}
            for col in root.findall("s:cols/s:col", NS):
                width = float(col.get("width", "12"))
                if not math.isfinite(width) or width < 0:
                    raise ControlledError("Invalid workbook column width")
                first, last = int(col.attrib["min"]) - 1, int(col.attrib["max"])
                if not 0 <= first < last <= 16384:
                    raise ControlledError("Invalid workbook column range")
                for index in range(first, last):
                    widths[index] = width
            rows = {}
            for row in root.findall("s:sheetData/s:row", NS):
                number = int(row.attrib["r"])
                if not 1 <= number <= 1048576 or number in rows:
                    raise ControlledError("Duplicate or invalid workbook row")
                cells = {}
                for cell in row.findall("s:c", NS):
                    index, actual_row = _column(cell.attrib["r"])
                    if actual_row != number or index in cells:
                        raise ControlledError("Duplicate or misplaced workbook cell")
                    value = cell.find("s:v", NS)
                    kind = cell.get("t", "n")
                    formula = cell.find("s:f", NS)
                    if formula is not None and (value is None or
                            (value.text is None and kind != "str")):
                        raise ControlledError("Workbook formula cache is unavailable")
                    if kind == "s":
                        offset = int(value.text)
                        if not 0 <= offset < len(shared):
                            raise ControlledError("Workbook shared string index is invalid")
                        text = shared[offset]
                    elif kind == "inlineStr" and formula is None:
                        text = _rich_text(cell.find("s:is", NS))
                    elif kind == "b":
                        if value is None or value.text not in ("0", "1"):
                            raise ControlledError("Invalid workbook boolean")
                        text = "TRUE" if value.text == "1" else "FALSE"
                    elif kind in ("n", "str", "e", "d"):
                        text = _text(value.text or "") if value is not None else ""
                        if kind == "n" and text and not math.isfinite(float(text)):
                            raise ControlledError("Invalid workbook numeric value")
                    else:
                        raise ControlledError("Unsupported workbook cell value type")
                    cells[index] = text
                rows[number] = cells
            images = []
            for drawing in root.findall("s:drawing", NS):
                sheet_relations = _relations(archive, source)
                path, kind = sheet_relations[drawing.attrib["{" + NS["r"] + "}id"]]
                if kind != "drawing":
                    raise ControlledError("Invalid workbook drawing relationship")
                image_relations = _relations(archive, path)
                for anchor in _xml(archive, path):
                    pictures = anchor.findall("d:pic", NS)
                    if len(pictures) != 1 or anchor.find("d:graphicFrame", NS) is not None:
                        raise ControlledError("Unsupported workbook drawing; cannot omit content")
                    blip = pictures[0].find("d:blipFill/a:blip", NS)
                    image, kind = image_relations[blip.attrib["{" + NS["r"] + "}embed"]]
                    if kind != "image":
                        raise ControlledError("Unsupported workbook image")
                    images.append(archive.read(image))
            result.append({"name": name, "rows": rows, "widths": widths, "images": images})
        return result


@lru_cache(maxsize=20000)
def _lines(text, width, font=FONT):
    # Keep exact slices (including whitespace); never elide or clip long tokens.
    text = text.replace("\t", "\\t").replace("\r", "\\r")
    result = []
    for paragraph in text.split("\n"):
        start, cursor, used, space = 0, 0, 0, -1
        while cursor < len(paragraph):
            advance = pdfmetrics.stringWidth(paragraph[cursor], font, SIZE)
            if used + advance > width:
                end = space + 1 if space >= start + (cursor - start) // 2 else cursor
                if end <= start:
                    raise ControlledError("Workbook PDF column is too narrow for a glyph")
                result.append(paragraph[start:end])
                start, cursor, used, space = end, end, 0, -1
                continue
            used += advance
            if paragraph[cursor] == " ":
                space = cursor
            cursor += 1
        result.append(paragraph[start:])
    return tuple(result)


def _bands(sheet):
    columns = sorted({col for row in sheet["rows"].values() for col in row})
    if not columns:
        return [[]], {}
    available = RIGHT - LEFT - ROW_LABEL
    widths = {col: min(235, max(85, sheet["widths"].get(col, 18) * 5))
              for col in columns}
    bands, current, used = [], [], 0
    for col in columns:
        if current and used + widths[col] > available:
            bands.append(current)
            current = [columns[0]]
            used = widths[columns[0]]
        current.append(col)
        used += widths[col]
    if current:
        bands.append(current)
    for band in bands:
        extra = (available - sum(widths[col] for col in band)) / len(band)
        # Per-band widths must not overwrite the widths used by other bands.
        if extra < 0:
            raise ControlledError("Workbook PDF column band exceeds page width")
    return bands, widths


def render_workbook_pdf(data, max_bytes=MAX_ATTACHMENTS):
    """Render source values/caches, not reconstructed evidence or an Excel summary."""
    try:
        sheets = parse_workbook(data)
        stream = io.BytesIO()
        canvas = Canvas(stream, pagesize=(WIDTH, HEIGHT), pageCompression=1, invariant=1)
        canvas.setTitle("Complete workbook values")
        canvas.setAuthor("Hyper-V observability report runtime")
        canvas.setSubject("Source XLSX SHA256: " + sha(data))
        page = 0
        for sheet_index, sheet in enumerate(sheets, 1):
            bands, preferred = _bands(sheet)
            for band_index, band in enumerate(bands, 1):
                available = RIGHT - LEFT - ROW_LABEL
                extra = (available - sum(preferred[col] for col in band)) / len(band) if band else 0
                widths = {col: preferred[col] + extra for col in band}
                rows = sorted(sheet["rows"].items())
                first = rows[0] if rows else None
                header = ([_lines(first[1].get(col, ""), widths[col] - 2 * PAD, BOLD)
                           for col in band] if first else [])
                repeat_header = bool(header) and max(map(len, header)) <= 8

                def draw_row(number, content, offset, count, y, bold=False, continued=False):
                    height = count * LEADING + 2 * PAD
                    canvas.setFont(FONT, 7)
                    canvas.setFillColor(colors.black)
                    canvas.drawString(LEFT, y - 12, str(number) + ("+" if continued else ""))
                    x = LEFT + ROW_LABEL
                    for col, lines in zip(band, content):
                        canvas.setFillColor(BLUE if bold else colors.white)
                        canvas.rect(x, y - height, widths[col], height, fill=1, stroke=0)
                        canvas.setStrokeColor(colors.HexColor("#CCD5DF"))
                        canvas.rect(x, y - height, widths[col], height, fill=0, stroke=1)
                        canvas.setFillColor(colors.white if bold else colors.black)
                        canvas.setFont(BOLD if bold else FONT, SIZE)
                        for line_index, text in enumerate(lines[offset:offset + count]):
                            canvas.drawString(x + PAD, y - PAD - SIZE - line_index * LEADING, text)
                        x += widths[col]
                    return y - height

                def new_page(repeat=False, images=False):
                    nonlocal page
                    if page:
                        canvas.showPage()
                    page += 1
                    canvas.setFillColor(BLUE)
                    canvas.setFont(BOLD, 12)
                    canvas.drawString(LEFT, HEIGHT - 26,
                                      f"{sheet_index}/{len(sheets)}  {sheet['name']}")
                    canvas.setFont(FONT, 7)
                    canvas.setFillColor(colors.black)
                    canvas.drawString(LEFT, HEIGHT - 39,
                                      f"Workbook values | column band {band_index}/{len(bands)}"
                                      " | formula caches, not recalculation | row + = continued")
                    canvas.drawString(LEFT, HEIGHT - 51, "XLSX SHA256: " + sha(data))
                    canvas.drawString(LEFT, 15, f"Page {page} | blank cells remain blank; TRUE/FALSE are booleans;"
                                      r" tabs/CR displayed as \t/\r")
                    y = HEIGHT - 62
                    if images:
                        for image in sheet["images"]:
                            reader = ImageReader(io.BytesIO(image))
                            iw, ih = reader.getSize()
                            if iw <= 0 or ih <= 0:
                                raise ControlledError("Invalid workbook image dimensions")
                            scale = min((RIGHT - LEFT) / iw, 60 / ih)
                            if y - ih * scale < BOTTOM + 120:
                                raise ControlledError("Workbook images exceed readable page space")
                            canvas.drawImage(reader, LEFT, y - ih * scale, iw * scale, ih * scale, mask="auto")
                            y -= ih * scale + 8
                    canvas.setFont(BOLD, SIZE)
                    x = LEFT + ROW_LABEL
                    for col in band:
                        canvas.drawString(x + PAD, y - 10, column_name(col))
                        x += widths[col]
                    y -= 18
                    if repeat and repeat_header:
                        y = draw_row(first[0], header, 0, max(map(len, header)), y, bold=True)
                    return y

                y = new_page(images=True)
                if not rows or not band:
                    canvas.setFont(FONT, SIZE)
                    canvas.drawString(LEFT, y - 14, "Empty worksheet (no populated cells).")
                for row_index, (number, cells) in enumerate(rows):
                    bold = row_index == 0
                    content = [_lines(cells.get(col, ""), widths[col] - 2 * PAD,
                                      BOLD if bold else FONT) for col in band]
                    remaining = max(map(len, content), default=1)
                    offset = 0
                    while offset < remaining:
                        capacity = int((y - BOTTOM - 2 * PAD) // LEADING)
                        if capacity < 1:
                            y = new_page(repeat=not bold)
                            continue
                        count = min(capacity, remaining - offset)
                        y = draw_row(number, content, offset, count, y, bold, offset > 0)
                        offset += count
                        if offset < remaining:
                            y = new_page(repeat=not bold)
        canvas.save()
        result = stream.getvalue()
        if len(result) > max_bytes:
            raise ControlledError("Complete workbook PDF exceeds remaining 5 MiB payload budget")
        return result
    except ControlledError:
        raise
    except (zipfile.BadZipFile, ET.ParseError, KeyError, TypeError, ValueError,
            IndexError, OSError, RuntimeError, TTFError) as error:
        raise ControlledError("Workbook PDF conversion failed; no content may be omitted") from error
