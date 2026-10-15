"""Read Simplicio AIA image files into NumPy arrays.

One AIA file contains one acquisition set. Its array order is
``(exposure, row, column)``. Multiple files can be stacked into the analysis
code's expected order: ``(set, exposure, row, column)``.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import struct
from typing import Iterable

import numpy as np


_HEADER = struct.Struct("<3sHHHH")
_MAGIC = b"AIA"
_UINT16_BYTES = 2


class AIAFormatError(ValueError):
    """Raised when a file does not match the Simplicio AIA format."""


@dataclass(frozen=True)
class AIARecord:
    """Decoded pixels and optional sequence variables from one AIA file."""

    path: Path
    pixels: np.ndarray
    sequence_variables: tuple[tuple[str, float], ...]

    @property
    def exposures(self) -> int:
        return int(self.pixels.shape[0])

    @property
    def rows(self) -> int:
        return int(self.pixels.shape[1])

    @property
    def columns(self) -> int:
        return int(self.pixels.shape[2])


def _parse_sequence_variables(data: bytes, path: Path) -> tuple[tuple[str, float], ...]:
    """Decode repeated UTF-8-name/NUL/little-endian-double metadata records."""

    variables: list[tuple[str, float]] = []
    position = 0

    while position < len(data):
        name_end = data.find(b"\0", position)
        if name_end < 0:
            raise AIAFormatError(
                f"{path}: sequence-variable name is missing its NUL terminator"
            )

        try:
            name = data[position:name_end].decode("utf-8")
        except UnicodeDecodeError as error:
            raise AIAFormatError(
                f"{path}: sequence-variable name is not valid UTF-8"
            ) from error

        position = name_end + 1
        if len(data) - position < 8:
            raise AIAFormatError(
                f"{path}: sequence variable {name!r} is missing its 8-byte value"
            )

        value = struct.unpack_from("<d", data, position)[0]
        variables.append((name, value))
        position += 8

    return tuple(variables)


def read_aia_record(path: str | Path) -> AIARecord:
    """Read one AIA file, including optional sequence-variable metadata.

    The returned pixel array has shape ``(exposures, rows, columns)`` and
    dtype ``uint16``.
    """

    aia_path = Path(path)
    with aia_path.open("rb") as stream:
        header = stream.read(_HEADER.size)
        if len(header) != _HEADER.size:
            raise AIAFormatError(
                f"{aia_path}: truncated header; expected {_HEADER.size} bytes"
            )

        magic, integer_bytes, rows, columns, exposures = _HEADER.unpack(header)
        if magic != _MAGIC:
            raise AIAFormatError(
                f"{aia_path}: invalid signature {magic!r}; expected {_MAGIC!r}"
            )
        if integer_bytes != _UINT16_BYTES:
            raise AIAFormatError(
                f"{aia_path}: unsupported pixel width {integer_bytes}; expected 2"
            )
        if rows == 0 or columns == 0 or exposures == 0:
            raise AIAFormatError(
                f"{aia_path}: dimensions must be nonzero; "
                f"got exposures={exposures}, rows={rows}, columns={columns}"
            )

        pixel_count = exposures * rows * columns
        pixels = np.fromfile(stream, dtype="<u2", count=pixel_count)
        if pixels.size != pixel_count:
            raise AIAFormatError(
                f"{aia_path}: truncated pixel payload; expected {pixel_count} "
                f"pixels, found {pixels.size}"
            )

        trailing_data = stream.read()

    pixels = pixels.reshape((exposures, rows, columns))
    sequence_variables = _parse_sequence_variables(trailing_data, aia_path)
    return AIARecord(aia_path, pixels, sequence_variables)


def read_aia(path: str | Path) -> np.ndarray:
    """Return one AIA file as ``(exposures, rows, columns)``."""

    return read_aia_record(path).pixels


def _resolve_paths(source: str | Path | Iterable[str | Path]) -> list[Path]:
    if isinstance(source, (str, Path)):
        source_path = Path(source)
        if source_path.is_dir():
            paths = list(source_path.glob("*.aia"))
        else:
            paths = [source_path]
    else:
        paths = [Path(path) for path in source]

    paths.sort(key=lambda path: (path.name.casefold(), str(path).casefold()))
    if not paths:
        raise FileNotFoundError("No .aia files were found")
    return paths


def load_aia_series(
    source: str | Path | Iterable[str | Path],
    *,
    expected_exposures: int | None = 4,
) -> np.ndarray:
    """Stack AIA files as ``(sets, exposures, rows, columns)``.

    Directory contents are sorted by filename. Simplicio's timestamp filenames
    therefore sort chronologically. Set ``expected_exposures=None`` to load
    legacy files without requiring a particular exposure count.
    """

    paths = _resolve_paths(source)
    image_sets: list[np.ndarray] = []
    expected_shape: tuple[int, int, int] | None = None

    for path in paths:
        pixels = read_aia(path)
        if expected_exposures is not None and pixels.shape[0] != expected_exposures:
            raise AIAFormatError(
                f"{path}: expected {expected_exposures} exposures, "
                f"found {pixels.shape[0]}"
            )

        if expected_shape is None:
            expected_shape = pixels.shape
        elif pixels.shape != expected_shape:
            raise AIAFormatError(
                f"{path}: shape {pixels.shape} does not match the first "
                f"file's shape {expected_shape}"
            )
        image_sets.append(pixels)

    return np.stack(image_sets, axis=0)


def _main() -> int:
    parser = argparse.ArgumentParser(
        description="Load Simplicio AIA files into a four-dimensional NumPy array."
    )
    parser.add_argument("source", type=Path, help="An .aia file or a directory of files")
    parser.add_argument(
        "--expected-exposures",
        type=int,
        default=4,
        help="required exposures per set (default: 4; use 0 to allow any count)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="optional .npy output path",
    )
    args = parser.parse_args()

    expected_exposures = args.expected_exposures or None
    try:
        images = load_aia_series(args.source, expected_exposures=expected_exposures)
    except (AIAFormatError, FileNotFoundError, OSError) as error:
        parser.error(str(error))
    print(f"shape={images.shape} dtype={images.dtype}")
    if args.output is not None:
        np.save(args.output, images, allow_pickle=False)
        print(f"saved {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
