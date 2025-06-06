# Raman Spectra Integrator

This project provides a Tkinter-based GUI for integrating Raman spectra.

## Usage

Run the application with:

```bash
python3 Raman_Integration/main.py
```

Select a folder or files containing `.txt` or `.spc` spectra, define integration ranges and peak positions, then export the results to Excel.

The output workbook includes:

- **Integration**: Areas for each defined range.
- **Peaks**: Baseline-subtracted and raw intensities for each peak.
- **Ratios**: Custom ratio calculations for integrated areas.
- **Peak Ratios**: Ratio calculations for peak intensities.
- **Spectral Math**: Additional user-defined formulas for integrated areas.
- **Peak Spectral Math**: User formulas applied to peak intensities.

## Requirements

Install dependencies with:

```bash
pip install -r requirements.txt
```

Python 3.10 or later is recommended.
