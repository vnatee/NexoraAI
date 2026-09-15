import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
import os
import logging

#WEB SCRAPING DEMO
def run_scraping_job(start_url) -> dict:

    def clean_url(url):
        parsed_url = urlparse(url)
        path = parsed_url.path
        default_files = ['index.html', 'index.htm', 'index.php', 'default.html', 'default.htm', 'home.html']
        for df in default_files:
            if path.endswith(f'/{df}'):
                path = path[:-len(df)]
                if not path:
                    path = '/'
                break
        if not path.endswith('/') and not '.' in os.path.basename(path) and path != '/':
            path += '/'
        cleaned_url = parsed_url._replace(path=path).geturl()
        return cleaned_url

    def get_base_url(url):
        parsed_url = urlparse(url)
        return f"{parsed_url.scheme}://{parsed_url.netloc}"

    def generate_file_path_and_name_from_url(url):
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname if parsed_url.hostname else "unknown_domain"
        hostname_clean = hostname.replace('www.', '').replace('.', '_')
        path_segments = [s for s in parsed_url.path.split('/') if s]
        relative_dir = ""
        filename_part = ""
        if not path_segments:
            relative_dir = hostname_clean
            filename_part = "root"
        else:
            last_segment = path_segments[-1]
            if '.' in last_segment and len(last_segment.split('.')[-1]) <= 4:
                filename_part = os.path.splitext(last_segment)[0]
                relative_dir_parts = path_segments[:-1]
            else:
                filename_part = last_segment if last_segment else "index"
                relative_dir_parts = path_segments[:-1]
            relative_dir = os.path.join(hostname_clean, *relative_dir_parts)
        filename_part_clean = re.sub(r'[^\w\-_\. ]', '_', filename_part).strip()
        if not filename_part_clean or filename_part_clean == "index" or filename_part_clean == "root":
            if parsed_url.query:
                query_part = re.sub(r'[^\w\-_\.]', '_', parsed_url.query)[:30]
                filename_part_clean = f"{filename_part_clean}_{query_part}"
        max_filename_len = 80
        if len(filename_part_clean) > max_filename_len:
            filename_part_clean = filename_part_clean[:max_filename_len - 5] + "_long"
        relative_dir_clean = re.sub(r'[^\w\-\_]', '_', relative_dir).strip()
        return relative_dir_clean, filename_part_clean

    def scrape_text_from_url(url):
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            text_content = soup.body.get_text(separator=' ', strip=True) if soup.body else soup.get_text(separator=' ', strip=True)
            return text_content
        except requests.exceptions.RequestException as e:
            logging.error(f"    ❌ Request error for {url}: {e}")
            return None
        except Exception as e:
            logging.error(f"    ❌ An unexpected error occurred while scraping {url}: {e}")
            return None

    # ------------------- Main Scraping Logic -------------------


    start_url = clean_url(start_url)
    base_url = get_base_url(start_url)
    logging.info(f"\n✅ Starting scraping links from: {start_url}")

    try:
        logging.info(f"Requesting main page content for {start_url}...")
        main_page_content = requests.get(start_url, timeout=15)
        main_page_content.raise_for_status()
        soup = BeautifulSoup(main_page_content.text, 'html.parser')
    except requests.exceptions.RequestException as e:
        logging.error(f"FATAL ERROR: Error accessing the main URL {start_url}: {e}")
        raise e

    links_found = soup.find_all('a', href=True)
    logging.info(f"✅ Found {len(links_found)} potential links on the main page.")
    processed_urls = set()
    uploaded_count = 0
    skipped_count = 0
    result_file = []
    for i, link in enumerate(links_found):
        href = link.get('href')
        full_url = urljoin(start_url, href)
        full_url = clean_url(full_url)

        if full_url.startswith(('http://', 'https://')) and \
           get_base_url(full_url) == base_url and \
           full_url not in processed_urls:

            processed_urls.add(full_url)
            new_url = str(full_url).replace("/","_")
            relative_dir_path, filename_base = generate_file_path_and_name_from_url(full_url)
            blob_path = os.path.join(relative_dir_path, f"{relative_dir_path}_{filename_base}||{new_url}.txt").replace("\\", "/")
            
            logging.info(f"\nProcessing link [{i+1}/{len(links_found)}]: {link.get_text(strip=True)[:50] if link.get_text(strip=True) else 'No Link Text'}... ({full_url})")
            logging.info(f"Target Blob: {blob_path}")
            
            text_content = scrape_text_from_url(full_url)
            
            if text_content:
                print(f"Target Blob: {blob_path}")
                result_file.append([blob_path,text_content])
                uploaded_count = uploaded_count + 1 
            else:
                logging.warning(f"    ❌ Skipped (Error occurred during scraping - see above for details).")
                skipped_count += 1
        else:
            reason_skipped = []
            if not full_url.startswith(('http://', 'https://')):
                reason_skipped.append("Not a valid HTTP/HTTPS URL")
            if get_base_url(full_url) != base_url:
                reason_skipped.append("Different domain")
            if full_url in processed_urls:
                reason_skipped.append("Already processed/Duplicate")

            logging.info(f"\nProcessing link [{i+1}/{len(links_found)}]: {link.get_text(strip=True)[:50] if link.get_text(strip=True) else 'No Link Text'}... ({full_url})")
            logging.info(f"    ➡️ Skipped (Reason(s): {', '.join(reason_skipped) if reason_skipped else 'Unknown criteria mismatch'})")
            skipped_count += 1
            
    logging.info("\n--- Scraping process completed ---")
    return {"status": "success", "message": f"Scraping completed. Uploaded {uploaded_count} blobs, skipped {skipped_count} links."},result_file