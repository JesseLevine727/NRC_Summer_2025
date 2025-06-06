import itertools
import os
import io
from typing import List, Tuple, Dict, TypeAlias

_spectra_cache: Dict[str, Tuple[List['pd.DataFrame'], List[Tuple[float, float]]]] = {} # type: ignore
_figure_cache: Dict[str, "Figure"] = {} # type: ignore

Range: TypeAlias = Tuple[float, float]
SpectraResults: TypeAlias = Dict[str, Dict[Range, List[float]]]
PeakResults: TypeAlias = Dict[str, Dict[float, List[float]]]
FigureMap: TypeAlias = Dict[str, "Figure"] # type: ignore
Coordinate: TypeAlias = Tuple[float, float]
CoordinateMap: TypeAlias = Dict[str, List[Coordinate]]

def load_map_file(path: str) -> Tuple[List['pd.DataFrame'], List[Tuple[float, ...]]]: # type: ignore
    """
    Reads a multi‐spectrum map file where the first line is wavenumbers
    and subsequent rows contain N coordinate columns followed by intensity values.
    Supports 1-D, 2-D
    Returns:
      - spectra: List of DataFrames, one per pixel/spectrum.
      - coordinate_list: List of coordinate tuples (length N).
    """
    import numpy as np
    import pandas as pd
    # read header wavenumbers
    with open(path) as f:
        wavenumbers = np.fromstring(f.readline().strip(), sep=' ')
    # load remaining numeric data
    data = np.loadtxt(path, skiprows=1)
    # figure out how many leading columns are coordinates
    num_coords = data.shape[1] - wavenumbers.size

    coords_array = data[:, :num_coords]      # shape: (pixels, num_coords)
    inten_array  = data[:, num_coords:]      # shape: (pixels, n_wavenumbers)

    spectra: List[pd.DataFrame]        = []
    coordinate_list: List[Tuple[float, ...]] = []

    for i, row in enumerate(inten_array):
        df = pd.DataFrame({
            'wavenumber': wavenumbers,
            'intensity' : row
        })
        spectra.append(df)
        coordinate_list.append(tuple(float(c) for c in coords_array[i]))

    return spectra, coordinate_list




def read_spectra(path: str) -> Tuple[List['pd.DataFrame'], List[Coordinate]]: #type: ignore
    """
    Reads spectra from a file and returns both spectra and coordinates.
    Caches the raw spectra to avoid re-reading on subsequent calls.
    Returns (spectra_list, coordinates_list).
    For single spectrum files, coordinates will be empty list [].
    """
    import pandas as pd
    import spc
    # Check cache first
    if path in _spectra_cache:
        return _spectra_cache[path]

    extension = os.path.splitext(path)[1].lower()

    if extension == ".txt":
        first = open(path).readline().split()
        if len(first) > 2:
            spectra, coords = load_map_file(path)
        else:
            # single‐spectrum files
            df = pd.read_csv(path, sep=r"\s+", names=["wavenumber","intensity"])
            spectra, coords = [df], []

    elif extension == ".spc":
        spectra_file = spc.File(path)
        txt = spectra_file.data_txt()
        df = pd.read_csv(io.StringIO(txt), sep=r"\s+", names=["wavenumber", "intensity"])
        spectra, coords = [df], []
    else:
        spectra, coords = [], []

    # Store in cache
    _spectra_cache[path] = (spectra, coords)
    return spectra, coords

def compute_areas_and_figures(
    folder: str,
    ranges: List[Range],
    peaks: List[float] | None = None,
) -> Tuple[SpectraResults, PeakResults, FigureMap, CoordinateMap]:
    """Compute integration areas and peak intensities for all spectra in *folder*.

    ``ranges`` are integration regions expressed as ``(x_min, x_max)`` tuples.
    ``peaks`` is a list of wavenumber positions. For each position the nearest
    data point is selected and its baseline-corrected intensity is reported.
    """
    import numpy as np
    import matplotlib as mpl
    from matplotlib.figure import Figure
    from matplotlib import colormaps
    
    mpl.rcParams['figure.max_open_warning'] = 0

    cmap = colormaps['viridis']
    colors = cmap(np.linspace(0, 1, len(ranges)))
    color_map = dict(zip(ranges, colors))
    peak_map: Dict[float, tuple] = {}
    if peaks:
        peak_colors = cmap(np.linspace(0, 1, len(peaks)))
        peak_map = dict(zip(peaks, peak_colors))

    results: SpectraResults = {}
    peak_results: PeakResults = {}
    figs: FigureMap = {}
    coordinates: CoordinateMap = {}

    for fname in sorted(os.listdir(folder)):
        full_path = os.path.join(folder, fname)
        spectra, coords = read_spectra(full_path)
        if not spectra:
            continue

        coordinates[fname] = coords

        # Reuse or create a non-GUI Figure object
        if fname in _figure_cache:
            fig = _figure_cache[fname]
            ax = fig.axes[0] if fig.axes else fig.add_subplot(111)
            ax.clear()
        else:
            fig = Figure(figsize=(6, 4))    # <-- non-GUI Figure
            ax = fig.add_subplot(111)
            _figure_cache[fname] = fig

        # Stack x and Y as before
        x = spectra[0]['wavenumber'].to_numpy()
        Y = np.stack([df['intensity'].to_numpy() for df in spectra], axis=0)

        # background traces
        base_color = 'black' if Y.shape[0] == 1 else 'lightgray'
        for yi in Y:
            ax.plot(x, yi, color=base_color, alpha=0.6)

        file_areas: Dict[Range, List[float]] = {}
        file_peaks: Dict[float, List[float]] = {}
        for (xmin, xmax), color in color_map.items():
            mask = (x >= xmin) & (x <= xmax)
            xr = x[mask]
            if xr.size == 0:
                file_areas[(xmin, xmax)] = [0.0]*Y.shape[0]
                continue

            Yr = Y[:, mask]
            order = np.argsort(xr)       
            xr    = xr[order]            
            Yr    = Yr[:, order] 
            I0 = Yr[:, 0]
            I1 = Yr[:, -1]
            factor = (xr - xmin) / (xmax - xmin)
            baseline = I0[:, None] + (I1 - I0)[:, None] * factor[None, :]
            top = Yr - baseline
            areas = np.trapezoid(top, xr, axis=1)
            areas = np.maximum(areas, 0.0)
            file_areas[(xmin, xmax)] = areas.tolist()

            # shading
            for yi_row, bi_row in zip(Yr, baseline):
                ax.plot(xr, bi_row, '--', color=color, alpha=0.5)
                ax.fill_between(xr, bi_row, yi_row, where=(yi_row>bi_row), color=color, alpha=0.2)
                ax.fill_between(xr, bi_row, yi_row, where=(yi_row<bi_row), color=color, alpha=0.1)

        if peaks:
            for center, pcolor in peak_map.items():
                idx = int(np.abs(x - center).argmin())
                win = 3
                left = max(0, idx - win)
                right = min(len(x) - 1, idx + win)
                xr = x[left:right + 1]
                Yr = Y[:, left:right + 1]
                if xr.size == 0:
                    file_peaks[center] = [0.0] * Y.shape[0]
                    continue

                b0 = Yr[:, 0]
                b1 = Yr[:, -1]
                factor = (xr - xr[0]) / max(xr[-1] - xr[0], 1e-9)
                baseline = b0[:, None] + (b1 - b0)[:, None] * factor[None, :]
                diff = Yr - baseline
                max_idx = diff.argmax(axis=1)
                heights = diff[np.arange(diff.shape[0]), max_idx]
                file_peaks[center] = heights.tolist()
                ax.axvline(xr[max_idx[0]], color=pcolor, linestyle="--", alpha=0.7)

        ax.set(
            title=os.path.splitext(fname)[0],
            xlabel='Wavenumber (1/cm)',
            ylabel='Intensity (a.u.)'
        )

        results[fname] = file_areas
        if peaks:
            peak_results[fname] = file_peaks
        figs[fname] = fig

    return results, peak_results, figs, coordinates



def compute_areas_and_figures_on_file(
    path: str,
    ranges: List[Range],
    peaks: List[float] | None = None,
) -> Tuple[SpectraResults, PeakResults, FigureMap, CoordinateMap]:
    """Helper to compute areas and peaks for a single file."""
    folder = os.path.dirname(path)
    fname  = os.path.basename(path)
    # call the normal function on the folder
    all_results, all_peaks, all_figs, all_coords = compute_areas_and_figures(
        folder, ranges, peaks
    )
    return (
        {fname: all_results.get(fname, {})},
        {fname: all_peaks.get(fname, {})},
        {fname: all_figs.get(fname)},
        {fname: all_coords.get(fname, [])},
    )


# New helper to compute all pairwise ratios and their inverses
def pairwise_ratios(df: 'pd.DataFrame', value_cols: List[str]) -> 'pd.DataFrame': # type: ignore
    """
    Given a wide DataFrame and a list of numeric columns (ranges),
    add for each unique pair (c1, c2):
      - c1/c2
      - c2/c1
    Returns the DataFrame with new ratio columns appended.
    """
    import numpy as np
    
    for c1, c2 in itertools.combinations(value_cols, 2):
        # original ratio
        ratio_col = f"{c1}/{c2}"
        ratio = df[c1] / df[c2].replace({0: np.nan})
        df[ratio_col] = ratio.fillna(0.0).astype(float)

        # inverse ratio
        inv_col = f"{c2}/{c1}"
        inv_ratio = df[c2] / df[c1].replace({0: np.nan})
        df[inv_col] = inv_ratio.fillna(0.0).astype(float)
    return df


def evaluate_formulas(df: 'pd.DataFrame', formulas: List[str], column_order: List[str]) -> 'pd.DataFrame': # type: ignore
    """Evaluate arbitrary expressions referencing ranges by number.

    Parameters
    ----------
    df : DataFrame
        Input dataframe containing numeric columns.
    formulas : List[str]
        Expressions using integers starting at 1 to reference columns.
    column_order : List[str]
        Names of the numeric columns in positional order.

    Returns
    -------
    DataFrame
        A dataframe with the evaluated results for each formula.
    """
    import pandas as pd
    import re

    rename_map = {col: f"p{i+1}" for i, col in enumerate(column_order)}
    temp = df[column_order].rename(columns=rename_map)

    out = pd.DataFrame(index=df.index)
    for expr in formulas:
        norm = re.sub(r"\b(\d+)\b", lambda m: f"p{m.group(1)}", expr)
        try:
            out[expr] = temp.eval(norm)
        except Exception:
            out[expr] = float('nan')
    return out