# Event Search Tools

This directory contains tools for searching and retrieving event information from Luma.

## Files

- `event_search.py`: The main implementation and entry point with the `EventSearch` class
- `find_events_luma.py`: Legacy interface for backward compatibility (uses `event_search.py` internally)
- `prompts.py`: Contains prompts used for event search and extraction

## Usage

### Main Implementation (Recommended)

```python
from event_search import EventSearch

# Initialize the search
event_search = EventSearch(api_key="your-api-key")

# Search for events
events = await event_search.search_events(
    query="AI and Machine Learning",
    location="San Francisco",
    category="Technology",
    max_results=5
)

# Process results
for event in events:
    print(f"Title: {event.title}")
    print(f"Date: {event.date}")
    print(f"Location: {event.location}")
    print(f"URL: {event.url}")
    if event.speakers:
        print("Speakers:")
        for speaker in event.speakers:
            print(f"- {speaker['name']} ({speaker['title']} at {speaker['company']})")
```

### Legacy Interface (For Backward Compatibility)

```python
from find_events_luma import find_events

# Search for events
find_events(
    user_intent="I want to find an event about AI Agent",
    user_location="San Francisco",
    user_category="Technology",
    output_file="results/event_results.json"
)
```

## Features

- Search events by query, location, and category
- Extract detailed event information including:
  - Title
  - Date
  - Location
  - URL
  - Speakers (name, title, company)
- Save results to JSON file
- Browser automation for event search and extraction
- Error handling and retry mechanisms

## Requirements

- Python 3.7+
- OpenAI API key
- Required packages (see requirements.txt):
  - browser-use
  - pydantic
  - playwright
  - langchain

## Configuration

The tools use the following environment variables:
- `OPENAI_API_KEY`: Your OpenAI API key

## Output Format

Events are saved in JSON format with the following structure:

```json
[
  {
    "title": "Event Title",
    "date": "Event Date",
    "location": "Event Location",
    "url": "Event URL",
    "speakers": [
      {
        "name": "Speaker Name",
        "title": "Speaker Title",
        "company": "Speaker Company"
      }
    ]
  }
]
```

## Notes

- The script uses a headless browser for automation
- Results are saved in JSON format for easy parsing
- The script includes a test function for Playwright setup verification
- For new code, use `event_search.py` directly
- `find_events_luma.py` is maintained for backward compatibility