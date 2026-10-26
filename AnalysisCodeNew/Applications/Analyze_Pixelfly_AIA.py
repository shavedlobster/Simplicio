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


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from ImageAnalysis import ImageAnalysisCode


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
                          show_raw=False):
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
        column_densities, dx=dx_microns, mode='both', yFitMode='single')
    results = ImageAnalysisCode.AnalyseFittingResults(
        fit_parameters, logTime=catalogue.index)
    results = results.join(catalogue)

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
