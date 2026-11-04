## Recording instructions

> Run python script from PlatformIO Core CLI, found from Alien head -> Quick Access -> Miscellaneous
```
python tools/record_csv.py filenamehere.csv
```

## Plotting a CSV

Install Matplotlib if needed, then run the plotter:
```
python -m pip install matplotlib
python tools/plot_csv.py
```

By default, the plotter reads `handsanitizer1.csv` from the project folder.
To plot another CSV in that folder, change `CSV_FILE` in `tools/plot_csv.py`.
The five columns are labeled VOC, NH3, H2S, EtOH, and Odor, matching `src/main.cpp`.