# jadeglass change log

This file records changes made for the jadeglass Pixelfly adaptation of Simplicio.

## 2026-10-19 — Make the external signal start a complete exposure set

These changes are included on branch `vs2026` in the user's `shavedlobster/Simplicio` fork.

### Finding

- The **Exposures per image** value was already passed from `Form1` to `CameraThread`, which loops exactly that many times.
- The previous Pixelfly mode waited for a separate hardware trigger inside every exposure iteration, so a four-exposure set required four manual pulses.
- The `insommer/Simplicio` UI calls the intended mode `Ext Start`, indicating that the external signal starts the set rather than directly timing every exposure.

### Changed

- `Driver.h`, `CameraThread.h`, and `CameraThread.cpp`
  - Rename the camera capability from External Trigger to External Start.
  - Notify the driver at the beginning of every complete image set.
- `PixelflyUsbDriver.h` and `PixelflyUsbDriver.cpp`
  - Arm in PCO software-trigger mode for both Internal and Ext Start operation.
  - In Ext Start mode, queue the first frame and nonblockingly watch the physical exposure-trigger input.
  - Require a low-to-high transition so a stale high signal cannot start multiple repeated sets.
  - After the start transition, call `PCO_ForceTrigger` once for every exposure requested by Simplicio without requiring more external pulses.
  - Reset the external-start state for each set during repeated acquisition and keep Interrupt Acquisition responsive while waiting.
- `Form1.h` and `Form1.cpp`
  - Rename the selector option from `External` to `Ext Start` to describe the behavior accurately.
- `PIXELFLY_SETUP.md`
  - Document one external start event per image set and automatic triggering of the selected exposure count.

### Validation

- Verified the control flow: `Form1` passes the selected exposure count to `CameraThread`; `beginImageSet()` runs once per set; and the `for (lay < layers)` loop calls `expose()` exactly once per selected exposure.
- `Debug | x64` compiled and linked successfully with 64-bit MSBuild in both the working checkout and the active Visual Studio source checkout: 0 errors and the existing obsolete security-attribute warning.
- The active checkout's standard `x64\Debug\forms2.exe` remained locked by the previous process/debug session, so its verified current binary was written to `x64\DebugExtStart\forms2.exe`.
- Physical validation with the Pixelfly trigger input remains required.

## 2026-10-19 — Port Pixelfly external-trigger support

These changes are included on branch `vs2026` in the user's `shavedlobster/Simplicio` fork.

### Source reviewed

- Fetched the current `insommer/Simplicio` `vs2026` branch.
- Used commits `036c385` (trigger-mode selector) and `07dfbf3` (Cicero/Pixelfly external-trigger wiring) as the reference implementation.
- Did not merge the lab branch wholesale, so the local metadata-emulator and camera-setting work remains intact.

### Changed

- `Form1.h` and `Form1.cpp`
  - Add an Internal/External trigger selector, defaulting to Internal.
  - Apply the selected mode before every acquisition, including acquisitions started by Cicero.
  - Lock the selector while acquisition is active and restore it afterward.
  - Reject External mode for camera adapters that do not explicitly support it.
  - Move the Debug-only metadata-emulator button below the server controls so it no longer overlaps the acquisition indicator.
- `Driver.h`, `CameraThread.h`, and `CameraThread.cpp`
  - Add an instance-level trigger-mode interface and pass the selected mode to the active camera driver.
  - Poll image completion at 1 ms intervals so waiting for an external trigger does not run a full-speed busy loop.
- `PixelflyUsbDriver.h` and `PixelflyUsbDriver.cpp`
  - Store trigger mode per Pixelfly instance.
  - Arm with the PCO SDK's software-trigger or external-trigger constant.
  - Continue using `PCO_ForceTrigger` only for Internal mode.
  - In External mode, queue the transfer buffer and wait for the hardware trigger to complete it; the existing Interrupt Acquisition path can cancel the wait.
- `PIXELFLY_SETUP.md`
  - Document both trigger modes, the four-pulse requirement for a four-exposure set, cancellation behavior, and the physical-signal safety boundary.

### Deliberate differences from `insommer/Simplicio`

- Do not use a static trigger flag shared by every driver instance.
- Reset the driver to Internal whenever Internal is selected; the lab implementation only set the flag to External.
- Do not poll `PCO_GetExpTrigSignalStatus` indefinitely and then call `PCO_ForceTrigger` in external mode.

### Validation

- `Debug | x64` and `Release | x64` compiled successfully with Visual Studio 2026 MSBuild 18.9.1: 0 errors and the existing obsolete security-attribute warning.
- All 5 Python AIA reader regression tests passed with `unittest`.
- Confirmed that Visual Studio was still running the older checkout at `C:\Users\jadeg\source\repos\Simplicio`; synchronized only the reviewed trigger and metadata files into that local checkout without committing or pushing them.
- Built the active Visual Studio checkout with 64-bit MSBuild. Its existing `x64\Debug\forms2.exe` was locked by the prior Visual Studio/debug session, so the verified current executable was written to `x64\DebugTrigger\forms2.exe`; that binary contains the earlier `Trigger:` and `External` UI strings. The standard Visual Studio output still needs to be rebuilt after the old process/debug session releases its executable.
- Physical Pixelfly trigger validation remains pending.

## 2026-10-15 — Add a local Cicero metadata emulator

These changes are included on branch `vs2026` in the user's `shavedlobster/Simplicio` fork.

### Added

- `CICERO_METADATA_TEST.md`
  - Documents the Debug-only emulator workflow, its fixed test variables, the Python validation command, and the parts of the real Cicero pipeline that it does not test.

### Changed

- `Form1.h`, `Form1.cpp`, and `CameraThread.h`
  - Add a `Test Cicero Metadata (Debug)` button only when the application is compiled with `_DEBUG`.
  - Require an initialized and idle camera, an existing selected save folder, and enabled saving before the emulator can start.
  - Create three known numeric variables, force a four-exposure acquisition, and send them through the existing `Form1::sequenceStarted` path used by Cicero.
  - Keep Release builds and normal acquisition behavior unchanged.

### Validation

- `Debug | x64` and `Release | x64` compiled successfully with Visual Studio 2026 MSBuild 18.9.1: 0 errors and the existing obsolete security-attribute warning.
- All 5 Python AIA reader regression tests passed with `unittest`.
- Physical-camera validation remains to be performed with the Debug x64 application and Pixelfly camera.

## Repository policy

- Keep work local unless it is explicitly sent to the user's fork.
- Do not push changes to the upstream `atsommer/Simplicio` repository.
- Add an entry here for every repository change made from September 2, 2026 onward.
- Record the affected file locations, the purpose of the change, and the validation performed.
- Do not include unrelated pre-existing working-tree changes in commits or patches.

At initialization, the active Visual Studio checkout's `origin` remote pointed to `https://github.com/atsommer/Simplicio.git`. Publishing is performed from a separate checkout whose `origin` is the user's `shavedlobster/Simplicio` fork.

## 2026-09-02 — Initialize change log

### Added

- `jadeglassCHANGELOG.md`
  - Created this running record at the repository root.
  - Added the local/fork-only repository policy above.

### Validation

- Confirmed that this entry only adds a new documentation file.
- No commit or push was performed.

## 2026-09-01 to 2026-09-02 — First pco.pixelfly 1.4 USB capture

All changes in this section remain uncommitted in the local `vs2026` checkout.

### Added

- `PixelflyUsbDriver.h`
  - Declares the Simplicio `Driver` implementation for the pco.pixelfly 1.4 USB.
  - Stores the PCO camera handle, SDK buffer, transfer event, dimensions, bit depth, and acquisition state.

- `PixelflyUsbDriver.cpp`
  - Opens PCO camera index 0 and verifies `CAMERATYPE_PCO_USBPIXELFLY`.
  - Reads the camera description, ROI, binning, dimensions, and dynamic resolution.
  - Arms the camera in software-trigger mode and automatic acquire mode.
  - Allocates an SDK image buffer, queues transfers with `PCO_AddBufferEx`, and triggers exposures with `PCO_ForceTrigger`.
  - Checks transfer completion and driver status before copying raw pixels into Simplicio's 16-bit image buffer.
  - Cancels transfers, stops recording, frees buffers, and closes the camera during cleanup.
  - Reports PCO SDK errors through the Forms interface.

- `PIXELFLY_SETUP.md`
  - Documents the installed PCO software, relevant source files, Visual Studio build procedure, first-camera test, and SDK call sequence.

### Changed

- `Form1.h`, camera list initialization near the `cameraListBox` control
  - Added `pco.pixelfly 1.4 USB` to the visible Camera Type list.

- `CameraThread.cpp`, includes, `init`, `changeCamera`, and `takeImages`
  - Includes and constructs `PixelflyUsbDriver` when the Pixelfly item is selected.
  - Keeps legacy Sensicam and Princeton/WinView adapters out of the x64 build because their bundled libraries are 32-bit.
  - Checks `armCamera()` and restores the form state if arming fails.

- `forms2.vcxproj`, project configurations and build inputs
  - Added Debug and Release x64 configurations.
  - Added an overridable `PCO_SDK_DIR`/`PcoSdkDir` path with the installed pco.cpp directory as its default.
  - Added PCO include and library paths plus `sc2_cam.lib` for x64 builds.
  - Added the Pixelfly source and header to the project.
  - Excluded legacy 32-bit camera sources from x64 builds.
  - Copies `sc2_cam.dll` into the x64 output directory after a successful build.

- `forms2.vcxproj.filters`
  - Places the Pixelfly source and header under the Source Files and Header Files groups in Solution Explorer.

- `forms2.sln`
  - Added Debug and Release x64 solution configurations.
  - Maps Any CPU and Mixed Platforms to x64 so Visual Studio does not silently build the incompatible Win32 target for Pixelfly.

### Environment discovered

- `pco.camware` 4.21.1
- `pco.usb2 driver` 2.4.0
- `pco.cpp` 1.7.0
- Visual Studio Community 2026, version 18.9.2
- PCO SDK location: `C:\Program Files\PCO Digital Camera Toolbox\pco.cpp`

### Validation

- Built `Debug|x64` successfully with Visual Studio/MSBuild.
- Built the `Debug|Mixed Platforms` solution configuration successfully after mapping it to x64.
- Confirmed that the output contains `forms2.exe`, `sc2_cam.dll`, and the required managed assemblies.
- Passed a startup smoke test.
- Confirmed in the running form that `pco.pixelfly 1.4 USB` appears and can be selected.
- Confirmed with the physical camera that one-image acquisition works through Simplicio.

### Not changed as part of this work

- The old `PixelFly SDK` directory was not deleted.
- Four-exposure acquisition and preview-formula behavior were not implemented.
- The pre-existing deletion of `app.aps` was not made by this work.
- The pre-existing untracked `RCa17348` item was not made or modified by this work.
- No commit or push was performed.

## 2026-09-02 — Prevent preview crashes during rapid input

All changes in this section remain uncommitted in the local `vs2026` checkout.

### Changed

- `ImageThread.h`, preview worker state
  - Changed the processing flag to an integer so the .NET `Interlocked` methods can reserve and release the worker atomically.
  - Added a per-image snapshot of the Single frame setting and separated the worker wrapper from preview rendering.

- `ImageThread.cpp`, `processImage`, `processNewImage`, and preview rendering
  - Prevents two image-preview threads from starting at the same time when acquisition controls are clicked rapidly.
  - Resets the processing state even when preview generation throws an exception, so one failure cannot leave previews permanently disabled.
  - Freezes the bin size, pixel size, and Single frame interpretation for each image before its worker starts.
  - Sizes preview bitmaps from the sampled dimensions and the requested preview pixel size.
  - Fills the complete preview pixel block instead of writing one scaled coordinate into a bitmap that could be too small. This removes the `IndexOutOfRangeException` previously reported in `ImageThread::processNewImage`.
  - Checks the layer count before using the four-layer Single frame preview calculation.

### Validation

- Compiled all Debug x64 sources successfully.
- The normal output could not be overwritten while the previously built `forms2.exe` was still running.
- Rebuilt and linked successfully to the separate local `x64\CodexValidation` output directory; the existing obsolete .NET security-attribute warning remains unrelated.
- Verified the preview-coordinate calculation for every allowed bin-size and pixel-size combination at representative full-frame dimensions; all 48 combinations remained within the allocated bitmap.
- A physical-camera button stress test remains to be run after stopping the old process and rebuilding the normal Debug x64 output.
- No commit or push was performed.

## 2026-09-02 — Prevent simultaneous acquisition threads and Pixelfly re-arm failure

All changes in this section remain uncommitted in the local `vs2026` checkout.

### Cause

- `CameraThread::acquire` checked the shared running flag before starting a worker but did not reserve that state until inside the worker. Rapid clicks could therefore start two acquisition threads.
- A second worker could call `PCO_ArmCamera` during the short interval after the first worker enabled camera recording but before the Pixelfly adapter updated its local recording flag. The SDK then correctly returned error `0x80031022`, "Arm is not possible while record active."

### Changed

- `CameraThread.h` and `CameraThread.cpp`
  - Changed the acquisition running flag to an integer so .NET `Interlocked` operations can reserve it atomically.
  - Reserves the running state before creating the acquisition worker, preventing a second rapid click from starting another worker.
  - Releases that state if worker startup fails and before notifying the form that acquisition has finished.
  - Uses the atomic running-state check when initializing or changing cameras.
  - Returns immediately after an image-buffer allocation failure instead of continuing with a null buffer.

- `PixelflyUsbDriver.cpp`, `stop`
  - Reads the camera's actual recording state with `PCO_GetRecordingState` rather than relying only on the adapter's local flag.
  - Requests immediate recording stop when the camera reports that recording is active, following the sequence used by the installed PCO C++ camera wrapper.

### Validation

- Rebuilt and linked the complete Debug x64 project successfully to the local `x64\CodexValidation` output directory.
- The existing obsolete .NET security-attribute warning remains unrelated.

## 2026-09-02 — Handle missing AIA save folders

All changes in this section remain uncommitted in the local `vs2026` checkout.

### Cause

- `settings.txt` contains the historical path `D:\Data\2012\2012-09`, which is not present on the current computer.
- `ImageData::saveFile` opened its output file before entering its exception-protected block, allowing `DirectoryNotFoundException` to terminate manual or automatic saving.
- The camera thread copied the form's designer path before `settings.txt` was loaded, so the displayed manual-save path and automatic-acquisition path could differ.

### Changed

- `Form1.cpp`, startup path initialization
  - Falls back to the current user's Documents folder when the configured directory does not exist.
  - Synchronizes the final displayed save path into `CameraThread` after reading `settings.txt`.

- `ImageData.cpp`, `saveFile`
  - Validates that the selected save directory exists before creating an AIA file.
  - Uses `Path::Combine` to construct the filename.
  - Protects file creation, writing, and cleanup with exception handling.
  - Leaves the image marked unsaved and displays an actionable message if the path is missing, inaccessible, or the write otherwise fails.

### Validation

- Rebuilt and linked the complete Debug x64 project successfully to the local `x64\CodexValidation` output directory.
- The existing obsolete .NET security-attribute warning remains unrelated.
- A manual AIA save to a user-selected folder remains to be tested in the normal Visual Studio run.
- No commit or push was performed.

## 2026-09-02 — Require save-folder selection for each run

All changes in this section remain uncommitted in the local `vs2026` checkout.

### Changed

- `Form1.h` and `Form1.cpp`, save destination state and controls
  - Removed the designer's historical absolute save path and replaced it with `Click to select save folder`.
  - Stores the selected directory separately from the label text and starts every application run with no save destination.
  - Stops loading a save destination from `settings.txt` and does not automatically substitute another hardcoded or default directory.
  - Opens the folder chooser when automatic saving is enabled without a selected path. Cancelling the chooser turns automatic saving back off.
  - Opens the folder chooser when `Save Image Data` is pressed without a selected path. Cancelling leaves the image unsaved.
  - Reuses the selected folder for later saves during the current application run and passes it to `CameraThread` for automatic acquisition saves.

- `settings.txt`
  - Removed the obsolete `D:\Data\2012\2012-09` value and documented that the folder is selected at runtime.

### Validation

- Confirmed that no active source or settings file contains the old `D:\Data` or `Documents and Settings` paths.
- Rebuilt and linked the complete Debug x64 project successfully to the local `x64\CodexValidation` output directory.
- The existing obsolete .NET security-attribute warning remains unrelated.
- The folder-selection and cancellation paths remain to be exercised interactively after rebuilding the normal Debug x64 output.
- No commit or push was performed.

## 2026-09-07 — Fork checkpoint

### Repository handling

- Prepared the reviewed Pixelfly integration, shared acquisition and preview fixes, AIA save-path changes, setup notes, and this changelog as one checkpoint for `shavedlobster/Simplicio` on branch `vs2026`.
- Excluded the unrelated local `app.aps` deletion, untracked `RCa17348`, and generated `x64` build output from the checkpoint.
- Kept the original `atsommer/Simplicio` repository unchanged.

### Validation

- Rebuilt and linked the complete Debug x64 project successfully from a clean clone of `shavedlobster/Simplicio` with the checkpoint files applied.
- The existing obsolete .NET security-attribute warning remains unrelated.

## 2026-09-07 — Link Camera Settings to the pco.pixelfly SDK

These changes were developed and physically validated in the local `vs2026` Visual Studio checkout before preparing the fork update.

### Explained structure

- The form's `Camera Settings` button calls `Form1::openCameraDialog`, which delegates to `CameraThread::openCameraDialog`, which then calls the active camera `Driver` implementation.
- The legacy Sensicam implementation receives a vendor-provided dialog from `OPEN_DIALOG_CAM`. The PCO SC2 SDK exposes setting functions but no equivalent drop-in dialog, so the Pixelfly adapter now constructs its own WinForms dialog and keeps all PCO calls inside `PixelflyUsbDriver`.

### Changed

- `CameraThread.cpp`, `openCameraDialog`
  - Rejects settings access while acquisition is running.
  - Requires the selected camera to be initialized before opening settings.

- `PixelflyUsbDriver.cpp`, `openCameraDialog`
  - Replaced the informational Camware message with a Pixelfly settings dialog.
  - Reads exposure, ROI, binning, current image size, dynamic bit depth, and camera-specific limits from the PCO SDK.
  - Allows exposure in milliseconds, horizontal and vertical binning, and all four ROI coordinates to be edited.
  - Shows whether each binning axis uses powers of two or linear steps, plus the reported ROI steps and minimum dimensions.
  - Validates basic binning and ROI limits before sending values to the camera.
  - Stops recording and releases the old transfer buffer before applying settings.
  - Applies exposure with `PCO_SetDelayExposureTime`, ROI with `PCO_SetROI`, and binning with `PCO_SetBinning`, then calls `PCO_ArmCamera` and refreshes the resulting image dimensions.
  - Attempts to restore the previous camera values if applying or arming the new configuration fails.
  - Leaves software-trigger selection under the existing acquisition path rather than exposing a setting that Simplicio would overwrite.

### Validation

- Rebuilt and linked the complete Debug x64 project successfully to the local `x64\CodexValidation` output directory.
- The first build identified and the final code corrected invalid chained assignments to managed NumericUpDown properties.
- The existing obsolete .NET security-attribute warning remains unrelated.
- User-reported physical-camera validation passed: the settings dialog opens, settings apply, and image acquisition continues to work with the Pixelfly.
- A physical-camera rapid-click test remains to be run after rebuilding the normal Debug x64 output.
- Prepared for a fork-only commit to `shavedlobster/Simplicio`; no change was made to `atsommer/Simplicio`.

## 2026-09-07 — Correct Pixelfly Centered-Region Selection

These changes are local to the `vs2026` Visual Studio checkout pending physical-camera validation and a later fork-only push.

### Finding

- Physical testing showed that arbitrary coordinates entered through `PCO_SetROI` returned to the camera's prior values when acquisition armed the camera.
- The pco.pixelfly 1.4 USB provides its documented `800 x 600` centered region as the PCO extended sensor format. Its standard sensor format is the full `1392 x 1040` area.
- Binning changes the number of output pixels but should preserve the field selected by the sensor format. Simplicio scales every captured array to its preview box, so output size alone did not identify the physical field being captured.

### Changed

- `PixelflyUsbDriver.cpp`, `openCameraDialog`
  - Replaced the four editable generic ROI-coordinate controls with a `Captured sensor area` selector.
  - Offers the camera-reported standard full-sensor format and, when available, the extended centered format.
  - Applies the selection using `PCO_SetSensorFormat` before applying binning and arming the camera.
  - Continues to display the ROI returned by the camera as read-only diagnostic information.
  - Rereads sensor format, ROI, binning, and output dimensions after arming.
  - Shows a confirmation containing the area, accepted binning, output dimensions, and camera-reported ROI.
  - Clarifies in the dialog that binning changes output resolution rather than the selected field of view.

### Validation pending

- Compiled `PixelflyUsbDriver.cpp` successfully as x64 C++/CLI against the installed PCO SDK and .NET Framework assemblies.
- A complete command-line MSBuild could not run in the Codex sandbox because Visual C++ `FileTracker` received an access-denied error before project compilation; build the complete solution in the already-open Visual Studio instance.
- Rebuild Debug x64 and confirm that `Centered region (800 x 600)` remains selected after an acquisition.
- At `1 x 1` binning, confirm centered output is `800 x 600`; at `2 x 2`, expect `400 x 300` while retaining the same centered field.

## 2026-09-07 — Fit and Center Image Previews

These changes are local to the `vs2026` Visual Studio checkout pending visual validation and a later fork-only push.

### Finding

- Simplicio created a preview bitmap from every captured pixel but drew it at display coordinate `(0, 0)` without scaling it to the black preview panel.
- Small previews therefore remained attached to the upper-left corner, while previews larger than the panel could be clipped.
- The placement affected only the screen preview. It did not discard or alter pixels stored in `ImageData` or AIA files.

### Changed

- `ImageThread.cpp`, `renderImage`
  - Calculates a uniform fit scale from the captured image and the available preview-panel dimensions.
  - Preserves the captured image's aspect ratio.
  - Centers the image and its information area horizontally and vertically within the black panel.
  - Reserves enough vertical space for the timestamp, value information, and any sequence variables.
  - Clears each preview buffer to black before drawing the fitted image.
  - Positions the information box against the fitted image rather than its former unscaled coordinates.

### Validation pending

- Compiled the changed `ImageThread.cpp` successfully as x64 C++/CLI against the project's assemblies.
- Rebuild Debug x64 and compare full `1392 x 1040`, centered `800 x 600`, and binned captures.
- Confirm each complete frame is visible, centered, and undistorted, and that the timestamp/value box remains within the panel.

## 2026-10-05 — Add a Python AIA reader and four-dimensional series loader

These changes are local to the `shavedlobster/Simplicio` fork checkout. The existing C++ AIA writer was not changed.

### Reference validation

- Inspected the supplied Sommer Lab `AnalysisCodeNew` package and its Git history.
- Confirmed that its expected raw-image array order is `(iteration, picture, row, column)`.
- Confirmed that its four-frame burn-in mode interprets the frames as burn-in/reference, probe with atoms, probe without atoms, and dark/background.
- Confirmed that the analysis package did not previously contain an AIA reader.
- Parsed the supplied Pixelfly file `2026-09-02-16;07;48.aia` as a valid three-exposure, `1040 x 1392`, unsigned 16-bit image set with no trailing sequence-variable metadata.

### Added

- `AIAReader.py`
  - Validates the AIA signature, pixel width, dimensions, and payload length.
  - Reads one AIA file into a NumPy array ordered `(exposure, row, column)`.
  - Decodes optional sequence-variable metadata written after the pixel payload.
  - Sorts and stacks a file or folder into `(set, exposure, row, column)`.
  - Requires four exposures by default while allowing legacy exposure counts explicitly.
  - Provides a command-line option to validate a series and save it as `.npy`.

- `AIA_PYTHON_README.md`
  - Documents dimensions, four-frame interpretations, the binary layout, Python examples, and command-line use.

- `tests/test_aia_reader.py`
  - Verifies pixel ordering, metadata decoding, deterministic set ordering, legacy three-frame loading, four-frame validation, and truncated-file rejection using synthetic AIA fixtures.

### Remaining hardware validation

- Capture and load a real four-exposure Pixelfly AIA file. The supplied real file contains three exposures, so four-exposure behavior is covered by the byte-level test fixture but not yet by a physical-camera file.

## 2026-10-14 — Validate AIA integration against the live analysis repository

These changes are local to the `shavedlobster/Simplicio` fork checkout. No C++ acquisition or file-writing code was changed.

### Reference validation

- Fetched the current `main` branch of `insommer/AnalysisCodeNew` and checked commit `074594a58901286af7bd7c40b9505b70aca5935d` from October 8, 2026. The supplied ZIP was six commits behind that version.
- Confirmed that `LoadSpooledSeriesV2()` and the downstream analysis functions use the raw-image order `(iteration, picture, row, column)`, matching `load_aia_series()` output `(set, exposure, row, column)`.
- Confirmed the live `absImagingSimpleV2()` four-frame formulas: burn-in mode uses `(frame 1 - frame 0) / (frame 2 - frame 3)`, while skip-first mode discards frame 0 and applies the normal three-frame calculation to frames 1 through 3.
- Ran a synthetic four-exposure AIA series from `AIAReader.py` through the exact live `absImagingSimpleV2()` function. Both four-frame paths produced the expected optical density.
- Confirmed that the live repository contains no AIA reader and that `PreprocessBinImgs()` currently recognizes only Zyla `.dat` and Chameleon `.pgm` input. `Analyze_Atom_Pictures.py` therefore cannot select or load Pixelfly AIA data without an additional integration change.

### Changed

- `AIA_PYTHON_README.md`
  - Documented the current direct integration path from `load_aia_series()` to `absImagingSimpleV2()`.
  - Documented why the existing `PreprocessBinImgs()` and `Analyze_Atom_Pictures.py` paths do not yet accept Pixelfly AIA files.
  - Recorded the live analysis commit and compatibility result.

- `.gitignore`
  - Ignores Python bytecode and `__pycache__` directories generated while running the AIA reader tests.

### Remaining validation

- Capture a real four-exposure Pixelfly AIA set and run it through the complete analysis workflow.
- Add a Pixelfly/AIA branch to the analysis repository if Pixelfly should be selectable from `Analyze_Atom_Pictures.py` rather than loaded directly in Python.

## 2026-10-26 — Integrate automatic Python analysis into Simplicio

These changes are local to the `shavedlobster/Simplicio` fork checkout on the
`vs2026` branch. They have not been pushed.

### User-visible behavior

- Added an `Analyze saved images` checkbox to the Image Preview box.
- Added an `Analysis Setup` dialog for choosing the lab computer's Python
  executable, `AnalysisCodeNew/Applications/Analyze_Pixelfly_AIA.py`, imaging
  axis, camera binning, and optional analysis ROI.
- Added a status line showing whether analysis is off, waiting, queued,
  running, complete, or failed.
- Settings persist per Windows user in
  `%APPDATA%/Simplicio/pixelfly-analysis.settings`.

### Acquisition and analysis flow

- `ImageData` now records the final path of a successfully saved AIA file.
- Both automatic acquisition saves and the manual `Save Image Data` action
  enqueue that completed path when automatic analysis is enabled.
- A single background worker launches the configured Python analysis process,
  keeping the Windows Forms interface responsive and processing captures in
  order rather than launching competing fits.
- Each capture writes `<timestamp>_analysis.csv` and
  `<timestamp>_preview.png` into an `analysis` subfolder beside the AIA file.
- Analysis errors do not stop acquisition. Process-launch exceptions are
  written to a per-capture `_analysis_error.txt` file and shown in the status
  line.
- Python standard-error output is captured into that error file when the
  analyzer exits unsuccessfully, so failures remain diagnosable without a
  console window on the lab computer.
- Closing Simplicio stops its background analysis worker and terminates an
  active child analysis process.

### External dependency

- The lab computer must have Python and the local AnalysisCodeNew checkout
  containing the Pixelfly AIA analysis changes. Simplicio stores those paths
  through the setup dialog; no developer-machine path is compiled into the
  application.

### Documentation and validation

- Added `AUTO_ANALYSIS_SETUP.md` with lab-computer installation,
  configuration, and output instructions.
- Built the complete Simplicio solution successfully as `Release|x64` using
  Visual Studio 18 MSBuild. The existing Debug executable was open, so its
  linker could not replace that running file; C++ compilation completed
  before that Debug-only linker failure.
- Ran the exact Python command Simplicio launches against
  `C:\New folder\2026-10-26-12;27;55.aia`; it produced both a fitted CSV and a
  non-interactive PNG preview successfully.
- Physical validation on the lab computer remains necessary to confirm the
  chosen imaging axis, binning, ROI, and Pixelfly optical calibration.

## 2026-10-26 — Show the latest analysis preview inside Simplicio

These changes are local to the `shavedlobster/Simplicio` fork checkout on the
`vs2026` branch. They have not been pushed.

### Changed

- Simplicio opens a non-modal `Simplicio Analysis Preview` window when Python
  finishes analyzing the first saved AIA capture.
- The window displays the generated preview PNG with aspect-ratio-preserving
  zoom and shows its full path along the bottom.
- Later captures update the existing window instead of opening additional
  windows. If the user closes it, the next successful capture reopens it.
- Image files are copied into memory before display, so the preview does not
  remain locked on disk and can be replaced or deleted normally.
- The preview window is owned by the main Simplicio form and does not block
  camera controls or acquisition.

### Validation

- Built the complete Simplicio solution successfully as `Release|x64` with
  Visual Studio 18 MSBuild after adding the preview window.

## 2026-10-26 — Include the Pixelfly Python analyzer in the fork

These changes are in the `shavedlobster/Simplicio` fork checkout on the
`vs2026` branch.

### Changed

- Added a self-contained `AnalysisCodeNew` folder to the Simplicio repository
  so a lab-computer checkout contains the analyzer selected by Analysis Setup.
- Included `Applications/Analyze_Pixelfly_AIA.py` and the required
  `ImageAnalysis` modules for reading four-exposure AIA files, calculating
  optical density, fitting the image, writing CSV results, and creating the
  PNG preview.
- Included `requirements-pixelfly.txt` and `Setup_Pixelfly_Analysis.ps1` for
  installing the analyzer's Python packages on the lab computer.
- Updated `AUTO_ANALYSIS_SETUP.md` to use the analyzer bundled with the
  Simplicio checkout.

### Validation

- Ran the bundled analyzer against the four-exposure physical Pixelfly file
  `2026-10-26-12;27;55.aia`; it read all four `1040 x 1392` frames and wrote
  both the fitted CSV and PNG preview successfully.

## 2026-10-15 — Validate a physical four-exposure Pixelfly AIA file

This was a validation-only step. No C++ acquisition or AIA-writing code was changed.

### Validation

- Parsed the physical-camera file `2026-10-15-10;59;55.aia` with `AIAReader.py`.
- Confirmed an array shape of `(4, 1040, 1392)` with unsigned 16-bit pixels.
- Confirmed that the file size exactly equals the 11-byte AIA header plus four complete full-resolution image payloads, with no truncation or unexpected trailing bytes.
- Confirmed that this manually triggered acquisition contains no sequence-variable metadata, which is expected because the current writer only appends list-driven variables received from Cicero.
- This completes physical validation that Simplicio can save four Pixelfly exposures in one AIA file.

### Remaining validation

- Capture a controlled four-frame sequence with deliberately different image states to verify the physical meaning and order of frames 0 through 3.
- Run a real four-exposure series through the complete Sommer Lab optical-density analysis workflow.
