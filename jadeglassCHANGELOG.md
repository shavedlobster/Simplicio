# jadeglass change log

This file records changes made for the jadeglass Pixelfly adaptation of Simplicio.

## Repository policy

- Keep work local unless it is explicitly sent to the user's fork.
- Do not push changes to the upstream `atsommer/Simplicio` repository.
- Add an entry here for every repository change made from September 2, 2026 onward.
- Record the affected file locations, the purpose of the change, and the validation performed.
- Do not include unrelated pre-existing working-tree changes in commits or patches.

At initialization, the local checkout's `origin` remote points to `https://github.com/atsommer/Simplicio.git`. No fork remote is currently configured, so all changes listed below remain local.

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
