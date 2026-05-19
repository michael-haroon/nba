import json
import pandas as pd
from curl_cffi import requests

def download_nba_html(season="2025-26"):
    """
    Downloads the HTML for the NBA Traditional Box Scores page using a 
    single request with a high-fidelity browser fingerprint.
    """
    
    # Target URL with the specific sorting parameters requested
    url = f"https://www.nba.com/stats/teams/boxscores-traditional?SeasonType=Regular%20Season&Season={season}&dir=D&sort=GDATE"

    # Using the impersonation targets and headers logic from your curate_history.py
    # This ensures we don't look like a bot by matching Chrome's TLS and HTTP/2 signature.
    headers = {
        "Host": "www.nba.com",
        "Connection": "keep-alive",
        "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "upgrade-insecure-requests": "1",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-User": "?1",
        "Sec-Fetch-Dest": "document",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.9",
    }

    print(f"Downloading HTML from: {url}")

    try:
        # We use 'chrome124' to match the User-Agent and SEC headers
        response = requests.get(url, headers=headers, impersonate="chrome124", timeout=30)
        
        if response.status_code == 200:
            filename = f"nba_boxscores_{season}.html"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(response.text)
            
            print(f"Successfully downloaded to {filename}")
            print(f"File size: {len(response.text) / 1024:.2f} KB")
            
            # Check for the data script tag to confirm it's not a block page
            if "__NEXT_DATA__" in response.text:
                print("Verification: Data payload found in HTML.")
            else:
                print("Warning: HTML downloaded but data hydration script missing.")
                
            return response.text
        else:
            print(f"Failed. Status Code: {response.status_code}")
            return None

    except Exception as e:
        print(f"An error occurred: {e}")
        return None

if __name__ == "__main__":
    download_nba_html()