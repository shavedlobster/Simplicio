# pco.pixelfly 1.4 USB: first-capture setup

## Scope of this milestone

This version adds the camera to Simplicio's **Camera Type** list and implements one-frame acquisition through the installed PCO SDK. It does not yet add exposure controls, external triggering, four-frame acquisition, or preview formulas.

## Installed software used by this build

The development computer was found to have:

- pco.camware 4.21.1
- pco.usb2 driver 2.4.0
- pco.cpp 1.7.0

The default SDK directory is:

`C:\Program Files\PCO Digital Camera Toolbox\pco.cpp`

Set the `PCO_SDK_DIR` environment variable before opening Visual Studio if the SDK is installed elsewhere. It must point to the directory containing the `include`, `lib`, and `bin` folders.

## What the relevant files do

- `Form1.h` creates the Windows Form controls. `cameraListBox` is the visible Camera Type box.
- `Form1.cpp` receives selection and button events from the form.
- `CameraThread.cpp` selects a `Driver`, runs acquisition on a worker thread, and passes completed pixels to `ImageData`.
- `Driver.h` is the common interface implemented by every camera adapter.
- `PixelflyUsbDriver.h` declares the Pixelfly adapter and its camera/buffer state.
- `PixelflyUsbDriver.cpp` translates Simplicio operations into PCO SDK calls.
- `ImageData.cpp` owns the captured 16-bit pixels and saves the existing AIA file format.
- `ImageThread.cpp` creates the displayed preview from `ImageData`.
- `forms2.vcxproj` tells Visual Studio which sources, headers, SDK paths, libraries, and build architecture to use.
- `forms2.sln` is the solution opened in Visual Studio.

## Build in Visual Studio

1. Open `forms2.sln`.
2. In the toolbar select **Debug** and **x64**.
3. Choose **Build > Build Solution**.
4. The executable is written to `x64\Debug\forms2.exe`.

The current PCO SDK is 64-bit. The old bundled Sensicam and Princeton/WinView libraries are 32-bit, so those legacy adapters are excluded from the x64 build. Use the x64 build for the Pixelfly.

## First camera test

1. Connect and power the camera.
2. Open pco.camware and confirm that Live Preview works.
3. Stop acquisition and fully close pco.camware so it releases the camera.
4. Start `x64\Debug\forms2.exe`.
5. Select **pco.pixelfly 1.4 USB** in **Camera Type**. Successful selection opens camera index 0 and verifies its PCO camera type.
6. Leave the number of layers at 1 and click **Acquire**.
7. Simplicio arms the camera in software-trigger mode, queues one SDK image buffer, triggers one exposure, waits for transfer, copies the image as 16-bit pixels, and displays it through the existing image pipeline.

If selection fails, the adapter shows the PCO SDK error number and description. If it reports that camera 0 is a different PCO type, another PCO camera was opened first.

## First-acquisition call sequence

`PCO_OpenCamera` → camera type/description queries → `PCO_SetTriggerMode` → `PCO_SetAcquireMode` → `PCO_ArmCamera` → `PCO_GetSizes` → `PCO_AllocateBuffer` → `PCO_SetImageParameters` → `PCO_SetRecordingState` → `PCO_AddBufferEx` → `PCO_ForceTrigger` → wait/check buffer → copy pixels → cancel/stop/free/close

The adapter does not reset the camera to defaults. For this milestone it uses settings already present in the camera and changes trigger/acquire state only when arming.
