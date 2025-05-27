# Luma Event Finder

A Python sample code that automatically searches and extracts event information from Luma (lu.ma) based on user preferences and requirements.

## Overview

This script uses browser automation to search for events on Luma's platform, extract detailed information about events, speakers, and sponsors, and return the results in a structured JSON format.

## Features

- Automated event discovery based on user preferences
- Detailed event information extraction including:
  - Event title and URL
  - Event date
  - Event sponsors
  - Speaker profiles with:
    - Name, title, and company
    - Bio and image
    - Personal website
  - Sponsor profiles with:
    - Name, title, and company
    - Bio and image
    - Website

## Prerequisites

- Python 3.x
- Playwright
- LangChain
- OpenAI API access (or compatible API endpoint)

## Installation

1. Clone the repository
2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

The script requires the following environment variables:
- API key for the language model
- Base URL for the API endpoint

## Usage

1. Import and initialize the script:
```python
from find_events_luma import event_agent, main
```

2. Set your search parameters:
```python
user_intent = "Your event search intent"
user_location = "Optional: Your preferred location"
user_featured_calendars = "Optional: Specific calendar to search"
user_category = "Optional: Event category"
```

3. Run the script:
```
python3 find_events_luma.py
```

## Output

The script generates a `results.json` file containing:
- Selected event details
- Speaker information
- Sponsor information
- All information is structured in JSON format


## Notes

- The script uses a headless browser for automation
- Results are saved in JSON format for easy parsing
- The script includes a test function for Playwright setup verification