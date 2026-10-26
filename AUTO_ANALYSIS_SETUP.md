# Pixelfly automatic analysis setup

Simplicio can queue each successfully saved AIA capture for Python analysis.
Acquisition and analysis run independently: a Python failure changes the
analysis status but does not stop the camera or Cicero sequence.

## Lab computer prerequisites

1. Build the `vs2026` Simplicio solution for `x64`.
2. Use the Pixelfly-enabled `AnalysisCodeNew` folder included in this
   Simplicio checkout.
3. Install its Python dependencies by running
   `AnalysisCodeNew\Setup_Pixelfly_Analysis.ps1`, or run:

   ```powershell
   python -m pip install -r AnalysisCodeNew\requirements-pixelfly.txt
   ```

## Configure Simplicio

1. Start Simplicio and select the AIA save folder.
2. Enable `Save`.
3. Click `Analysis Setup` in the Image Preview box.
4. Select the lab computer's `python.exe`.
5. Select
   `<Simplicio folder>\AnalysisCodeNew\Applications\Analyze_Pixelfly_AIA.py`.
6. Select the imaging axis and the same binning used by the camera.
7. Leave ROI blank to analyze the complete captured image, or enter
   `row start, row end, column start, column end`.
8. Click `Save`, then enable `Analyze saved images`.

The configuration is stored for the current Windows user in
`%APPDATA%\Simplicio\pixelfly-analysis.settings`.

## Output

For a capture such as `2026-10-26-12;27;55.aia`, Simplicio creates:

- `analysis\2026-10-26-12;27;55_analysis.csv`
- `analysis\2026-10-26-12;27;55_preview.png`

The status line reports queued, running, completed, and failed analyses. A
process-launch exception is also written beside the other outputs as
`*_analysis_error.txt`.
