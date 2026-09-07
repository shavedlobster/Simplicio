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
	using namespace System::Drawing;
	using namespace System::Windows::Forms;

	static void addSettingsRow(TableLayoutPanel^ table, int row, String^ name, Control^ control, String^ note) {
		Label^ nameLabel = gcnew Label();
		nameLabel->Text = name;
		nameLabel->AutoSize = true;
		nameLabel->Anchor = AnchorStyles::Left;
		table->Controls->Add(nameLabel, 0, row);
		table->Controls->Add(control, 1, row);
		Label^ noteLabel = gcnew Label();
		noteLabel->Text = note;
		noteLabel->AutoSize = true;
		noteLabel->Anchor = AnchorStyles::Left;
		table->Controls->Add(noteLabel, 2, row);
	}

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
		if (camera == NULL) {
			MessageBox::Show("Initialize the camera before opening its settings.",
				"pco.pixelfly 1.4 USB", MessageBoxButtons::OK, MessageBoxIcon::Warning);
			return INIT_ERROR;
		}

		WORD recordingState = 0;
		lastError = PCO_GetRecordingState(camera, &recordingState);
		if (lastError != PCO_NOERROR) {
			showSdkError("Reading recording state", lastError);
			return INIT_ERROR;
		}
		if (recordingState != 0) {
			MessageBox::Show("Stop image acquisition before changing camera settings.",
				"pco.pixelfly 1.4 USB", MessageBoxButtons::OK, MessageBoxIcon::Information);
			return INIT_ERROR;
		}

		PCO_Description description = {};
		description.wSize = sizeof(description);
		DWORD delay = 0;
		DWORD exposure = 0;
		WORD delayBase = 0;
		WORD exposureBase = 0;
		WORD sensorFormat = SENSORFORMAT_STANDARD;
		WORD x0 = 1, y0 = 1, x1 = 0, y1 = 0;
		WORD binH = 1, binV = 1;
		WORD actualWidth = 0, actualHeight = 0, maxWidth = 0, maxHeight = 0;

		lastError = PCO_GetCameraDescription(camera, &description);
		if (lastError == PCO_NOERROR)
			lastError = PCO_GetDelayExposureTime(camera, &delay, &exposure, &delayBase, &exposureBase);
		if (lastError == PCO_NOERROR)
			lastError = PCO_GetSensorFormat(camera, &sensorFormat);
		if (lastError == PCO_NOERROR)
			lastError = PCO_GetROI(camera, &x0, &y0, &x1, &y1);
		if (lastError == PCO_NOERROR)
			lastError = PCO_GetBinning(camera, &binH, &binV);
		if (lastError == PCO_NOERROR)
			lastError = PCO_GetSizes(camera, &actualWidth, &actualHeight, &maxWidth, &maxHeight);
		if (lastError != PCO_NOERROR) {
			showSdkError("Reading camera settings", lastError);
			return INIT_ERROR;
		}

		double exposureMs = exposureBase == 0 ? exposure / 1000000.0 :
			(exposureBase == 1 ? exposure / 1000.0 : (double)exposure);
		double minimumExposureMs = description.dwMinExposureDESC / 1000000.0;
		double maximumExposureMs = (double)description.dwMaxExposureDESC;
		if (maximumExposureMs < minimumExposureMs)
			maximumExposureMs = minimumExposureMs;

		Form^ dialog = gcnew Form();
		dialog->Text = "pco.pixelfly 1.4 USB Settings";
		dialog->FormBorderStyle = FormBorderStyle::FixedDialog;
		dialog->StartPosition = FormStartPosition::CenterParent;
		dialog->MinimizeBox = false;
		dialog->MaximizeBox = false;
		dialog->ShowInTaskbar = false;
		dialog->ClientSize = System::Drawing::Size(560, 350);

		TableLayoutPanel^ table = gcnew TableLayoutPanel();
		table->Dock = DockStyle::Fill;
		table->Padding = Padding(12);
		table->ColumnCount = 3;
		table->RowCount = 8;
		table->ColumnStyles->Add(gcnew ColumnStyle(SizeType::Absolute, 145));
		table->ColumnStyles->Add(gcnew ColumnStyle(SizeType::Absolute, 190));
		table->ColumnStyles->Add(gcnew ColumnStyle(SizeType::Percent, 100));

		NumericUpDown^ exposureBox = gcnew NumericUpDown();
		exposureBox->DecimalPlaces = 6;
		exposureBox->Minimum = Convert::ToDecimal(minimumExposureMs);
		exposureBox->Maximum = Convert::ToDecimal(maximumExposureMs);
		exposureBox->Increment = Convert::ToDecimal(0.001);
		exposureBox->Value = Convert::ToDecimal(Math::Min(Math::Max(exposureMs, minimumExposureMs), maximumExposureMs));
		exposureBox->Width = 130;

		ComboBox^ sensorFormatBox = gcnew ComboBox();
		sensorFormatBox->DropDownStyle = ComboBoxStyle::DropDownList;
		sensorFormatBox->Width = 180;
		sensorFormatBox->Items->Add(String::Format("Full sensor ({0} x {1})",
			description.wMaxHorzResStdDESC, description.wMaxVertResStdDESC));
		bool hasCenteredFormat = description.wMaxHorzResExtDESC > 0 && description.wMaxVertResExtDESC > 0;
		if (hasCenteredFormat)
			sensorFormatBox->Items->Add(String::Format("Centered region ({0} x {1})",
				description.wMaxHorzResExtDESC, description.wMaxVertResExtDESC));
		sensorFormatBox->SelectedIndex = hasCenteredFormat && sensorFormat == SENSORFORMAT_EXTENDED ? 1 : 0;

		NumericUpDown^ binHBox = gcnew NumericUpDown();
		binHBox->Minimum = 1;
		binHBox->Maximum = Math::Max((int)description.wMaxBinHorzDESC, 1);
		binHBox->Value = binH;
		NumericUpDown^ binVBox = gcnew NumericUpDown();
		binVBox->Minimum = 1;
		binVBox->Maximum = Math::Max((int)description.wMaxBinVertDESC, 1);
		binVBox->Value = binV;

		addSettingsRow(table, 0, "Exposure", exposureBox, "ms");
		addSettingsRow(table, 1, "Captured sensor area", sensorFormatBox,
			"Binning changes output resolution, not this field of view");
		addSettingsRow(table, 2, "Horizontal binning", binHBox,
			description.wBinHorzSteppingDESC == 0 ? "powers of two" : "linear values");
		addSettingsRow(table, 3, "Vertical binning", binVBox,
			description.wBinVertSteppingDESC == 0 ? "powers of two" : "linear values");
		addSettingsRow(table, 4, "Camera-reported ROI", gcnew Label(),
			String::Format("({0}, {1}) through ({2}, {3})", x0, y0, x1, y1));
		addSettingsRow(table, 5, "Current output size", gcnew Label(), String::Format("{0} x {1} pixels", actualWidth, actualHeight));
		addSettingsRow(table, 6, "Dynamic resolution", gcnew Label(), String::Format("{0} bit", description.wDynResDESC));

		Label^ instruction = gcnew Label();
		instruction->Text = "Apply selects the Pixelfly sensor format, then binning. The accepted area and output size are confirmed after the camera is armed.";
		instruction->AutoSize = true;
		instruction->MaximumSize = System::Drawing::Size(470, 0);
		table->Controls->Add(instruction, 0, 7);
		table->SetColumnSpan(instruction, 3);

		FlowLayoutPanel^ buttons = gcnew FlowLayoutPanel();
		buttons->FlowDirection = FlowDirection::RightToLeft;
		buttons->Dock = DockStyle::Bottom;
		buttons->Height = 48;
		buttons->Padding = Padding(8);
		Button^ cancelButton = gcnew Button();
		cancelButton->Text = "Cancel";
		cancelButton->DialogResult = System::Windows::Forms::DialogResult::Cancel;
		Button^ applyButton = gcnew Button();
		applyButton->Text = "Apply";
		applyButton->DialogResult = System::Windows::Forms::DialogResult::OK;
		buttons->Controls->Add(cancelButton);
		buttons->Controls->Add(applyButton);
		dialog->CancelButton = cancelButton;
		dialog->AcceptButton = applyButton;
		dialog->Controls->Add(table);
		dialog->Controls->Add(buttons);

		if (dialog->ShowDialog() != System::Windows::Forms::DialogResult::OK)
			return 0;

		WORD newBinH = Decimal::ToUInt16(binHBox->Value);
		WORD newBinV = Decimal::ToUInt16(binVBox->Value);
		bool validBinH = description.wBinHorzSteppingDESC != 0 || (newBinH & (newBinH - 1)) == 0;
		bool validBinV = description.wBinVertSteppingDESC != 0 || (newBinV & (newBinV - 1)) == 0;
		WORD newSensorFormat = sensorFormatBox->SelectedIndex == 1 ? SENSORFORMAT_EXTENDED : SENSORFORMAT_STANDARD;
		if (!validBinH || !validBinV) {
			MessageBox::Show("The selected binning is outside the limits reported by the camera.",
				"pco.pixelfly 1.4 USB", MessageBoxButtons::OK, MessageBoxIcon::Warning);
			return INIT_ERROR;
		}

		double newExposureMs = Decimal::ToDouble(exposureBox->Value);
		WORD originalSensorFormat = sensorFormat;
		WORD originalBinH = binH;
		WORD originalBinV = binV;
		WORD newExposureBase;
		DWORD newExposure;
		if (newExposureMs * 1000000.0 <= UInt32::MaxValue) {
			newExposureBase = 0;
			newExposure = (DWORD)Math::Max(1.0, Math::Round(newExposureMs * 1000000.0));
		}
		else if (newExposureMs * 1000.0 <= UInt32::MaxValue) {
			newExposureBase = 1;
			newExposure = (DWORD)Math::Max(1.0, Math::Round(newExposureMs * 1000.0));
		}
		else {
			newExposureBase = 2;
			newExposure = (DWORD)Math::Max(1.0, Math::Round(newExposureMs));
		}

		stop();
		releaseBuffer();
		lastError = PCO_SetDelayExposureTime(camera, delay, newExposure, delayBase, newExposureBase);
		if (lastError == PCO_NOERROR)
			lastError = PCO_SetSensorFormat(camera, newSensorFormat);
		if (lastError == PCO_NOERROR)
			lastError = PCO_SetBinning(camera, newBinH, newBinV);
		if (lastError == PCO_NOERROR)
			lastError = PCO_ArmCamera(camera);
		if (lastError == PCO_NOERROR)
			lastError = PCO_GetSizes(camera, &actualWidth, &actualHeight, &maxWidth, &maxHeight);
		if (lastError == PCO_NOERROR)
			lastError = PCO_GetROI(camera, &x0, &y0, &x1, &y1);
		if (lastError == PCO_NOERROR)
			lastError = PCO_GetBinning(camera, &binH, &binV);
		if (lastError == PCO_NOERROR)
			lastError = PCO_GetSensorFormat(camera, &sensorFormat);

		if (lastError != PCO_NOERROR) {
			int applyError = lastError;
			PCO_SetSensorFormat(camera, originalSensorFormat);
			PCO_SetBinning(camera, originalBinH, originalBinV);
			PCO_SetDelayExposureTime(camera, delay, exposure, delayBase, exposureBase);
			PCO_ArmCamera(camera);
			getSettings();
			showSdkError("Applying camera settings", applyError);
			return INIT_ERROR;
		}

		imageWidth = actualWidth;
		imageHeight = actualHeight;
		bitResolution = description.wDynResDESC;
		getSettings();
		String^ acceptedArea = sensorFormat == SENSORFORMAT_EXTENDED ?
			String::Format("Centered region ({0} x {1})", description.wMaxHorzResExtDESC, description.wMaxVertResExtDESC) :
			String::Format("Full sensor ({0} x {1})", description.wMaxHorzResStdDESC, description.wMaxVertResStdDESC);
		MessageBox::Show(
			String::Format("Camera accepted:\r\n\r\nArea: {0}\r\nBinning: {1} x {2}\r\nOutput: {3} x {4} pixels\r\nCamera ROI: ({5}, {6}) through ({7}, {8})",
				acceptedArea, binH, binV, actualWidth, actualHeight, x0, y0, x1, y1),
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
