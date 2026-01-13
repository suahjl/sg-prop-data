# SRX Price Index Scraper

Automates the extraction of time series data from the [SRX Price Index](https://www.srx.com.sg/price-index) website. Scrapes property price index data for Singapore's private and HDB residential markets.

## Features

- **Comprehensive data extraction**: Scrapes all combinations of:
  - Property Types: Private Non-Landed, Private Landed, HDB
  - Sale Types: All Sale, Resale
  - Market Segments: All, Core Central, Rest of Central, Outside Central
- **Handles pagination**: Extracts complete historical data across multiple pages
- **Date processing**: Converts dates to `mmm-yyyy` format (e.g., `jan-1995`) and sorts ascending (oldest first)
- **Dual output format**: 
  - Individual `.txt` files (CSV format, for Notepad++ compatibility)
  - Bundled `.zip` archive with `.csv` extensions

## Getting Started

### Prerequisites

- Python 3.10+
- Google Chrome browser (for Selenium WebDriver)

### Clone the Repository

```bash
git clone https://github.com/suahjl/sg-prop-data.git
cd sg-prop-data
```

### Option A: Using Virtual Environment (Recommended)

1. **Create a virtual environment:**

   ```bash
   # Windows
   python -m venv .venv
   
   # macOS/Linux
   python3 -m venv .venv
   ```

2. **Activate the virtual environment:**

   ```bash
   # Windows (PowerShell)
   .\.venv\Scripts\Activate.ps1
   
   # Windows (Command Prompt)
   .\.venv\Scripts\activate.bat
   
   # macOS/Linux
   source .venv/bin/activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

### Option B: Using Global Python Environment

If you prefer not to use a virtual environment:

```bash
pip install -r requirements.txt
```

> **Note:** Using a virtual environment is recommended to avoid package conflicts with other projects.

## Usage

### Run the Scraper

```bash
python scrape_srx_price_index.py
```

For debugging (saves page source and screenshots to `debug/`):

```bash
python scrape_srx_price_index.py --debug
```

The scraper will:
1. Open a Chrome browser window
2. Navigate to the SRX Price Index page
3. Iterate through all 24 combinations (3 property types × 2 sale types × 4 market segments)
4. Extract all data with pagination handling
5. Process dates (sort ascending, format as `mmm-yyyy`)
6. Save files to `output/` directory
7. Create a zip archive with `.csv` files

### Process Existing Files (Ad-hoc)

If you need to re-process existing `.txt` files (e.g., reformat dates, recreate zip):

```bash
python process_and_zip.py
```

This will:
- Convert dates to `mmm-yyyy` format
- Sort data ascending (oldest observation first)
- Recreate the zip archive

## Output

Files are saved in the `output/` directory:

```
output/
├── srx_price_index_private_non-landed_all_sale_all.txt
├── srx_price_index_private_non-landed_all_sale_core_central.txt
├── srx_price_index_private_non-landed_all_sale_rest_of_central.txt
├── ... (24 files total)
└── srx_price_index.zip
    ├── srx_price_index_private_non-landed_all_sale_all.csv
    └── ... (same files with .csv extension)
```

### File Format

Each file contains:
- **Date**: Month-year in `mmm-yyyy` format (e.g., `jan-1995`)
- **Value**: Price index value
- **% Change**: Month-on-month percentage change

Data is sorted ascending (oldest observation first).

## Project Structure

```
sg-prop-data/
├── scrape_srx_price_index.py   # Main scraper script
├── process_and_zip.py          # Ad-hoc processing utility
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── LICENSE                     # MIT License
├── .gitignore                  # Git ignore rules
└── output/                     # Scraped data (git-ignored)
```

## Troubleshooting

### Chrome browser not found

Make sure Google Chrome is installed on your system. The script uses Selenium with Chrome WebDriver, which is automatically managed by `webdriver-manager`.

### Website structure changed

If the scraper fails to find dropdowns or data:
1. Run with `--debug` flag to save page source for inspection
2. Check the dropdown IDs in the HTML (currently uses `table-property-type`, `table-sale-resale`, `table-market-segments`)
3. Update the `find_dropdowns()` method in `scrape_srx_price_index.py` if needed

### Slow page loading

Increase the `delay` parameter when initializing the scraper:

```python
scraper = SRXPriceIndexScraper(delay=3)  # Default is 2 seconds
```

### Rate limiting

If you encounter blocks or errors, add longer delays between requests by increasing the `delay` parameter.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This tool is for educational and research purposes. Please respect the website's terms of service and use responsibly. The scraped data is sourced from SRX and remains their intellectual property.
