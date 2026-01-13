"""
Script to scrape SRX Price Index data from https://www.srx.com.sg/price-index
Handles multiple dropdown combinations and pagination to extract all time series data.
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


class SRXPriceIndexScraper:
    def __init__(self, base_url="https://www.srx.com.sg/price-index", delay=2, debug=False):
        """
        Initialize the scraper.
        
        Args:
            base_url: URL of the SRX price index page
            delay: Delay between actions in seconds
            debug: If True, save page source and screenshots for debugging
        """
        self.base_url = base_url
        self.debug = debug
        self.driver = None
        
        # Detect CI environment and increase delays
        self.is_ci = os.environ.get('CI', 'false').lower() == 'true'
        if self.is_ci:
            self.delay = max(delay, 4)  # Minimum 4 seconds delay in CI
            self.debug = True  # Always debug in CI for troubleshooting
            print(f"  ℹ CI environment detected - delay set to {self.delay}s, debug mode enabled")
        else:
            self.delay = delay
        
        # Define all dropdown options
        self.property_types = [
            "Private Non-Landed",
            "Private Landed", 
            "HDB"
        ]
        
        self.sale_types = [
            "All Sale",
            "Resale"
        ]
        
        self.market_segments = [
            "All",
            "Core Central",
            "Rest of Central",
            "Outside Central"
        ]
        
    def setup_driver(self):
        """Initialize Chrome WebDriver with appropriate options."""
        
        # Use undetected-chromedriver in CI to bypass Cloudflare
        if self.is_ci and UC_AVAILABLE:
            print("  ℹ Using undetected-chromedriver to bypass Cloudflare")
            
            options = uc.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--headless=new')
            
            self.driver = uc.Chrome(options=options, headless=True)
            self.driver.implicitly_wait(15)
            
        else:
            # Standard selenium for local use
            options = webdriver.ChromeOptions()
            options.add_argument('--start-maximized')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            if self.is_ci:
                # Fallback if undetected-chromedriver not available
                print("  ℹ Running in CI environment - enabling headless mode")
                options.add_argument('--headless=new')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--disable-gpu')
                options.add_argument('--window-size=1920,1080')
            
            # Use webdriver-manager to handle ChromeDriver automatically
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
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except TimeoutException:
            print(f"Timeout waiting for element: {by}={value}")
            return None
            
    def wait_for_clickable(self, by, value, timeout=20):
        """Wait for an element to be clickable."""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((by, value))
            )
            return element
        except TimeoutException:
            print(f"Timeout waiting for clickable element: {by}={value}")
            return None
            
    def navigate_to_page(self):
        """Navigate to the SRX price index page."""
        print(f"  → Navigating to {self.base_url}...")
        self.driver.get(self.base_url)
        
        # Wait longer in CI for page to fully load
        wait_time = self.delay * 3 if self.is_ci else self.delay * 2
        time.sleep(wait_time)
        
        # Try to dismiss any cookie consent or popup
        try:
            # Common cookie consent button selectors
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
        
        # Log page state for debugging
        print(f"  ✓ Page loaded (title: {self.driver.title[:50]}...)" if len(self.driver.title) > 50 else f"  ✓ Page loaded (title: {self.driver.title})")
        
    def find_dropdown_by_label(self, label_text):
        """
        Find a dropdown by its label text.
        This is a helper method to locate dropdowns that might have different structures.
        """
        try:
            # Try to find label and then the associated select element
            labels = self.driver.find_elements(By.TAG_NAME, "label")
            for label in labels:
                if label_text.lower() in label.text.lower():
                    # Try to find select element near the label
                    parent = label.find_element(By.XPATH, "./..")
                    select = parent.find_element(By.TAG_NAME, "select")
                    return select
        except:
            pass
            
        # Alternative: try to find select by placeholder or nearby text
        try:
            selects = self.driver.find_elements(By.TAG_NAME, "select")
            for select in selects:
                # Check if label text is nearby
                try:
                    parent = select.find_element(By.XPATH, "./..")
                    if label_text.lower() in parent.text.lower():
                        return select
                except:
                    continue
        except:
            pass
            
        return None
        
    def select_dropdown_option(self, dropdown_element, option_text):
        """Select an option from a dropdown."""
        try:
            select = Select(dropdown_element)
            select.select_by_visible_text(option_text)
            time.sleep(self.delay)  # Wait for data to load
            return True
        except Exception as e:
            print(f"Error selecting option '{option_text}': {e}")
            return False
            
    def extract_table_data(self):
        """Extract data from the current table view."""
        data = []
        
        try:
            # Wait for table to be present
            table = self.wait_for_element(By.TAG_NAME, "table")
            if not table:
                # Try alternative selectors
                table = self.driver.find_element(By.CSS_SELECTOR, "table")
                
            # Find all rows
            rows = table.find_elements(By.TAG_NAME, "tr")
            
            # Skip header row if present
            start_idx = 0
            if len(rows) > 0:
                # Check if first row is header
                first_row = rows[0]
                headers = [th.text.strip() for th in first_row.find_elements(By.TAG_NAME, "th")]
                if not headers:
                    headers = [td.text.strip() for td in first_row.find_elements(By.TAG_NAME, "td")]
                
                # If headers found, start from second row
                if headers and any(h for h in headers if h):
                    start_idx = 1
                    
            # Extract data rows
            for row in rows[start_idx:]:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 2:  # At least date and value columns
                    row_data = [cell.text.strip() for cell in cells]
                    if any(row_data):  # Skip empty rows
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
        """Handle pagination to get all pages of data.
        
        The SRX page uses: <li id="pagination-next-button">Next</li>
        The Next button stays visible even on the last page, so we detect
        the end by checking if the page content is the same as the previous page.
        """
        all_data = []
        page_num = 1
        previous_page_data = None
        
        print(f"\n  → Extracting table data...")
        
        while True:
            # Extract current page data
            page_data = self.extract_table_data()
            
            # Check if this page is the same as the previous page (end of data)
            if previous_page_data is not None and page_data == previous_page_data:
                print(f"    📄 Page {page_num}: ⚠ Duplicate content detected - reached end of data")
                break
            
            if page_data:
                all_data.extend(page_data)
                print(f"    📄 Page {page_num}: ✓ Found {len(page_data)} rows (Total: {len(all_data)})")
                previous_page_data = page_data  # Store for comparison
            else:
                print(f"    📄 Page {page_num}: ⚠ No data found")
                break
                
            # Find the Next button by its ID
            try:
                next_button = self.driver.find_element(By.ID, "pagination-next-button")
                
                # Check if it's visible and clickable
                if not next_button.is_displayed():
                    print(f"    ✓ Reached last page (Next button hidden)")
                    break
                    
                # Check if disabled via class or style
                classes = next_button.get_attribute('class') or ''
                style = next_button.get_attribute('style') or ''
                
                if 'disabled' in classes.lower() or 'display: none' in style.lower() or 'visibility: hidden' in style.lower():
                    print(f"    ✓ Reached last page (Next button disabled)")
                    break
                
                # Try to click next
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
        
    def find_dropdowns(self):
        """
        Find all dropdown elements on the page.
        Returns a dictionary with dropdown types as keys.
        
        The SRX page has table-specific dropdowns with these IDs:
        - table-property-type: Property types (Private Non-Landed, Private Landed, HDB)
        - table-sale-resale: Sale types (All Sale, Resale)
        - table-market-segments: Market segments (All, Core Central, etc.)
        """
        dropdowns_dict = {}
        
        try:
            # Use the exact IDs from the SRX page
            # Property type dropdown
            try:
                element = self.driver.find_element(By.ID, "table-property-type")
                dropdowns_dict['property'] = element
                print(f"    Found property dropdown: table-property-type")
            except:
                print(f"    ⚠ Could not find table-property-type")
            
            # Sale type dropdown
            try:
                element = self.driver.find_element(By.ID, "table-sale-resale")
                dropdowns_dict['sale'] = element
                print(f"    Found sale dropdown: table-sale-resale")
            except:
                print(f"    ⚠ Could not find table-sale-resale")
            
            # Market segment dropdown
            try:
                element = self.driver.find_element(By.ID, "table-market-segments")
                dropdowns_dict['market'] = element
                print(f"    Found market dropdown: table-market-segments")
            except:
                print(f"    ⚠ Could not find table-market-segments")
                            
        except Exception as e:
            print(f"  ✗ Error finding dropdowns: {e}")
            
        return dropdowns_dict
        
    def scrape_combination(self, property_type, sale_type, market_segment):
        """
        Scrape data for a specific combination of dropdown options.
        
        Returns:
            DataFrame with the scraped data
        """
        print(f"\n{'='*80}")
        print(f"SERIES: {property_type} | {sale_type} | {market_segment}")
        print(f"{'='*80}")
        
        # Navigate to page
        self.navigate_to_page()
        
        # Find and select dropdowns
        try:
            print(f"  → Finding dropdowns...")
            dropdowns = self.find_dropdowns()
            
            if not dropdowns:
                print("  ⚠ Warning: Could not find dropdowns. Trying alternative method...")
                # Last resort: find all selects and use them in order
                all_selects = self.driver.find_elements(By.TAG_NAME, "select")
                if len(all_selects) >= 3:
                    dropdowns = {
                        'property': all_selects[0],
                        'sale': all_selects[1],
                        'market': all_selects[2]
                    }
                    print(f"  ✓ Found {len(all_selects)} dropdown(s) using fallback method")
                else:
                    print(f"  ✗ Error: Found only {len(all_selects)} dropdown(s), expected 3")
                    return pd.DataFrame()
            else:
                print(f"  ✓ Found {len(dropdowns)} dropdown(s)")
            
            # Select options
            print(f"  → Selecting dropdown options...")
            if 'property' in dropdowns:
                if self.select_dropdown_option(dropdowns['property'], property_type):
                    print(f"    ✓ Property Type: {property_type}")
                else:
                    print(f"    ✗ Warning: Could not select property type: {property_type}")
            else:
                print("    ✗ Warning: Property type dropdown not found")
                
            if 'sale' in dropdowns:
                if self.select_dropdown_option(dropdowns['sale'], sale_type):
                    print(f"    ✓ Sale Type: {sale_type}")
                else:
                    print(f"    ✗ Warning: Could not select sale type: {sale_type}")
            else:
                print("    ✗ Warning: Sale type dropdown not found")
                
            if 'market' in dropdowns:
                if self.select_dropdown_option(dropdowns['market'], market_segment):
                    print(f"    ✓ Market Segment: {market_segment}")
                else:
                    print(f"    ✗ Warning: Could not select market segment: {market_segment}")
            else:
                print("    ✗ Warning: Market segment dropdown not found")
                    
            # Wait for table to update
            print(f"  → Waiting for table to load...")
            time.sleep(self.delay * 2)
            print(f"  ✓ Table loaded")
            
            # Debug: Save page source if debug mode
            if self.debug:
                debug_dir = "debug"
                os.makedirs(debug_dir, exist_ok=True)
                filename_base = f"{property_type}_{sale_type}_{market_segment}".replace(" ", "_").lower()
                try:
                    with open(os.path.join(debug_dir, f"{filename_base}_page_source.html"), "w", encoding="utf-8") as f:
                        f.write(self.driver.page_source)
                    self.driver.save_screenshot(os.path.join(debug_dir, f"{filename_base}_screenshot.png"))
                    print(f"  Debug files saved for {filename_base}")
                except Exception as e:
                    print(f"  Could not save debug files: {e}")
            
            # Get headers
            print(f"  → Extracting table headers...")
            headers = self.get_table_headers()
            print(f"  ✓ Headers: {headers}")
            
            # Handle pagination and get all data
            all_data = self.handle_pagination()
            
            if all_data:
                # Create DataFrame
                # Ensure headers match data columns
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
        """
        Process the Date column:
        1. Convert "Nov 2025" to "2025-11" (periodM) for sorting
        2. Sort ascending (oldest first)
        3. Convert to "nov-2025" (mmm-yyyy lowercase) for final output
        
        Returns the processed DataFrame.
        """
        if df.empty or 'Date' not in df.columns:
            return df
            
        # Month name to number mapping
        month_map = {
            'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
            'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
            'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
        }
        
        def parse_date_to_periodM(date_str):
            """Convert 'Nov 2025' to '2025-11'"""
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
            """Convert '2025-11' to 'nov-2025'"""
            try:
                parts = period_str.split('-')
                if len(parts) == 2:
                    year, month_num = parts
                    # Reverse lookup month abbreviation
                    month_abbr = [k for k, v in month_map.items() if v == month_num]
                    if month_abbr:
                        return f"{month_abbr[0].lower()}-{year}"
            except:
                pass
            return period_str
        
        # Step 1: Convert to periodM format for sorting
        df['_sort_key'] = df['Date'].apply(parse_date_to_periodM)
        
        # Step 2: Sort ascending (oldest first)
        df = df.sort_values('_sort_key', ascending=True).reset_index(drop=True)
        
        # Step 3: Convert Date to mmm-yyyy format
        df['Date'] = df['_sort_key'].apply(periodM_to_mmm_yyyy)
        
        # Remove the sort key column
        df = df.drop(columns=['_sort_key'])
        
        return df
        
    def generate_filename(self, property_type, sale_type, market_segment):
        """Generate a filename for the output file."""
        # Clean names for filename
        prop_clean = property_type.replace(" ", "_").lower()
        sale_clean = sale_type.replace(" ", "_").lower()
        market_clean = market_segment.replace(" ", "_").lower()
        
        filename = f"srx_price_index_{prop_clean}_{sale_clean}_{market_clean}.txt"
        return filename
        
    def save_data(self, df, filename):
        """Save DataFrame to CSV file with .txt extension."""
        if df.empty:
            print(f"Skipping empty dataset: {filename}")
            return
        
        # Process dates before saving
        print(f"  → Processing dates (sorting ascending, formatting)...")
        df = self.process_dates(df)
        print(f"  ✓ Dates processed: {df['Date'].iloc[0]} to {df['Date'].iloc[-1]}")
            
        # Create output directory if it doesn't exist
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        
        filepath = os.path.join(output_dir, filename)
        df.to_csv(filepath, index=False, encoding='utf-8')
        print(f"Saved: {filepath} ({len(df)} rows)")
        
    def create_zip_archive(self):
        """
        Create a zip archive containing all .txt files as .csv files.
        The zip file is saved in the output directory.
        """
        output_dir = "output"
        zip_filename = os.path.join(output_dir, "srx_price_index.zip")
        
        print(f"\n  → Creating zip archive: {zip_filename}")
        
        # Find all .txt files in output directory
        txt_files = glob.glob(os.path.join(output_dir, "srx_price_index_*.txt"))
        
        if not txt_files:
            print(f"  ⚠ No .txt files found to add to zip")
            return
            
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for txt_file in txt_files:
                # Get just the filename without path
                base_name = os.path.basename(txt_file)
                # Change extension from .txt to .csv for the zip
                csv_name = base_name.replace('.txt', '.csv')
                # Add file to zip with new name
                zipf.write(txt_file, csv_name)
                print(f"    Added: {csv_name}")
                
        print(f"  ✓ Zip archive created: {zip_filename} ({len(txt_files)} files)")
        
    def scrape_all(self):
        """Scrape all combinations of dropdown options."""
        print("\n" + "="*80)
        print("SRX PRICE INDEX SCRAPER - STARTING")
        print("="*80)
        
        self.setup_driver()
        
        try:
            total_combinations = len(self.property_types) * len(self.sale_types) * len(self.market_segments)
            current = 0
            successful = 0
            failed = 0
            
            print(f"\nTotal combinations to process: {total_combinations}")
            print(f"Property Types: {len(self.property_types)}")
            print(f"Sale Types: {len(self.sale_types)}")
            print(f"Market Segments: {len(self.market_segments)}")
            
            for property_type in self.property_types:
                for sale_type in self.sale_types:
                    for market_segment in self.market_segments:
                        current += 1
                        print(f"\n{'#'*80}")
                        print(f"COMBINATION [{current}/{total_combinations}]")
                        print(f"{'#'*80}")
                        
                        df = self.scrape_combination(property_type, sale_type, market_segment)
                        
                        if not df.empty:
                            filename = self.generate_filename(property_type, sale_type, market_segment)
                            print(f"  → Saving data to {filename}...")
                            self.save_data(df, filename)
                            successful += 1
                            print(f"  ✓ Series completed successfully!")
                        else:
                            failed += 1
                            print(f"  ✗ Series failed - no data extracted")
                            
                        time.sleep(self.delay)  # Delay between combinations
                        
            # Create zip archive with .csv files
            if successful > 0:
                self.create_zip_archive()
                
        finally:
            self.close_driver()
            print("\n" + "="*80)
            print("SCRAPING COMPLETED!")
            print("="*80)
            print(f"Total combinations processed: {current}")
            print(f"Successful: {successful}")
            print(f"Failed: {failed}")
            print("="*80)


def main():
    """Main function to run the scraper."""
    import sys
    
    # Check for debug flag
    debug = '--debug' in sys.argv or '-d' in sys.argv
    
    scraper = SRXPriceIndexScraper(debug=debug)
    scraper.scrape_all()


if __name__ == "__main__":
    main()
