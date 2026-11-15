"""Minimal stdlib reader for ASCII DXF files.

It exposes only the ezdxf surface this package's validator uses -- ``readfile``
returning a document with ``header``, ``dxfversion`` and ``modelspace()``, and
entities answering ``dxftype()``, ``.dxf.layer``, ``.dxf.text``, ``.dxf.start``,
``.dxf.end``, ``.dxf.location``, ``.text``, ``.closed``, ``.is_closed``,
``.get_points()`` and ``.vertices`` -- with ezdxf's semantics at those call
sites.  A structurally broken file raises ``DXFStructureError``, so the reads
the validator already guards with ``try/except`` keep failing as before.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, NamedTuple


class DXFStructureError(Exception):
    """Raised for a file that is not a readable ASCII DXF."""


class Vec3(NamedTuple):
    """ezdxf point semantics: a float triple that also answers .x/.y/.z."""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


NULLVEC = Vec3()

# Group-code value types, following the DXF reference (everything else is text).
_INT_RANGES = ((60, 79), (90, 99), (160, 179), (270, 289), (370, 389), (400, 409), (420, 429), (440, 459), (1060, 1071))
_FLOAT_RANGES = ((10, 59), (110, 149), (210, 239), (460, 469), (1010, 1059))
# Sub-entities ezdxf binds to their owner instead of listing in a layout.
_BOUND = {"VERTEX", "ATTRIB", "SEQEND"}


def _typed(code: int, value: str) -> Any:
    """The value a group code carries; ezdxf types these when it loads the tag."""
    for lo, hi in _INT_RANGES:
        if lo <= code <= hi:
            return int(float(value))
    for lo, hi in _FLOAT_RANGES:
        if lo <= code <= hi:
            return float(value)
    return value


class _Namespace:
    """The ``entity.dxf`` attribute namespace."""

    _POINTS = {"start": 10, "end": 11, "location": 10, "insert": 10}
    _VALUES = {"layer": (8, "0"), "text": (1, ""), "flags": (70, 0)}

    def __init__(self, tags: list[tuple[int, Any]]) -> None:
        self._tags = tags

    def _first(self, code: int, default: Any = None) -> Any:
        for tag_code, value in self._tags:
            if tag_code == code:
                return value
        return default

    def __getattr__(self, name: str) -> Any:
        if name in self._POINTS:
            base = self._POINTS[name]
            if self._first(base) is None:
                return NULLVEC
            return Vec3(self._first(base, 0.0), self._first(base + 10, 0.0), self._first(base + 20, 0.0))
        if name in self._VALUES:
            code, default = self._VALUES[name]
            return self._first(code, default)
        raise AttributeError(name)


class DXFEntity:
    def __init__(self, dxftype: str, tags: list[tuple[int, Any]]) -> None:
        self._dxftype = dxftype
        self._tags = tags
        self.dxf = _Namespace(tags)
        self.vertices: list[DXFEntity] = []

    def dxftype(self) -> str:
        return self._dxftype

    @property
    def closed(self) -> bool:
        """LWPOLYLINE/POLYLINE closed flag (bit 1 of group code 70)."""
        return bool(self.dxf.flags & 1)

    is_closed = closed

    @property
    def text(self) -> str:
        """MTEXT content: the code 3 continuation chunks then the code 1 tail."""
        parts = [value for code, value in self._tags if code == 3]
        parts.append(next((value for code, value in self._tags if code == 1), ""))
        return "".join(parts)

    def get_points(self, format: str = "xyseb") -> list[tuple[float, ...]]:
        """LWPOLYLINE vertices; each group code 10 opens a new vertex."""
        points: list[dict[str, float]] = []
        fields = {20: "y", 40: "s", 41: "e", 42: "b"}
        for code, value in self._tags:
            if code == 10:
                points.append({"x": float(value), "y": 0.0, "s": 0.0, "e": 0.0, "b": 0.0})
            elif points and code in fields:
                points[-1][fields[code]] = float(value)
        return [tuple(point[key] for key in format) for point in points]


class Drawing:
    def __init__(self, header: dict[str, Any], entities: list[DXFEntity]) -> None:
        self.header = header
        self.dxfversion = str(header.get("$ACADVER", "AC1009"))
        self._modelspace = entities

    def modelspace(self) -> list[DXFEntity]:
        return self._modelspace


_CODEPAGES = {"932": "cp932", "936": "gbk", "949": "uhc", "950": "big5"}


def _probe(lines: list[str], name: str) -> str | None:
    """The value tag of a header variable, read from a latin-1 view of the file."""
    for index in range(0, len(lines) - 2, 2):
        if lines[index].strip() == "9" and lines[index + 1].strip() == name:
            return lines[index + 3] if index + 3 < len(lines) else None
    return None


def _decode(data: bytes) -> list[str]:
    lines = data.decode("latin-1").splitlines()
    version = (_probe(lines, "$ACADVER") or "AC1009").strip()
    if version >= "AC1021":
        encoding = "utf-8"
    else:
        codepage = (_probe(lines, "$DWGCODEPAGE") or "ANSI_1252").strip().upper()
        number = codepage[5:] if codepage.startswith("ANSI_") else codepage
        encoding = _CODEPAGES.get(number, "cp" + number)
    try:
        return data.decode(encoding, errors="surrogateescape").splitlines()
    except LookupError:
        return data.decode("cp1252", errors="surrogateescape").splitlines()


def _tags(lines: list[str]) -> list[tuple[int, Any]]:
    if len(lines) % 2:
        raise DXFStructureError("premature end of file: dangling group code")
    tags = []
    for index in range(0, len(lines), 2):
        raw = lines[index].strip()
        try:
            code = int(raw)
        except ValueError:
            raise DXFStructureError(f"invalid group code {raw!r} at line {index + 1}") from None
        try:
            tags.append((code, _typed(code, lines[index + 1])))
        except ValueError:
            raise DXFStructureError(f"invalid value for group code {code} at line {index + 2}") from None
    return tags


def _strip_appdata(tags: list[tuple[int, Any]]) -> list[tuple[int, Any]]:
    """Drop 102 application-data groups, which ezdxf keeps out of the namespace."""
    if not any(code == 102 for code, _ in tags):
        return tags
    out, inside = [], False
    for code, value in tags:
        if code == 102:
            inside = not value.startswith("}")
        elif not inside:
            out.append((code, value))
    return out


def readfile(filename: Any) -> Drawing:
    tags = _tags(_decode(Path(filename).read_bytes()))
    header: dict[str, Any] = {}
    block_records: dict[str, str] = {}
    raw_entities: list[tuple[str, list[tuple[int, Any]]]] = []

    section: str | None = None
    saw_eof = False
    index = 0
    while index < len(tags):
        code, value = tags[index]
        if code == 999:
            index += 1
            continue
        if code == 0 and value == "SECTION":
            if section is not None:
                raise DXFStructureError("nested SECTION")
            if index + 1 >= len(tags) or tags[index + 1][0] != 2:
                raise DXFStructureError("SECTION without a name tag")
            section = tags[index + 1][1].strip()
            index += 2
            continue
        if code == 0 and value == "ENDSEC":
            if section is None:
                raise DXFStructureError("ENDSEC without SECTION")
            section = None
            index += 1
            continue
        if code == 0 and value == "EOF":
            saw_eof = True
            break
        if section is None:
            raise DXFStructureError(f"tag ({code}, {value!r}) outside of a SECTION")

        if section == "HEADER" and code == 9:
            name = value.strip()
            index += 1
            values = []
            while index < len(tags) and tags[index][0] not in (0, 9):
                values.append(tags[index][1])
                index += 1
            if len(values) == 1:
                header[name] = values[0]
            elif len(values) >= 2:
                header[name] = Vec3(*(list(values[:3]) + [0.0] * (3 - len(values[:3]))))
            continue
        if code == 0 and section in ("TABLES", "ENTITIES"):
            entity_type = value
            start = index + 1
            index = start
            while index < len(tags) and tags[index][0] != 0:
                index += 1
            entity_tags = _strip_appdata(tags[start:index])
            if section == "TABLES" and entity_type == "BLOCK_RECORD":
                namespace = _Namespace(entity_tags)
                name = namespace._first(2)
                if name is not None:
                    block_records[str(name).strip().upper()] = str(namespace._first(5, "")).strip().upper()
            elif section == "ENTITIES":
                raw_entities.append((entity_type, entity_tags))
            continue
        index += 1

    if not saw_eof:
        raise DXFStructureError("missing DXF EOF")
    if not header and not raw_entities and not block_records:
        raise DXFStructureError("no DXF sections found")

    model_handle = block_records.get("*MODEL_SPACE")
    entities: list[DXFEntity] = []
    owner: DXFEntity | None = None
    for entity_type, entity_tags in raw_entities:
        entity = DXFEntity(entity_type, entity_tags)
        if entity_type in _BOUND:
            if entity_type == "VERTEX" and owner is not None:
                owner.vertices.append(entity)
            elif entity_type == "SEQEND":
                owner = None
            continue
        owner = entity
        handle = entity.dxf._first(330)
        in_model = (str(handle).strip().upper() == model_handle) if (handle is not None and model_handle) else not entity.dxf._first(67, 0)
        if in_model:
            entities.append(entity)
    return Drawing(header, entities)
