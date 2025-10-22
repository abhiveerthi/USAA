import requests
from bs4 import BeautifulSoup
import sys
import argparse
import csv


def scrape_banking_dive(num_articles=20):
    """
    Scrapes the titles and summaries of articles from Banking Dive.

    Args:
        num_articles (int): The target number of articles to collect.
    """
    
    base_url = "https://www.bankingdive.com/news/"
    articles_data = []
    page_num = 1
    
    # Set a User-Agent header to mimic a real browser
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    print(f"Starting scraper... targeting {num_articles} articles.\n")

    try:
        # Loop through pages until we have enough articles
        while len(articles_data) < num_articles:
            # Construct the URL for the current page
            # page=1 is the same as the main /news/ page
            current_url = f"{base_url}?page={page_num}"
            print(f"Fetching page: {current_url}")
            
            # Make the HTTP request
            response = requests.get(current_url, headers=headers)
            
            # Check for bad responses (404, 403, 500, etc.)
            response.raise_for_status()
            
            # Parse the HTML content
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # New strategy: Banking Dive may use containers with classes that include
            # 'rowfeed' (for example rowfeed items). Search for any elements whose
            # class contains the substring 'rowfeed' and treat each as an article
            # candidate. This is more robust than relying on a single <ul> wrapper.
            def has_feed_class(tag):
                """Return True if the tag's class list contains feed-like tokens.

                We accept tokens that contain 'rowfeed' or start with/contain 'feed'
                (e.g., 'feed__item', 'feed__title', 'feed__description').
                """
                cls = tag.get('class')
                if not cls:
                    return False
                for c in cls:
                    if not isinstance(c, str):
                        continue
                    low = c.lower()
                    if 'rowfeed' in low:
                        return True
                    # match tokens like 'feed', 'feed__item', 'feed-item', 'feed__title'
                    if low == 'feed' or low.startswith('feed') or 'feed__' in low or 'feed-' in low:
                        return True
                return False

            # Try to find item-level containers first (li/div/article with rowfeed)
            articles = soup.find_all(lambda tag: tag.name in ('li', 'div', 'article') and has_feed_class(tag))

            # Fallback: sometimes there isn't an explicit rowfeed item element; try
            # to find any element which contains 'rowfeed' in its class attribute.
            if not articles:
                containers = soup.find_all(has_feed_class)
                # Flatten potential children that look like article nodes
                for c in containers:
                    # prefer children that are li/article/div
                    children = c.find_all(['li', 'article', 'div'])
                    if children:
                        for ch in children:
                            if has_feed_class(ch):
                                articles.append(ch)
                            else:
                                # include the child anyway as a possible article
                                articles.append(ch)
                # last resort: if still empty, try all <article> tags
                if not articles:
                    articles = soup.find_all('article')

            # If no candidate articles found, assume we've reached the end
            if not articles:
                print("Found no article-like elements on this page. Stopping.")
                break

            # Loop through each candidate and extract title + summary with fallbacks
            for article in articles:
                # Title: prefer h3/h2/h1, otherwise first <a> with text
                title_element = None
                for tag_name in ('h3', 'h2', 'h1'):
                    t = article.find(tag_name)
                    if t and t.get_text(strip=True):
                        title_element = t
                        break
                if not title_element:
                    a = article.find('a')
                    if a and a.get_text(strip=True):
                        title_element = a

                # Summary/description: prefer p with 'deck' or 'summary' in class,
                # otherwise first <p> with reasonable length
                summary_element = None
                # try class-based heuristics
                for p in article.find_all('p'):
                    pcls = p.get('class')
                    text = p.get_text(strip=True)
                    if not text:
                        continue
                    if pcls and any(k in ' '.join(pcls).lower() for k in ('deck', 'summary', 'excerpt', 'dek', 'rowfeed')):
                        summary_element = p
                        break
                # fallback to first <p> with > 20 chars
                if not summary_element:
                    for p in article.find_all('p'):
                        text = p.get_text(strip=True)
                        if text and len(text) > 20:
                            summary_element = p
                            break

                # As an alternate fallback, some summaries are in divs/spans
                if not summary_element:
                    for tag in ('div', 'span'):
                        for el in article.find_all(tag):
                            text = el.get_text(strip=True)
                            if text and 20 < len(text) < 500:
                                summary_element = el
                                break
                        if summary_element:
                            break

                # Ensure we have at least a title (and optionally a summary)
                if title_element:
                    title = title_element.get_text(strip=True)
                    summary = summary_element.get_text(strip=True) if summary_element else ''
                    articles_data.append({'title': title, 'summary': summary})

                    # Stop once we've hit our target
                    if len(articles_data) >= num_articles:
                        break
            
            # Go to the next page
            page_num += 1

    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
    except requests.exceptions.RequestException as e:
        print(f"An error occurred during the request: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    # --- Return the final results ---
    print(f"\n--- Successfully collected {len(articles_data)} articles ---")
    return articles_data

# --- How to Run This Code ---
# 1. Make sure you have the required libraries:
#    pip install requests
#    pip install beautifulsoup4
#
# 2. Save the code as a .py file (e.g., scraper.py)
# 3. Run it from your terminal:
#    python scraper.py

def main(argv=None):
    parser = argparse.ArgumentParser(description='Scrape Banking Dive news titles and summaries.')
    parser.add_argument('--num', '-n', type=int, default=20, help='Number of articles to collect (default: 20)')
    parser.add_argument('--csv', '-o', type=str, default=None, help='Path to CSV output file (optional)')
    args = parser.parse_args(argv)

    articles = scrape_banking_dive(args.num)

    # Print to stdout (trimmed) like before
    for i, article in enumerate(articles[:args.num]):
        print(f"\nARTICLE {i + 1}")
        print(f"  Title: {article['title']}")
        print(f"  Summary: {article['summary']}")

    # If CSV output requested, write the file
    if args.csv:
        try:
            # Use UTF-8-sig so Excel on Windows can read the UTF-8 CSV correctly
            with open(args.csv, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=['title', 'summary'])
                writer.writeheader()
                for article in articles[:args.num]:
                    writer.writerow({'title': article['title'], 'summary': article['summary']})
            print(f"\nWrote {len(articles[:args.num])} articles to CSV: {args.csv}")
        except Exception as e:
            print(f"Failed to write CSV {args.csv}: {e}")


if __name__ == "__main__":
    main()