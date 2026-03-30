"""
Script to scrape SRX Rent Index data from https://www.srx.com.sg/price-index
Uses the Rent toggle and 3 dropdowns: property type, property subtypes, market segments.
Handles pagination to extract all time series data.
"""

import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import os
import zipfile
import glob

# Try to import undetected-chromedriver for bypassing Cloudflare
try:
    import undetected_chromedriver as uc
    UC_AVAILABLE = True
except ImportError:
    UC_AVAILABLE = False


class SRXRentIndexScraper:
    def __init__(self, base_url="https://www.srx.com.sg/price-index", delay=2, debug=False):
        """
        Initialize the scraper.

        Args:
            base_url: URL of the SRX price index page (same page, Rent toggle)
            delay: Delay between actions in seconds
            debug: If True, save page source and screenshots for debugging
        """
        self.base_url = base_url
        self.debug = debug
        self.driver = None

        # Detect CI environment and increase delays
        self.is_ci = os.environ.get('CI', 'false').lower() == 'true'
        if self.is_ci:
            self.delay = max(delay, 4)
            self.debug = True
            print(f"  ℹ CI environment detected - delay set to {self.delay}s, debug mode enabled")
        else:
            self.delay = delay

        # Rent mode uses 3 dropdowns: property type, property subtypes, market segments
        self.property_types = [
            "Private Non-Landed",
            "Private Landed",
            "HDB"
        ]

        self.market_segments = [
            "All",
            "Core Central",
            "Rest of Central",
            "Outside Central"
        ]

        # Property subtypes vary by property type - discovered dynamically per combination

    def setup_driver(self):
        """Initialize Chrome WebDriver with appropriate options."""
        has_display = os.environ.get('DISPLAY') is not None

        if self.is_ci:
            if has_display:
                print(f"  ℹ CI with xvfb detected (DISPLAY={os.environ.get('DISPLAY')})")
                print("  ℹ Using undetected-chromedriver in non-headless mode")

                if UC_AVAILABLE:
                    options = uc.ChromeOptions()
                    options.add_argument('--no-sandbox')
                    options.add_argument('--disable-dev-shm-usage')
                    options.add_argument('--window-size=1920,1080')
                    self.driver = uc.Chrome(options=options, headless=False)
                    self.driver.implicitly_wait(15)
                else:
                    options = webdriver.ChromeOptions()
                    options.add_argument('--no-sandbox')
                    options.add_argument('--disable-dev-shm-usage')
                    options.add_argument('--window-size=1920,1080')
                    options.add_argument('--disable-blink-features=AutomationControlled')
                    service = Service(ChromeDriverManager().install())
                    self.driver = webdriver.Chrome(service=service, options=options)
                    self.driver.implicitly_wait(15)
            else:
                print("  ℹ CI without display - using headless mode")
                if UC_AVAILABLE:
                    options = uc.ChromeOptions()
                    options.add_argument('--no-sandbox')
                    options.add_argument('--disable-dev-shm-usage')
                    options.add_argument('--disable-gpu')
                    options.add_argument('--window-size=1920,1080')
                    options.add_argument('--headless=new')
                    self.driver = uc.Chrome(options=options, headless=True)
                    self.driver.implicitly_wait(15)
                else:
                    options = webdriver.ChromeOptions()
                    options.add_argument('--headless=new')
                    options.add_argument('--no-sandbox')
                    options.add_argument('--disable-dev-shm-usage')
                    options.add_argument('--disable-gpu')
                    options.add_argument('--window-size=1920,1080')
                    service = Service(ChromeDriverManager().install())
                    self.driver = webdriver.Chrome(service=service, options=options)
                    self.driver.implicitly_wait(10)
        else:
            options = webdriver.ChromeOptions()
            options.add_argument('--start-maximized')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.implicitly_wait(10)

    def close_driver(self):
        """Close the browser driver."""
        if self.driver:
            self.driver.quit()

    def wait_for_element(self, by, value, timeout=20):
        """Wait for an element to be present."""
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
        except TimeoutException:
            print(f"Timeout waiting for element: {by}={value}")
            return None

    def navigate_to_page(self):
        """Navigate to the SRX price index page."""
        print(f"  → Navigating to {self.base_url}...")
        self.driver.get(self.base_url)

        wait_time = self.delay * 3 if self.is_ci else self.delay * 2
        time.sleep(wait_time)

        # Dismiss cookie consent or popup
        try:
            consent_selectors = [
                "//button[contains(text(), 'Accept')]",
                "//button[contains(text(), 'OK')]",
                "//button[contains(text(), 'Got it')]",
                "//button[contains(@class, 'accept')]",
                "//a[contains(@class, 'close')]",
            ]
            for selector in consent_selectors:
                try:
                    btn = self.driver.find_element(By.XPATH, selector)
                    if btn.is_displayed():
                        btn.click()
                        print(f"  ℹ Dismissed popup/consent dialog")
                        time.sleep(1)
                        break
                except:
                    continue
        except:
            pass

        print(f"  ✓ Page loaded (title: {self.driver.title[:50]}...)" if len(self.driver.title) > 50 else f"  ✓ Page loaded (title: {self.driver.title})")

    def click_rent_toggle(self):
        """
        Click the Rent toggle to switch from Sale to Rent view.
        The toggle is typically above the property types dropdown (Sale | Rent tabs).
        """
        print(f"  → Clicking Rent toggle...")
        try:
            # Strategy 1: Find the tab/button group containing both Sale and Rent (index section)
            # The Rent toggle is usually a sibling of "Sale" in the same container
            try:
                sale_el = self.driver.find_element(By.XPATH, "//a[normalize-space(text())='Sale']")
                parent = sale_el.find_element(By.XPATH, "./..")
                rent_el = parent.find_element(By.XPATH, ".//a[normalize-space(text())='Rent']")
                if rent_el.is_displayed():
                    rent_el.click()
                    time.sleep(self.delay * 2)
                    print(f"  ✓ Rent toggle clicked")
                    return True
            except:
                pass

            # Strategy 2: Find Rent in same container as "Property Types" (table filters area)
            try:
                prop_label = self.driver.find_element(By.XPATH, "//*[contains(text(),'Property Types')]")
                container = prop_label.find_element(By.XPATH, "./ancestor::*[.//select][position()<8][1]")
                rent_el = container.find_element(By.XPATH, ".//a[contains(text(),'Rent')]")
                if rent_el.is_displayed():
                    rent_el.click()
                    time.sleep(self.delay * 2)
                    print(f"  ✓ Rent toggle clicked")
                    return True
            except:
                pass

            # Strategy 3: Click any visible Rent link that's NOT a property search link
            all_rent = self.driver.find_elements(By.XPATH, "//a[contains(text(),'Rent')]")
            for link in all_rent:
                try:
                    href = link.get_attribute('href') or ''
                    if 'search' in href or '/rent/' in href:
                        continue
                    if link.is_displayed() and link.is_enabled():
                        link.click()
                        time.sleep(self.delay * 2)
                        print(f"  ✓ Rent toggle clicked")
                        return True
                except:
                    continue

            # Strategy 4: Button or span with "Rent"
            for tag in ["button", "span", "div"]:
                try:
                    el = self.driver.find_element(By.XPATH, f"//{tag}[normalize-space(text())='Rent']")
                    if el.is_displayed():
                        el.click()
                        time.sleep(self.delay * 2)
                        print(f"  ✓ Rent toggle clicked")
                        return True
                except:
                    continue

            print(f"  ⚠ Could not find Rent toggle - page may already be in Rent mode or structure changed")
            return False
        except Exception as e:
            print(f"  ✗ Error clicking Rent toggle: {e}")
            return False

    def select_dropdown_option(self, dropdown_element, option_text):
        """Select an option from a dropdown."""
        try:
            select = Select(dropdown_element)
            select.select_by_visible_text(option_text)
            time.sleep(self.delay)
            return True
        except Exception as e:
            print(f"Error selecting option '{option_text}': {e}")
            return False

    def get_select_options(self, select_element):
        """Get all option texts from a select element (excluding empty/placeholder)."""
        try:
            select = Select(select_element)
            options = [opt.text.strip() for opt in select.options if opt.text.strip()]
            return options
        except:
            return []

    def extract_table_data(self):
        """Extract data from the current table view."""
        data = []
        try:
            table = self.wait_for_element(By.TAG_NAME, "table")
            if not table:
                table = self.driver.find_element(By.CSS_SELECTOR, "table")

            rows = table.find_elements(By.TAG_NAME, "tr")
            start_idx = 0
            if len(rows) > 0:
                first_row = rows[0]
                headers = [th.text.strip() for th in first_row.find_elements(By.TAG_NAME, "th")]
                if not headers:
                    headers = [td.text.strip() for td in first_row.find_elements(By.TAG_NAME, "td")]
                if headers and any(h for h in headers if h):
                    start_idx = 1

            for row in rows[start_idx:]:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 2:
                    row_data = [cell.text.strip() for cell in cells]
                    if any(row_data):
                        data.append(row_data)
        except Exception as e:
            print(f"Error extracting table data: {e}")
        return data

    def get_table_headers(self):
        """Get the table headers."""
        try:
            table = self.wait_for_element(By.TAG_NAME, "table")
            if table:
                header_row = table.find_element(By.TAG_NAME, "tr")
                headers = [th.text.strip() for th in header_row.find_elements(By.TAG_NAME, "th")]
                if not headers:
                    headers = [td.text.strip() for td in header_row.find_elements(By.TAG_NAME, "td")]
                return headers if headers else ["Date", "Index Value", "Change"]
        except:
            pass
        return ["Date", "Index Value", "Change"]

    def handle_pagination(self):
        """Handle pagination to get all pages of data."""
        all_data = []
        page_num = 1
        previous_page_data = None
        print(f"\n  → Extracting table data...")

        while True:
            page_data = self.extract_table_data()

            if previous_page_data is not None and page_data == previous_page_data:
                print(f"    📄 Page {page_num}: ⚠ Duplicate content detected - reached end of data")
                break

            if page_data:
                all_data.extend(page_data)
                print(f"    📄 Page {page_num}: ✓ Found {len(page_data)} rows (Total: {len(all_data)})")
                previous_page_data = page_data
            else:
                print(f"    📄 Page {page_num}: ⚠ No data found")
                break

            try:
                next_button = self.driver.find_element(By.ID, "pagination-next-button")
                if not next_button.is_displayed():
                    print(f"    ✓ Reached last page (Next button hidden)")
                    break
                classes = next_button.get_attribute('class') or ''
                style = next_button.get_attribute('style') or ''
                if 'disabled' in classes.lower() or 'display: none' in style.lower() or 'visibility: hidden' in style.lower():
                    print(f"    ✓ Reached last page (Next button disabled)")
                    break
                print(f"    → Clicking Next...", end=" ")
                next_button.click()
                time.sleep(self.delay)
                page_num += 1
                print("✓")
            except NoSuchElementException:
                print(f"    ✓ No more pages (Next button not found)")
                break
            except Exception as e:
                print(f"    ⚠ Pagination ended: {e}")
                break

        print(f"  ✓ Extraction complete: {len(all_data)} total rows from {page_num} page(s)")
        return all_data

    def find_rent_dropdowns(self):
        """
        Find the 3 dropdowns when Rent is selected:
        - table-property-type: Property types
        - table-property-subtypes (or similar): Property subtypes
        - table-market-segments: Market segments
        """
        dropdowns_dict = {}
        try:
            # Property type
            try:
                element = self.driver.find_element(By.ID, "table-property-type")
                dropdowns_dict['property'] = element
                print(f"    Found property dropdown: table-property-type")
            except:
                print(f"    ⚠ Could not find table-property-type")

            # Property subtypes - may use different ID when in Rent mode
            subtype_ids = ["table-property-subtypes", "table-property-subtype", "table-sale-resale"]
            for sid in subtype_ids:
                try:
                    element = self.driver.find_element(By.ID, sid)
                    dropdowns_dict['subtype'] = element
                    print(f"    Found subtype dropdown: {sid}")
                    break
                except:
                    continue
            if 'subtype' not in dropdowns_dict:
                print(f"    ⚠ Could not find property subtypes dropdown")

            # Market segments
            try:
                element = self.driver.find_element(By.ID, "table-market-segments")
                dropdowns_dict['market'] = element
                print(f"    Found market dropdown: table-market-segments")
            except:
                print(f"    ⚠ Could not find table-market-segments")

        except Exception as e:
            print(f"  ✗ Error finding dropdowns: {e}")

        return dropdowns_dict

    def scrape_combination(self, property_type, property_subtype, market_segment):
        """Scrape data for a specific combination of dropdown options."""
        print(f"\n{'='*80}")
        print(f"SERIES: {property_type} | {property_subtype} | {market_segment}")
        print(f"{'='*80}")

        self.navigate_to_page()
        self.click_rent_toggle()

        try:
            print(f"  → Finding dropdowns...")
            dropdowns = self.find_rent_dropdowns()

            if not dropdowns:
                print("  ⚠ Warning: Could not find dropdowns. Trying fallback...")
                all_selects = self.driver.find_elements(By.TAG_NAME, "select")
                if len(all_selects) >= 3:
                    dropdowns = {
                        'property': all_selects[0],
                        'subtype': all_selects[1],
                        'market': all_selects[2]
                    }
                    print(f"  ✓ Found {len(all_selects)} dropdown(s) using fallback")
                else:
                    print(f"  ✗ Error: Found only {len(all_selects)} dropdown(s), expected 3")
                    return pd.DataFrame()
            else:
                print(f"  ✓ Found {len(dropdowns)} dropdown(s)")

            print(f"  → Selecting dropdown options...")
            if 'property' in dropdowns:
                if self.select_dropdown_option(dropdowns['property'], property_type):
                    print(f"    ✓ Property Type: {property_type}")
                else:
                    print(f"    ✗ Warning: Could not select property type: {property_type}")
            time.sleep(self.delay)

            if 'subtype' in dropdowns:
                if self.select_dropdown_option(dropdowns['subtype'], property_subtype):
                    print(f"    ✓ Property Subtype: {property_subtype}")
                else:
                    print(f"    ✗ Warning: Could not select property subtype: {property_subtype}")
            time.sleep(self.delay)

            if 'market' in dropdowns:
                if self.select_dropdown_option(dropdowns['market'], market_segment):
                    print(f"    ✓ Market Segment: {market_segment}")
                else:
                    print(f"    ✗ Warning: Could not select market segment: {market_segment}")

            print(f"  → Waiting for table to load...")
            time.sleep(self.delay * 2)
            print(f"  ✓ Table loaded")

            if self.debug:
                debug_dir = "debug"
                os.makedirs(debug_dir, exist_ok=True)
                filename_base = f"rent_{property_type}_{property_subtype}_{market_segment}".replace(" ", "_").lower()
                try:
                    with open(os.path.join(debug_dir, f"{filename_base}_page_source.html"), "w", encoding="utf-8") as f:
                        f.write(self.driver.page_source)
                    self.driver.save_screenshot(os.path.join(debug_dir, f"{filename_base}_screenshot.png"))
                    print(f"  Debug files saved for {filename_base}")
                except Exception as e:
                    print(f"  Could not save debug files: {e}")

            print(f"  → Extracting table headers...")
            headers = self.get_table_headers()
            print(f"  ✓ Headers: {headers}")

            all_data = self.handle_pagination()

            if all_data:
                num_cols = len(all_data[0]) if all_data else 0
                if len(headers) != num_cols:
                    headers = headers[:num_cols] if len(headers) > num_cols else headers + [f"Column_{i+1}" for i in range(len(headers), num_cols)]
                df = pd.DataFrame(all_data, columns=headers[:num_cols])
                print(f"  ✓ DataFrame created: {len(df)} rows × {len(df.columns)} columns")
                return df
            else:
                print(f"  ✗ No data found for this combination")
                return pd.DataFrame()

        except Exception as e:
            print(f"  ✗ Error scraping combination: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()

    def process_dates(self, df):
        """Process the Date column: sort ascending, format as mmm-yyyy."""
        if df.empty or 'Date' not in df.columns:
            return df

        month_map = {
            'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
            'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
            'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
        }

        def parse_date_to_periodM(date_str):
            try:
                parts = date_str.strip().split()
                if len(parts) == 2:
                    month_abbr, year = parts
                    month_num = month_map.get(month_abbr, '01')
                    return f"{year}-{month_num}"
            except:
                pass
            return date_str

        def periodM_to_mmm_yyyy(period_str):
            try:
                parts = period_str.split('-')
                if len(parts) == 2:
                    year, month_num = parts
                    month_abbr = [k for k, v in month_map.items() if v == month_num]
                    if month_abbr:
                        return f"{month_abbr[0].lower()}-{year}"
            except:
                pass
            return period_str

        df['_sort_key'] = df['Date'].apply(parse_date_to_periodM)
        df = df.sort_values('_sort_key', ascending=True).reset_index(drop=True)
        df['Date'] = df['_sort_key'].apply(periodM_to_mmm_yyyy)
        df = df.drop(columns=['_sort_key'])
        return df

    def generate_filename(self, property_type, property_subtype, market_segment):
        """Generate a filename for the output file."""
        prop_clean = property_type.replace(" ", "_").lower()
        subtype_clean = property_subtype.replace(" ", "_").lower()
        market_clean = market_segment.replace(" ", "_").lower()
        return f"srx_rent_index_{prop_clean}_{subtype_clean}_{market_clean}.txt"

    def save_data(self, df, filename):
        """Save DataFrame to CSV file with .txt extension."""
        if df.empty:
            print(f"Skipping empty dataset: {filename}")
            return

        print(f"  → Processing dates (sorting ascending, formatting)...")
        df = self.process_dates(df)
        print(f"  ✓ Dates processed: {df['Date'].iloc[0]} to {df['Date'].iloc[-1]}")

        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, filename)
        df.to_csv(filepath, index=False, encoding='utf-8')
        print(f"Saved: {filepath} ({len(df)} rows)")

    def create_zip_archive(self):
        """Create a zip archive containing all rent index .txt files as .csv files."""
        output_dir = "output"
        zip_filename = os.path.join(output_dir, "srx_rent_index.zip")

        print(f"\n  → Creating zip archive: {zip_filename}")
        txt_files = glob.glob(os.path.join(output_dir, "srx_rent_index_*.txt"))

        if not txt_files:
            print(f"  ⚠ No .txt files found to add to zip")
            return

        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for txt_file in txt_files:
                base_name = os.path.basename(txt_file)
                csv_name = base_name.replace('.txt', '.csv')
                zipf.write(txt_file, csv_name)
                print(f"    Added: {csv_name}")

        print(f"  ✓ Zip archive created: {zip_filename} ({len(txt_files)} files)")

    def get_property_subtypes_for_type(self, property_type):
        """
        Discover property subtypes dynamically for a given property type.
        Options vary: Private Non-Landed has All/Condo/Apartment, HDB has room types, etc.
        """
        self.navigate_to_page()
        self.click_rent_toggle()

        dropdowns = self.find_rent_dropdowns()
        if 'property' not in dropdowns or 'subtype' not in dropdowns:
            return ["All"]

        self.select_dropdown_option(dropdowns['property'], property_type)
        time.sleep(self.delay)
        options = self.get_select_options(dropdowns['subtype'])
        return options if options else ["All"]

    def scrape_all(self):
        """Scrape all combinations. Discovers property subtypes per property type."""
        print("\n" + "="*80)
        print("SRX RENT INDEX SCRAPER - STARTING")
        print("="*80)

        self.setup_driver()

        total = 0
        all_combinations = []
        try:
            # Build combinations: for each property type, get subtypes, then cross with market segments
            for property_type in self.property_types:
                if hasattr(self, '_fixed_subtype'):
                    subtypes = [self._fixed_subtype]
                else:
                    subtypes = self.get_property_subtypes_for_type(property_type)
                for subtype in subtypes:
                    for market_segment in self.market_segments:
                        all_combinations.append((property_type, subtype, market_segment))

            total = len(all_combinations)
            print(f"\nTotal combinations to process: {total}")
            if total == 0:
                print("  ⚠ No combinations to scrape (could not discover dropdown options)")
            successful = 0
            failed = 0

            for current, (property_type, property_subtype, market_segment) in enumerate(all_combinations, 1):
                current += 1
                print(f"\n{'#'*80}")
                print(f"COMBINATION [{current}/{total}]")
                print(f"{'#'*80}")

                df = self.scrape_combination(property_type, property_subtype, market_segment)

                if not df.empty:
                    filename = self.generate_filename(property_type, property_subtype, market_segment)
                    print(f"  → Saving data to {filename}...")
                    self.save_data(df, filename)
                    successful += 1
                    print(f"  ✓ Series completed successfully!")
                else:
                    failed += 1
                    print(f"  ✗ Series failed - no data extracted")

                time.sleep(self.delay)

            if successful > 0:
                self.create_zip_archive()

        finally:
            self.close_driver()
            print("\n" + "="*80)
            print("SCRAPING COMPLETED!")
            print("="*80)
            print(f"Total combinations processed: {total}")
            print(f"Successful: {successful}")
            print(f"Failed: {failed}")
            print("="*80)


def main():
    """Main function to run the scraper."""
    import argparse

    parser = argparse.ArgumentParser(description='Scrape SRX Rent Index data')
    parser.add_argument('--debug', '-d', action='store_true', help='Save screenshots and page source for debugging')
    parser.add_argument('--property', type=str, help='Filter by property type (e.g. "Private Non-Landed")')
    parser.add_argument('--subtype', type=str, help='Filter by property subtype (e.g. "All")')
    parser.add_argument('--market', type=str, help='Filter by market segment (e.g. "All")')
    args = parser.parse_args()

    scraper = SRXRentIndexScraper(debug=args.debug)

    # If filters are provided, override the scrape_all loop
    if args.property or args.subtype or args.market:
        property_types = [args.property] if args.property else scraper.property_types
        market_segments = [args.market] if args.market else scraper.market_segments
        scraper.property_types = property_types
        scraper.market_segments = market_segments
        if args.subtype:
            scraper._fixed_subtype = args.subtype

    scraper.scrape_all()


if __name__ == "__main__":
    main()
