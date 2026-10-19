# Local Cicero metadata emulator

The local emulator verifies the path from Cicero-style numeric variables through
the real camera acquisition and into the trailing metadata records of an AIA
file. It does not require Cicero, Atticus, or a network connection.

The control is compiled only in a Debug build. Release builds do not contain the
button or its test values.

## Run the test

1. Build and run `Debug | x64` in Visual Studio.
2. Select `pco.pixelfly 1.4 USB` and initialize the camera.
3. Click the save-folder link and choose an existing folder.
4. Enable `Save`.
5. Click `Test Cicero Metadata (Debug)`.

The test forces `Exposures per image` to 4 and uses the normal
`Form1::sequenceStarted` acquisition path. The resulting AIA file should contain:

| Name | Value |
| --- | ---: |
| `emulator.sequence_id` | `42.0` |
| `emulator.magnetic_field` | `4.5` |
| `emulator.imaging_frequency_mhz` | `110.2` |

## Inspect the result

From the repository root, replace the example path with the newly saved file:

```powershell
python -c "from AIAReader import read_aia_record; r=read_aia_record(r'C:\path\to\image.aia'); print(r.pixels.shape); print(r.sequence_variables)"
```

The expected shape is `(4, rows, columns)`. The expected metadata tuple contains
the three variables above.

This test validates camera capture, four-exposure AIA writing, and metadata
decoding. It does not validate Cicero remoting, `DataStructures.dll` compatibility,
network configuration, or hardware-trigger timing.
