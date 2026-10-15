# Reading Simplicio AIA files in Python

`AIAReader.py` reads the binary format written by `ImageData::saveFile` without
changing that established format.

## Array dimensions

One AIA file is one acquisition set:

```python
from AIAReader import read_aia

images = read_aia("2026-09-02-16;07;48.aia")
print(images.shape)  # (exposures, rows, columns)
```

A folder of files becomes the four-dimensional array used by the Sommer Lab
analysis code:

```python
from AIAReader import load_aia_series

images = load_aia_series(r"D:\Data\my-run")
print(images.shape)  # (sets, 4, rows, columns)
```

The indices are therefore:

```python
pixel_value = images[set_index, exposure_index, row, column]
```

The resulting array can be passed directly to the supplied analysis package:

```python
from ImageAnalysis import ImageAnalysisCode
from AIAReader import load_aia_series

raw_images = load_aia_series(r"D:\Data\my-run")
optical_density = ImageAnalysisCode.absImagingSimpleV2(
    raw_images,
    subtract_burntin=True,
)
```

This direct call is currently required for Pixelfly data. In the live
`insommer/AnalysisCodeNew` repository, `PreprocessBinImgs()` only loads Zyla
`.dat` files and Chameleon `.pgm` files. It does not recognize AIA files or a
Pixelfly camera type. Likewise, `Applications/Analyze_Atom_Pictures.py` calls
that preprocessing function, so Pixelfly cannot yet be selected through that
script without a separate integration change.

The confirmed current workflow is therefore:

1. Simplicio writes one AIA file for each acquisition set.
2. `load_aia_series()` reads and stacks those files into
   `(set, exposure, row, column)`.
3. The resulting NumPy array is passed to `absImagingSimpleV2()` or other
   analysis functions that accept an already-loaded image array.

`load_aia_series` requires four exposures by default. To open legacy
three-exposure files:

```python
legacy_images = load_aia_series(
    r"D:\Data\legacy-run",
    expected_exposures=3,
)
```

or allow the exposure count recorded in the first file:

```python
images = load_aia_series(path, expected_exposures=None)
```

## Four-exposure meaning

The current `insommer/AnalysisCodeNew` version of `ImageAnalysisCode.py` uses
four frames in its burn-in subtraction mode in this order:

1. Burn-in/reference
2. Probe with atoms
3. Probe without atoms
4. Dark/background

It calculates:

```python
with_atoms = images[:, 1] - images[:, 0]
without_atoms = images[:, 2] - images[:, 3]
optical_density = -np.log(with_atoms / without_atoms)
```

The analysis code also supports a four-frame sequence in which frame zero is
discarded and frames one through three are the usual with-atoms, without-atoms,
and background images. The acquisition sequence determines which interpretation
is correct; the AIA file records the frame order but does not label the frames.

This was checked against GitHub commit
`074594a58901286af7bd7c40b9505b70aca5935d` (October 8, 2026). A synthetic
four-exposure AIA series loaded by `AIAReader.py` produced the expected optical
density through that exact version of `absImagingSimpleV2()` in both its
burn-in and skip-first-frame paths.

## File format

All multibyte values are little-endian.

| Bytes | Meaning |
| --- | --- |
| 3 | ASCII signature `AIA` |
| 2 | Bytes per pixel; currently `2` |
| 2 | Rows |
| 2 | Columns |
| 2 | Exposure layers |
| `rows × columns × layers × 2` | Unsigned 16-bit pixels, layer first |
| Remaining bytes | Optional sequence variables |

Each optional sequence variable is stored as a UTF-8 name, a zero byte, and an
eight-byte little-endian floating-point value. `read_aia_record()` exposes these
values.

## Command line

The reader can validate a folder and optionally create a NumPy `.npy` file:

```powershell
python AIAReader.py "D:\Data\my-run" --output my-run.npy
```

The saved `.npy` retains the exact `(sets, exposures, rows, columns)` shape and
the unsigned 16-bit pixel values.
