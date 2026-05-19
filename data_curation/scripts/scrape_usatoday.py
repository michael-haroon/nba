import os
import re
from bs4 import BeautifulSoup
from pathlib import Path

# Directory containing your .html archives
INPUT_DIR = Path("/Users/michaelharoon/Projects/Prediction markets/nba/data_curation/data/unscraped_sites/usatoday_sag/")
OUTPUT_DIR = INPUT_DIR / "cleaned_ratings"
OUTPUT_DIR.mkdir(exist_ok=True)

def extract_sagarin_payload(html_content):
    soup = BeautifulSoup(html_content, 'lxml')
    
    # 1. Target the primary container across different site versions
    # 2013-2015: article#sagarin
    # 2016-2021: div.sagarin-container or raw <pre>
    container = soup.find('article', id='sagarin') or \
                soup.find('div', class_='sagarin-container') or \
                soup.find('pre')
    
    if not container:
        return None

    # Get text with newlines preserved
    raw_text = container.get_text(separator="\n")
    
    # 2. Refined anchor detection
    # We look for the copyright and the start of the rating table
    lines = [line.strip() for line in raw_text.split('\n')]
    
    start_idx = 0
    for i, line in enumerate(lines):
        if "Jeff Sagarin" in line or "RATING top-to-bottom" in line:
            start_idx = i
            break
            
    # Stop before the site footer/utility links
    end_idx = len(lines)
    for i, line in enumerate(lines):
        if "Back to top" in line or "Terms of Service" in line:
            end_idx = i
            break
            
    return "\n".join(lines[start_idx:end_idx])

def process_directory():
    print(f"Starting extraction in: {INPUT_DIR}")
    files = list(INPUT_DIR.glob("*.html"))
    
    success_count = 0
    for file_path in files:
        try:
            with open(file_path, 'r', encoding='latin-1', errors='ignore') as f:
                content = f.read()
                
            payload = extract_sagarin_payload(content)
            
            if payload and "RATING" in payload:
                output_file = OUTPUT_DIR / f"{file_path.stem}_cleaned.txt"
                output_file.write_text(payload)
                print(f"✔ Processed: {file_path.name}")
                success_count += 1
            else:
                print(f"✘ Failed to find rating table in: {file_path.name}")
                
        except Exception as e:
            print(f"‼ Error processing {file_path.name}: {e}")

    print(f"\nFinished. Successfully cleaned {success_count}/{len(files)} files.")
    print(f"Cleaned files are in: {OUTPUT_DIR}")

if __name__ == "__main__":
    process_directory()