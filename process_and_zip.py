"""
Utility script to process existing .txt files:
1. Convert dates from "Nov 2025" → sort by "2025-11" → output as "nov-2025"
2. Sort data ascending (oldest observation first)
3. Create a zip archive with .csv extensions

Usage:
    python process_and_zip.py
"""

import os
import glob
import zipfile
import pandas as pd


# Month name to number mapping
MONTH_MAP = {
    'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
    'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
    'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
}

# Reverse mapping for number to month abbreviation
NUM_TO_MONTH = {v: k.lower() for k, v in MONTH_MAP.items()}


def parse_date_to_periodM(date_str):
    """
    Convert various date formats to periodM format (yyyy-mm).
    
    Handles:
    - "Nov 2025" → "2025-11"
    - "nov-2025" → "2025-11" (already processed)
    """
    try:
        date_str = str(date_str).strip()
        
        # Check if already in mmm-yyyy format (e.g., "nov-2025")
        if '-' in date_str and len(date_str.split('-')) == 2:
            parts = date_str.split('-')
            if len(parts[0]) == 3 and len(parts[1]) == 4:
                # Already in mmm-yyyy format, convert to yyyy-mm
                month_abbr = parts[0].capitalize()
                year = parts[1]
                month_num = MONTH_MAP.get(month_abbr, '01')
                return f"{year}-{month_num}"
        
        # Handle "Nov 2025" format
        parts = date_str.split()
        if len(parts) == 2:
            month_abbr, year = parts
            month_num = MONTH_MAP.get(month_abbr, '01')
            return f"{year}-{month_num}"
            
    except Exception as e:
        print(f"    ⚠ Could not parse date '{date_str}': {e}")
        
    return date_str


def periodM_to_mmm_yyyy(period_str):
    """
    Convert periodM format to mmm-yyyy format.
    
    "2025-11" → "nov-2025"
    """
    try:
        parts = period_str.split('-')
        if len(parts) == 2:
            year, month_num = parts
            month_abbr = NUM_TO_MONTH.get(month_num, 'jan')
            return f"{month_abbr}-{year}"
    except:
        pass
    return period_str


def process_dataframe(df):
    """
    Process a DataFrame:
    1. Convert Date to periodM for sorting
    2. Sort ascending (oldest first)
    3. Convert Date to mmm-yyyy format
    
    Returns the processed DataFrame.
    """
    if df.empty or 'Date' not in df.columns:
        return df
    
    # Step 1: Convert to periodM format for sorting
    df['_sort_key'] = df['Date'].apply(parse_date_to_periodM)
    
    # Step 2: Sort ascending (oldest first)
    df = df.sort_values('_sort_key', ascending=True).reset_index(drop=True)
    
    # Step 3: Convert Date to mmm-yyyy format
    df['Date'] = df['_sort_key'].apply(periodM_to_mmm_yyyy)
    
    # Remove the sort key column
    df = df.drop(columns=['_sort_key'])
    
    return df


def process_files(output_dir="output"):
    """
    Process all .txt files in the output directory.
    """
    txt_files = glob.glob(os.path.join(output_dir, "srx_price_index_*.txt"))
    
    if not txt_files:
        print(f"⚠ No .txt files found in {output_dir}/")
        print("  Run the scraper first: python scrape_srx_price_index.py")
        return []
    
    print(f"Found {len(txt_files)} file(s) to process")
    print("-" * 60)
    
    processed_files = []
    
    for txt_file in sorted(txt_files):
        filename = os.path.basename(txt_file)
        print(f"\n📄 Processing: {filename}")
        
        try:
            # Read the file
            df = pd.read_csv(txt_file)
            original_rows = len(df)
            
            # Check first and last dates before processing
            if 'Date' in df.columns and len(df) > 0:
                first_date_before = df['Date'].iloc[0]
                last_date_before = df['Date'].iloc[-1]
                print(f"   Before: {first_date_before} ... {last_date_before} ({original_rows} rows)")
            
            # Process the DataFrame
            df = process_dataframe(df)
            
            # Check first and last dates after processing
            if 'Date' in df.columns and len(df) > 0:
                first_date_after = df['Date'].iloc[0]
                last_date_after = df['Date'].iloc[-1]
                print(f"   After:  {first_date_after} ... {last_date_after} ({len(df)} rows)")
            
            # Save back to file
            df.to_csv(txt_file, index=False, encoding='utf-8')
            print(f"   ✓ Saved")
            
            processed_files.append(txt_file)
            
        except Exception as e:
            print(f"   ✗ Error processing {filename}: {e}")
    
    return processed_files


def create_zip_archive(output_dir="output", zip_name="srx_price_index.zip"):
    """
    Create a zip archive containing all .txt files as .csv files.
    """
    zip_filepath = os.path.join(output_dir, zip_name)
    
    print(f"\n{'='*60}")
    print(f"Creating zip archive: {zip_filepath}")
    print("-" * 60)
    
    txt_files = glob.glob(os.path.join(output_dir, "srx_price_index_*.txt"))
    
    if not txt_files:
        print(f"⚠ No .txt files found in {output_dir}/")
        return
    
    with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for txt_file in sorted(txt_files):
            base_name = os.path.basename(txt_file)
            csv_name = base_name.replace('.txt', '.csv')
            zipf.write(txt_file, csv_name)
            print(f"  ✓ Added: {csv_name}")
    
    # Get zip file size
    zip_size = os.path.getsize(zip_filepath)
    zip_size_kb = zip_size / 1024
    
    print("-" * 60)
    print(f"✓ Zip archive created: {zip_filepath}")
    print(f"  Files: {len(txt_files)}")
    print(f"  Size: {zip_size_kb:.1f} KB")


def main():
    """Main function to process files and create zip."""
    print("=" * 60)
    print("SRX PRICE INDEX - PROCESS AND ZIP")
    print("=" * 60)
    
    output_dir = "output"
    
    # Step 1: Process all files
    print("\n[1/2] PROCESSING FILES")
    print("=" * 60)
    processed_files = process_files(output_dir)
    
    if not processed_files:
        print("\nNo files processed. Exiting.")
        return
    
    # Step 2: Create zip archive
    print("\n[2/2] CREATING ZIP ARCHIVE")
    create_zip_archive(output_dir)
    
    print("\n" + "=" * 60)
    print("COMPLETE!")
    print("=" * 60)
    print(f"Processed {len(processed_files)} file(s)")
    print(f"Output: {output_dir}/srx_price_index.zip")


if __name__ == "__main__":
    main()
