# SRX Price Index Scraper

This script automates the extraction of time series data from the SRX Price Index website (https://www.srx.com.sg/price-index).

## Features

- Automatically scrapes data for all combinations of:
  - Property Types: Private Non-Landed, Private Landed, HDB
  - Sale Types: All Sale, Resale
  - Market Segments: All, Core Central, Rest of Central, Outside Central
- Handles pagination to extract all historical data
- Saves data as CSV files with `.txt` extension (for Notepad++ compatibility)

## Setup

1. Activate your virtual environment:
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```

2. Install required packages:
   ```powershell
   pip install -r requirements.txt
   ```

## Usage

Run the scraper:
```powershell
python scrape_srx_price_index.py
```

For debugging (saves page source and screenshots):
```powershell
python scrape_srx_price_index.py --debug
```

The script will:
1. Open a Chrome browser window
2. Navigate to the SRX Price Index page
3. Iterate through all combinations of dropdown options
4. Extract all data (handling pagination)
5. Save each combination as a separate `.txt` file in the `output/` directory

**Note:** The script will process all 24 combinations (3 property types × 2 sale types × 4 market segments). This may take some time depending on the amount of data and your internet connection.

## Output

Files will be saved in the `output/` directory with naming format:
```
srx_price_index_{property_type}_{sale_type}_{market_segment}.txt
```

Example: `srx_price_index_private_non-landed_all_sale_all.txt`

## Notes

- The script uses Selenium with Chrome WebDriver
- ChromeDriver will be automatically downloaded and managed by `webdriver-manager`
- If the website structure changes, you may need to adjust the selectors in the script
- The script includes delays to avoid overwhelming the server

## Troubleshooting

If you encounter issues:

1. **Make sure Chrome browser is installed** - The script uses Chrome WebDriver

2. **Inspect the page structure** - If the scraper can't find the dropdowns or table, run:
   ```powershell
   python inspect_page_structure.py
   ```
   This will help identify the correct selectors for the website elements.

3. **Adjust selectors if needed** - If the website structure has changed, you may need to modify the `find_dropdowns()` method in `scrape_srx_price_index.py` to match the actual HTML structure.

4. **Use debug mode** - Run with `--debug` flag to save page sources and screenshots:
   ```powershell
   python scrape_srx_price_index.py --debug
   ```

5. **Increase delay** - If the page loads slowly, increase the `delay` parameter in the script (default is 2 seconds)

6. **Check for rate limiting** - If you get blocked, add longer delays between requests
