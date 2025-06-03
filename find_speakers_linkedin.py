import os
import requests
from bs4 import BeautifulSoup
import json

# --- CONFIG ---
GOOGLE_API_KEY = "AIzaSyAfGm5kah7uuBxAVmlvHFlMzn62gsOqwX8"
GOOGLE_CX = "36659b220105748bc"


def extract_speakers_from_luma(event_url):
    """
    Given a Luma event page URL, extract speaker names from the page.
    Returns a list of speaker names (strings).
    """
    resp = requests.get(event_url)
    soup = BeautifulSoup(resp.text, 'html.parser')
    speakers = []
    # Try to find speaker sections (Luma's structure may change)
    # Look for sections labeled as 'Speakers', 'Host', or similar
    for section in soup.find_all(['section', 'div']):
        if section.text.strip().lower().startswith(('speakers', 'host')):
            # Find all possible speaker name tags inside section
            for tag in section.find_all(['a', 'span', 'div']):
                # Heuristic: speaker names are usually not too long and not all uppercase
                txt = tag.get_text(strip=True)
                if 2 < len(txt) < 60 and txt.istitle():
                    speakers.append(txt)
    # Fallback: search for <a> tags with href to linkedin
    for a in soup.find_all('a', href=True):
        if 'linkedin.com/in/' in a['href']:
            txt = a.get_text(strip=True)
            if txt and txt not in speakers:
                speakers.append(txt)
    # Deduplicate
    return list(set(speakers))


def google_search_linkedin_profile(name):
    """
    Search Google for the top LinkedIn profile for the given name.
    Returns the first LinkedIn profile URL found, or None.
    """
    query = f'"{name}" site:linkedin.com'
    url = f"https://www.googleapis.com/customsearch/v1?key={GOOGLE_API_KEY}&cx={GOOGLE_CX}&q={requests.utils.quote(query)}"
    resp = requests.get(url)
    data = resp.json()
    if 'items' in data:
        for item in data['items']:
            link = item.get('link', '')
            if 'linkedin.com/in/' in link:
                return link
    return None


def find_speakers_linkedin(event_url, output_file="results/speakers_linkedin.json"):
    speakers = extract_speakers_from_luma(event_url)
    results = []
    for name in speakers:
        linkedin_url = google_search_linkedin_profile(name)
        results.append({"name": name, "linkedin": linkedin_url})
        print(f"{name}: {linkedin_url}")
    # Ensure results dir exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved results to {output_file}")


if __name__ == "__main__":
    # Example usage
    luma_event_url = "https://lu.ma/r8t4o2jr"
    find_speakers_linkedin(luma_event_url)
