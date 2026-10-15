import struct
import tempfile
import unittest
from pathlib import Path

import numpy as np

from AIAReader import AIAFormatError, load_aia_series, read_aia, read_aia_record


def write_aia(
    path: Path,
    pixels: np.ndarray,
    sequence_variables: tuple[tuple[str, float], ...] = (),
) -> None:
    exposures, rows, columns = pixels.shape
    with path.open("wb") as stream:
        stream.write(struct.pack("<3sHHHH", b"AIA", 2, rows, columns, exposures))
        stream.write(np.asarray(pixels, dtype="<u2").tobytes(order="C"))
        for name, value in sequence_variables:
            stream.write(name.encode("utf-8"))
            stream.write(b"\0")
            stream.write(struct.pack("<d", value))


class AIAReaderTests(unittest.TestCase):
    def test_reads_four_exposures_in_layer_row_column_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "set.aia")
            expected = np.arange(4 * 3 * 5, dtype=np.uint16).reshape(4, 3, 5)
            write_aia(path, expected, (("TOF", 1.25), ("bias", -2.0)))

            record = read_aia_record(path)

            np.testing.assert_array_equal(record.pixels, expected)
            self.assertEqual(record.pixels.shape, (4, 3, 5))
            self.assertEqual(record.pixels.dtype, np.dtype("uint16"))
            self.assertEqual(record.sequence_variables, (("TOF", 1.25), ("bias", -2.0)))

    def test_stacks_files_as_set_exposure_row_column(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            first = np.full((4, 2, 3), 10, dtype=np.uint16)
            second = np.full((4, 2, 3), 20, dtype=np.uint16)
            write_aia(folder / "2026-01-01-00;00;02.aia", second)
            write_aia(folder / "2026-01-01-00;00;01.aia", first)

            series = load_aia_series(folder)

            self.assertEqual(series.shape, (2, 4, 2, 3))
            np.testing.assert_array_equal(series[0], first)
            np.testing.assert_array_equal(series[1], second)

    def test_reads_legacy_three_exposure_file_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "legacy.aia")
            expected = np.arange(18, dtype=np.uint16).reshape(3, 2, 3)
            write_aia(path, expected)

            np.testing.assert_array_equal(read_aia(path), expected)
            series = load_aia_series(path, expected_exposures=3)
            self.assertEqual(series.shape, (1, 3, 2, 3))

    def test_four_exposure_series_rejects_legacy_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "legacy.aia")
            write_aia(path, np.zeros((3, 2, 3), dtype=np.uint16))

            with self.assertRaisesRegex(AIAFormatError, "expected 4 exposures, found 3"):
                load_aia_series(path)

    def test_rejects_truncated_pixel_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "truncated.aia")
            path.write_bytes(struct.pack("<3sHHHH", b"AIA", 2, 2, 3, 4) + b"\0\0")

            with self.assertRaisesRegex(AIAFormatError, "truncated pixel payload"):
                read_aia(path)


if __name__ == "__main__":
    unittest.main()
