"""Analyze four-exposure Simplicio AIA files from the pco.pixelfly camera.

Exposure zero is the burn-in frame and is intentionally discarded. Exposures
one through three are the probe-with-atoms, probe-without-atoms, and dark
frames used by the existing Sommer Lab absorption-imaging analysis.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from ImageAnalysis import ImageAnalysisCode


def assess_absorption_capture(raw_images, catalogue, *, max_invalid_fraction=0.25,
                              max_saturated_fraction=0.01):
    """Return per-set capture diagnostics and reject unusable frame sets."""
    rows = []
    problems = []
    for index, raw in enumerate(raw_images):
        atoms_signal = raw[1].astype(np.float64) - raw[3].astype(np.float64)
        reference_signal = raw[2].astype(np.float64) - raw[3].astype(np.float64)
        invalid = (atoms_signal <= 0) | (reference_signal <= 0)

        bit_depth = 16
        if 'Simplicio.Camera.BitDepth' in catalogue.columns:
            reported = catalogue.iloc[index]['Simplicio.Camera.BitDepth']
            if np.isfinite(reported) and 1 <= reported <= 16:
                bit_depth = int(reported)
        saturation_level = (1 << bit_depth) - 1
        saturated = raw >= saturation_level

        invalid_fraction = float(np.mean(invalid))
        saturated_fraction = float(np.mean(saturated))
        reference_median = float(np.median(reference_signal))
        row = {
            'AtomsFrameMean': float(np.mean(raw[1])),
            'ReferenceFrameMean': float(np.mean(raw[2])),
            'DarkFrameMean': float(np.mean(raw[3])),
            'ReferenceMinusDarkMedian': reference_median,
            'InvalidPixelFraction': invalid_fraction,
            'SaturatedPixelFraction': saturated_fraction,
            'CaptureQuality': 'PASS',
        }

        set_problems = []
        if reference_median <= 0:
            set_problems.append('reference frame is not brighter than the dark frame')
        if invalid_fraction > max_invalid_fraction:
            set_problems.append(
                'invalid pixel fraction {:.1%} exceeds {:.1%}'.format(
                    invalid_fraction, max_invalid_fraction))
        if saturated_fraction > max_saturated_fraction:
            set_problems.append(
                'saturated pixel fraction {:.1%} exceeds {:.1%}'.format(
                    saturated_fraction, max_saturated_fraction))
        if set_problems:
            row['CaptureQuality'] = 'FAIL'
            problems.append('set {}: {}'.format(index, '; '.join(set_problems)))
        rows.append(row)

    quality = pd.DataFrame(rows, index=catalogue.index)
    if problems:
        raise ValueError(
            'Capture validation failed before fitting. Check Cicero trigger timing '
            'and the atoms/reference/dark frame order. ' + ' | '.join(problems))
    return quality


def _find_first_aia(paths: list[Path]) -> Path:
    for path in paths:
        if path.is_file() and path.suffix.lower() == '.aia':
            return path
        if path.is_dir():
            matches = sorted(path.glob('*.aia'))
            if matches:
                return matches[0]
    raise FileNotFoundError('No .aia files were found in the supplied paths.')


def _date_from_filename(path: Path) -> str:
    match = re.match(r'(\d{4})-(\d{2})-(\d{2})', path.name)
    if match is None:
        raise ValueError(
            'Could not determine the experiment date from {!s}; use --date.'
            .format(path))
    year, month, day = match.groups()
    return '{}/{}/{}'.format(int(month), int(day), year)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Analyze Simplicio Pixelfly AIA image sets.')
    parser.add_argument(
        'paths', nargs='+', type=Path,
        help='one or more .aia files or folders containing .aia files')
    parser.add_argument(
        '--date', help='experiment date as MM/DD/YYYY; inferred from the filename by default')
    parser.add_argument('--axis', choices=('side', 'top'), default='side')
    parser.add_argument(
        '--binning', type=int, default=1,
        help='equal horizontal and vertical camera binning (default: 1)')
    parser.add_argument(
        '--roi', type=int, nargs=4, metavar=('ROW_START', 'ROW_END', 'COL_START', 'COL_END'),
        help='optional Python-style ROI applied after optical-density calculation')
    parser.add_argument('--rotate', type=float, default=0.0, help='counterclockwise rotation in degrees')
    parser.add_argument('--exam-from', type=int, default=None)
    parser.add_argument('--exam-until', type=int, default=None)
    parser.add_argument('--show-raw', action='store_true')
    parser.add_argument('--show-od', action='store_true')
    parser.add_argument('--output', type=Path, help='optional CSV output path')
    parser.add_argument('--preview', type=Path,
                        help='optional PNG containing the four frames and optical density')
    return parser


def save_analysis_preview(path, raw_images, optical_density, *, title=None):
    """Write a non-interactive diagnostic image for one analyzed AIA set."""
    raw = raw_images[0]
    od = optical_density[0]
    labels = (
        '0 burn-in (discarded)',
        '1 atoms',
        '2 probe/reference',
        '3 dark/background',
    )
    figure, axes = plt.subplots(2, 3, figsize=(15, 9), constrained_layout=True)
    for frame, axis, label in zip(raw, axes.flat[:4], labels):
        low, high = np.percentile(frame, (1, 99.5))
        image = axis.imshow(frame, cmap='gray', origin='lower',
                            vmin=low, vmax=high)
        axis.set_title(label)
        figure.colorbar(image, ax=axis, shrink=0.75)

    od_low, od_high = np.percentile(od, (1, 99.5))
    image = axes[1, 1].imshow(
        od, cmap='magma', origin='lower', vmin=od_low, vmax=od_high)
    axes[1, 1].set_title('Optical density')
    figure.colorbar(image, ax=axes[1, 1], shrink=0.75)
    axes[1, 2].plot(np.sum(od, axis=0), label='column sum')
    axes[1, 2].plot(np.sum(od, axis=1), label='row sum')
    axes[1, 2].set_title('Optical-density profiles')
    axes[1, 2].legend()
    figure.suptitle(title or Path(path).stem)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=120)
    plt.close(figure)


def analyze_pixelfly_aia(paths, *, date=None, axis='side', binning=1,
                          roi=None, rotate=0.0, exam_range=(None, None),
                          show_raw=False, max_invalid_fraction=0.25):
    """Run the reusable Pixelfly preprocessing and fitting workflow.

    Returns ``(results, optical_density, raw_images)`` so interactive tools,
    the command-line application, and the live folder watcher all use the
    same implementation.
    """
    paths = [Path(path) for path in paths]
    first_file = _find_first_aia(paths)
    experiment_date = date or _date_from_filename(first_file)

    optical_density, catalogue, raw_images = ImageAnalysisCode.PreprocessAIAImgs(
        *paths,
        examRange=exam_range,
        rotateAngle=rotate,
        ROI=roi,
        showRawImgs=show_raw,
        returnRawImgs=True,
        expectedExposures=4,
    )

    quality = assess_absorption_capture(
        raw_images, catalogue, max_invalid_fraction=max_invalid_fraction)

    if ('Simplicio.Camera.HorizontalBinning' in catalogue.columns and
            'Simplicio.Camera.VerticalBinning' in catalogue.columns):
        horizontal = int(catalogue.iloc[0]['Simplicio.Camera.HorizontalBinning'])
        vertical = int(catalogue.iloc[0]['Simplicio.Camera.VerticalBinning'])
        if horizontal != vertical:
            raise ValueError(
                'The legacy analysis requires equal horizontal and vertical '
                'binning; the AIA metadata reports {} x {}.'.format(
                    horizontal, vertical))
        if horizontal != binning:
            print('Using captured camera binning {} instead of configured {}.'.format(
                horizontal, binning))
        binning = horizontal

    params = ImageAnalysisCode.ExperimentParams(
        date=experiment_date,
        picturesPerIteration=4,
        axis=axis,
        cam_type='pixelfly',
        binning=binning,
    )
    dx_microns = params.camera.pixelsize_microns / params.magnification
    column_densities = optical_density / params.cross_section

    fit_parameters, backgrounds = ImageAnalysisCode.FitColumnDensity(
        column_densities, dx=dx_microns, mode='both', yFitMode='single',
        subtract_bg=0, Xsignal_feature='wide', Ysignal_feature='wide')
    results = ImageAnalysisCode.AnalyseFittingResults(
        fit_parameters, logTime=catalogue.index)
    results = results.join(catalogue)
    results = results.join(quality)

    return results, optical_density, raw_images


def main() -> int:
    args = build_parser().parse_args()
    results, optical_density, raw_images = analyze_pixelfly_aia(
        args.paths,
        date=args.date,
        axis=args.axis,
        binning=args.binning,
        roi=args.roi,
        rotate=args.rotate,
        exam_range=(args.exam_from, args.exam_until),
        show_raw=args.show_raw,
    )

    print('Raw image shape:', raw_images.shape)
    print('Optical-density shape:', optical_density.shape)
    print(results)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        results.to_csv(args.output)
        print('Saved results to', args.output)

    if args.preview is not None:
        save_analysis_preview(
            args.preview, raw_images, optical_density,
            title=_find_first_aia(args.paths).stem)
        print('Saved preview to', args.preview)

    if args.show_od:
        plt.figure()
        plt.imshow(optical_density[0], cmap='gray')
        plt.title('Pixelfly optical density: first set')
        plt.colorbar(label='Optical density')
        plt.tight_layout()
        plt.show()

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
