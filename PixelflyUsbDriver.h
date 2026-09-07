#ifndef PIXELFLY_USB_DRIVER
#define PIXELFLY_USB_DRIVER

#include "Driver.h"
#include <windows.h>

namespace forms2 {

	ref class PixelflyUsbDriver : Driver {
	public:
		PixelflyUsbDriver();
		~PixelflyUsbDriver();
		!PixelflyUsbDriver();

		virtual int initCamera() override;
		virtual int openCameraDialog() override;
		virtual void lockCameraDialog(bool lock) override;
		virtual void closeCamera() override;
		virtual void expose() override;
		virtual void stop() override;
		virtual int getImageStatus() override;
		virtual int getImageWidth() override;
		virtual int getImageHeight() override;
		virtual void readImage(System::UInt16* buffer) override;
		virtual int armCamera() override;
		virtual System::String^ getDriverName() override {
			return gcnew System::String("pco.pixelfly 1.4 USB");
		}

		virtual int getRows() override;
		virtual int getCols() override;
		virtual bool isDouble() override;
		virtual void update() override;

	protected:
		virtual void getSettings() override;

	private:
		HANDLE camera;
		HANDLE bufferEvent;
		SHORT bufferNumber;
		WORD* cameraBuffer;
		WORD imageWidth;
		WORD imageHeight;
		WORD bitResolution;
		DWORD bufferBytes;
		int lastError;
		bool framePending;
		bool recording;

		void releaseBuffer();
		void showSdkError(System::String^ operation, int errorCode);
	};
}

#endif
