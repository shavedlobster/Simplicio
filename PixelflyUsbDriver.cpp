#include "stdafx.h"
#include "PixelflyUsbDriver.h"

#include "pco_err.h"
#include "sc2_common.h"
#include "sc2_sdkstructures.h"
#include "sc2_sdkaddendum.h"
#include "sc2_camexport.h"
#include "sc2_defs.h"

#include <cstring>

namespace forms2 {
	using namespace System;
	using namespace System::Windows::Forms;

	PixelflyUsbDriver::PixelflyUsbDriver()
		: camera(NULL), bufferEvent(NULL), bufferNumber(-1), cameraBuffer(NULL),
		  imageWidth(0), imageHeight(0), bitResolution(16), bufferBytes(0),
		  lastError(PCO_NOERROR), framePending(false), recording(false) {
		roix1 = roiy1 = 1;
		roix2 = roiy2 = 0;
		hbin = vbin = 1;
	}

	PixelflyUsbDriver::~PixelflyUsbDriver() {
		this->!PixelflyUsbDriver();
	}

	PixelflyUsbDriver::!PixelflyUsbDriver() {
		closeCamera();
	}

	void PixelflyUsbDriver::showSdkError(String^ operation, int errorCode) {
		char errorText[256] = { 0 };
		PCO_GetErrorTextSDK((DWORD)errorCode, errorText, sizeof(errorText));
		MessageBox::Show(
			String::Format("{0} failed.\r\n\r\nPCO error 0x{1:X8}: {2}",
				operation, errorCode, gcnew String(errorText)),
			"pco.pixelfly 1.4 USB", MessageBoxButtons::OK, MessageBoxIcon::Error);
	}

	int PixelflyUsbDriver::initCamera() {
		closeCamera();
		HANDLE openedCamera = NULL;
		lastError = PCO_OpenCamera(&openedCamera, 0);
		if (lastError != PCO_NOERROR) {
			camera = NULL;
			showSdkError("Opening camera 0", lastError);
			return NO_CAMERA;
		}
		camera = openedCamera;

		PCO_CameraType cameraType = {};
		cameraType.wSize = sizeof(cameraType);
		lastError = PCO_GetCameraType(camera, &cameraType);
		if (lastError != PCO_NOERROR) {
			showSdkError("Reading the camera type", lastError);
			closeCamera();
			return INIT_ERROR;
		}
		if (cameraType.wCamType != CAMERATYPE_PCO_USBPIXELFLY) {
			MessageBox::Show(
				String::Format("Camera 0 is PCO type 0x{0:X4}, not a pco.pixelfly USB camera.",
					cameraType.wCamType),
				"pco.pixelfly 1.4 USB", MessageBoxButtons::OK, MessageBoxIcon::Warning);
			closeCamera();
			return INIT_ERROR;
		}

		PCO_Description description = {};
		description.wSize = sizeof(description);
		lastError = PCO_GetCameraDescription(camera, &description);
		if (lastError != PCO_NOERROR) {
			showSdkError("Reading the camera description", lastError);
			closeCamera();
			return INIT_ERROR;
		}
		bitResolution = description.wDynResDESC;
		getSettings();
		return 0;
	}

	int PixelflyUsbDriver::openCameraDialog() {
		MessageBox::Show(
			"Camera settings are currently read from the camera. Use pco.camware to set and test exposure before opening Simplicio.",
			"pco.pixelfly 1.4 USB", MessageBoxButtons::OK, MessageBoxIcon::Information);
		return 0;
	}

	void PixelflyUsbDriver::lockCameraDialog(bool) {
		// This first-capture adapter does not embed the PCO settings dialog.
	}

	void PixelflyUsbDriver::releaseBuffer() {
		if (camera != NULL && bufferNumber >= 0) {
			PCO_FreeBuffer(camera, bufferNumber);
		}
		bufferNumber = -1;
		bufferEvent = NULL; // Owned and closed by SC2_Cam when the buffer is freed.
		cameraBuffer = NULL;
		bufferBytes = 0;
	}

	void PixelflyUsbDriver::closeCamera() {
		if (camera == NULL)
			return;
		stop();
		releaseBuffer();
		PCO_CloseCamera(camera);
		camera = NULL;
		imageWidth = imageHeight = 0;
		lastError = PCO_NOERROR;
	}

	int PixelflyUsbDriver::armCamera() {
		if (camera == NULL)
			return INIT_ERROR;

		stop();
		releaseBuffer();

		lastError = PCO_SetTriggerMode(camera, 0x0001); // Software trigger.
		if (lastError == PCO_NOERROR)
			lastError = PCO_SetAcquireMode(camera, 0x0000); // Ignore acquire-enable input.
		if (lastError == PCO_NOERROR)
			lastError = PCO_ArmCamera(camera);

		WORD actualWidth = 0;
		WORD actualHeight = 0;
		WORD maxWidth = 0;
		WORD maxHeight = 0;
		if (lastError == PCO_NOERROR)
			lastError = PCO_GetSizes(camera, &actualWidth, &actualHeight, &maxWidth, &maxHeight);
		if (lastError == PCO_NOERROR) {
			imageWidth = actualWidth;
			imageHeight = actualHeight;
		}

		DWORD warning = 0;
		DWORD error = 0;
		DWORD status = 0;
		if (lastError == PCO_NOERROR)
			lastError = PCO_GetCameraHealthStatus(camera, &warning, &error, &status);
		if (lastError == PCO_NOERROR && error != 0)
			lastError = (int)error;

		if (lastError != PCO_NOERROR) {
			showSdkError("Arming the camera", lastError);
			return INIT_ERROR;
		}

		bufferBytes = (DWORD)imageWidth * (DWORD)imageHeight * sizeof(WORD);
		SHORT allocatedBufferNumber = -1;
		HANDLE allocatedBufferEvent = NULL;
		WORD* allocatedCameraBuffer = NULL;
		lastError = PCO_AllocateBuffer(camera, &allocatedBufferNumber, bufferBytes,
			&allocatedCameraBuffer, &allocatedBufferEvent);
		if (lastError == PCO_NOERROR) {
			bufferNumber = allocatedBufferNumber;
			bufferEvent = allocatedBufferEvent;
			cameraBuffer = allocatedCameraBuffer;
		}
		if (lastError == PCO_NOERROR)
			lastError = PCO_SetImageParameters(camera, imageWidth, imageHeight,
				IMAGEPARAMETERS_READ_WHILE_RECORDING, NULL, 0);
		if (lastError == PCO_NOERROR)
			lastError = PCO_SetRecordingState(camera, 0x0001);

		if (lastError != PCO_NOERROR) {
			showSdkError("Preparing image transfer", lastError);
			stop();
			releaseBuffer();
			return INIT_ERROR;
		}

		recording = true;
		framePending = false;
		getSettings();
		return 0;
	}

	void PixelflyUsbDriver::expose() {
		if (!recording || framePending || cameraBuffer == NULL) {
			lastError = PCO_ERROR_APPLICATION;
			return;
		}

		ResetEvent(bufferEvent);
		lastError = PCO_AddBufferEx(camera, 0, 0, bufferNumber,
			imageWidth, imageHeight, 16);
		if (lastError != PCO_NOERROR)
			return;

		WORD triggered = 0;
		lastError = PCO_ForceTrigger(camera, &triggered);
		if (lastError == PCO_NOERROR && triggered == 0)
			lastError = PCO_ERROR_APPLICATION;
		framePending = (lastError == PCO_NOERROR);
	}

	int PixelflyUsbDriver::getImageStatus() {
		if (lastError != PCO_NOERROR)
			return IMAGE_ERROR;
		if (!framePending)
			return CAMERA_IDLE;

		DWORD waitResult = WaitForSingleObject(bufferEvent, 0);
		if (waitResult == WAIT_TIMEOUT)
			return CAMERA_BUSY;
		if (waitResult != WAIT_OBJECT_0) {
			lastError = PCO_ERROR_APPLICATION;
			return IMAGE_ERROR;
		}

		DWORD statusDll = 0;
		DWORD statusDriver = 0;
		lastError = PCO_GetBufferStatus(camera, bufferNumber, &statusDll, &statusDriver);
		if (lastError != PCO_NOERROR)
			return IMAGE_ERROR;
		if (statusDriver != PCO_NOERROR) {
			lastError = (int)statusDriver;
			return IMAGE_ERROR;
		}
		return CAMERA_IDLE;
	}

	int PixelflyUsbDriver::getImageWidth() {
		return imageWidth;
	}

	int PixelflyUsbDriver::getImageHeight() {
		return imageHeight;
	}

	void PixelflyUsbDriver::readImage(UInt16* buffer) {
		if (buffer == NULL || cameraBuffer == NULL || !framePending)
			return;
		std::memcpy(buffer, cameraBuffer, bufferBytes);
		framePending = false;
		ResetEvent(bufferEvent);
	}

	void PixelflyUsbDriver::stop() {
		if (camera == NULL)
			return;
		if (bufferNumber >= 0)
			PCO_CancelImages(camera);
		WORD recordingState = 0;
		int stateError = PCO_GetRecordingState(camera, &recordingState);
		if ((stateError == PCO_NOERROR && recordingState != 0) ||
			(stateError != PCO_NOERROR && recording))
			PCO_SetRecordingState(camera, 0x0000);
		recording = false;
		framePending = false;
	}

	int PixelflyUsbDriver::getRows() {
		getSettings();
		return imageHeight;
	}

	int PixelflyUsbDriver::getCols() {
		getSettings();
		return imageWidth;
	}

	bool PixelflyUsbDriver::isDouble() {
		return false;
	}

	void PixelflyUsbDriver::update() {
		getSettings();
	}

	void PixelflyUsbDriver::getSettings() {
		if (camera == NULL)
			return;

		WORD x0 = 1, y0 = 1, x1 = 0, y1 = 0;
		WORD horizontalBinning = 1, verticalBinning = 1;
		if (PCO_GetROI(camera, &x0, &y0, &x1, &y1) == PCO_NOERROR) {
			roix1 = x0;
			roiy1 = y0;
			roix2 = x1;
			roiy2 = y1;
		}
		if (PCO_GetBinning(camera, &horizontalBinning, &verticalBinning) == PCO_NOERROR) {
			hbin = horizontalBinning;
			vbin = verticalBinning;
		}
		WORD actualWidth = 0, actualHeight = 0, maxWidth = 0, maxHeight = 0;
		if (PCO_GetSizes(camera, &actualWidth, &actualHeight, &maxWidth, &maxHeight) == PCO_NOERROR) {
			imageWidth = actualWidth;
			imageHeight = actualHeight;
		}
	}
}
