# Raman Spectra Integrator

This repository contains a Python application for integrating and analyzing Raman spectra. The graphical user interface is built with [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) and is designed to work both for newcomers to Raman spectroscopy and those who routinely process spectra.

## Quick Start

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
   Python 3.10 or later is recommended.

2. **Run the application**
   ```bash
   python3 Raman_Integration/main.py
   ```
   A window will open allowing you to browse for `.txt` or `.spc` files or an entire folder of spectra.

3. **Define ranges and peaks**
   - *Ranges* are entered as `x_min,x_max;...` e.g. `100,200;300,350`.
   - *Peaks* are wavenumber positions separated by semicolons (e.g. `1580;1600`).
   - Optional expressions allow custom ratios or spectral math.

4. **Run analysis and export**
   - Click **Run Analysis** to integrate all selected spectra.
   - Click **Export to Excel** to create a workbook with integration results, peak intensities, and any custom formulas.

## Features for Experts

- Supports multi-spectra map files with coordinate information.
- Computes baseline-corrected and raw peak intensities.
- Automatic generation of ratios of selected ranges and peaks.
- User-defined formulas ("Spectral Math" and "Peak Spectral Math") evaluated on the fly.
- Uses Matplotlib for plotting; figures are cached to reduce overhead.

The exported workbook contains the following sheets:

- **Integration** – integrated area for each defined range.
- **Peaks** – baseline-subtracted intensities at specified positions.
- **Ratios** – pairwise ratios of integrated areas.
- **Peak Ratios** – ratios of peak intensities.
- **Spectral Math** – results from custom formulas on areas.
- **Peak Spectral Math** – formulas applied to peak intensities.

## Repository Layout

- `Raman_Integration/gui.py` – main GUI implementation.
- `Raman_Integration/math_utils.py` – functions for reading spectra and computing results.
- `Raman_Integration/main.py` – simple entry point that launches the GUI.
- `requirements.txt` – required Python packages.

## Contributing

Issues and pull requests are welcome. Feel free to submit bug reports or feature suggestions.


