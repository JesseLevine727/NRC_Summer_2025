# Using RamanIntegrator.exe

This guide is for internal use and explains how to run the standalone Windows executable built from this project.

## Running the Program

1. Download or copy the entire `RamanIntegrator.dist` directory to your Windows machine.
2. Inside that folder double-click **`RamanIntegrator.exe`**. Alternatively open a Command Prompt, navigate to the folder, and type:
   ```cmd
   RamanIntegrator.exe
   ```
3. The Raman Spectra Integrator window will open.

## Basic Workflow

1. **Select Files or Folders** – Browse for individual `.txt` or `.spc` spectra or choose a folder containing multiple spectra.
2. **Define Ranges** – Enter integration ranges as `start,end` pairs separated by semicolons (e.g. `100,200;300,350`).
3. **Specify Peaks** – Provide wavenumber positions separated by semicolons (e.g. `1580;1600`).
4. **(Optional) Add Formulas** – Advanced users can supply custom expressions under "Spectral Math" and "Peak Spectral Math" for ratios or other calculations.
5. **Run Analysis** – Click **Run Analysis** to integrate the spectra.
6. **Export Results** – Click **Export to Excel** to create an `.xlsx` file containing integration areas, peak intensities, ratios, and any formula results.

## What You Can Do

- Integrate Raman spectra over arbitrary ranges.
- Measure baseline-corrected peak intensities.
- Automatically generate ratios of ranges and peaks.
- Apply your own mathematical expressions to the data.
- Export everything to Excel for further analysis or plotting.
