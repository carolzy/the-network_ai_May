# Network AI Clean

A comprehensive AI-powered system for business event recommendations and networking opportunities.

## Project Structure

```
network_ai_clean/
│
├── app.py                      # Main application entry point
├── README.md                   # Project documentation
├── requirements.txt            # Dependencies
├── .env                        # Environment variables
│
├── core/                       # Core functionality
│   ├── flow_controller.py      # User flow management
│   ├── question_engine.py      # AI interaction
│   └── website_analyzer.py     # Website analysis
│
├── events/                     # Event-related functionality
│   ├── event_search_agent.py   # Event search
│   ├── target_events_db.py     # Event database
│   ├── target_events_keywords.py # Keyword extraction
│   └── highlight_prompt.py     # Event highlighting
│
├── data/                       # Data files
│   └── luma_events/            # Event data CSVs
│       ├── luma_filtered_events_with_insights_0520.csv  # Latest event data (May 20, 2025)
│       ├── luma_events_with_insights_0502.csv           # Previous event data (May 2, 2025)
│       └── 10times_events_with_insights.csv             # Additional event data
│
├── prompts/                    # AI prompts
│   ├── target_events_prompt.py # Target events prompt
│   └── tradeshow_search_prompt.py # Tradeshow search prompt
│
├── templates/                  # HTML templates
│   ├── base.html               # Base template
│   ├── business_profile_events_fixed.html # Main event display
│   ├── event_search.html       # Event search interface
│   └── ... (other templates)
│
├── static/                     # CSS and JS files
│   ├── css/                    # Stylesheets
│   └── js/                     # JavaScript files
│
└── scripts/                    # Utility scripts
    ├── start_server.py         # Server startup
    └── start_network_ai_clean.sh # Shell script
```

## Key Components

### Core Components

- **Flow Controller**: Manages the multi-step B2B sales flow, user data, and conversation state
- **Question Engine**: Handles interactions with AI models (Gemini) for generating responses
- **Website Analyzer**: Extracts business information from websites using Playwright and AI

### Event Components

- **Event Search Agent**: Handles event search, processing, and relevance scoring
- **Target Events DB**: Manages storage and retrieval of target events recommendations
- **Target Events Keywords**: Extracts keywords from target events for search and filtering
- **Highlight Prompt**: Contains the prompt for highlighting important entities in event descriptions

### Data

- **Luma Events**: CSV files containing event data from Luma and other sources

## Getting Started

1. Ensure you have Python 3.8+ installed
2. Install dependencies: `pip install -r requirements.txt`
3. Configure your API keys in the `.env` file
4. Start the server: `bash scripts/start_network_ai_clean.sh`
5. Access the application at the URL shown in the console

## Main Features

- Business profile analysis based on user inputs and website data
- Personalized event recommendations based on business profile and goals
- Keyword extraction for targeted event search
- Tradeshow and local event search with relevance scoring
- Event highlighting to identify important information

## API Keys

The application requires the following API keys:
- Gemini API key for AI-powered analysis and generation
- (Optional) Claude API key for additional analysis capabilities

Configure these in the `.env` file.

# Luma Event Finder

A Python script that automatically searches and extracts event information from Luma (lu.ma) based on user preferences and requirements.

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
```python
asyncio.run(main())
```

## Output

The script generates a `results.json` file containing:
- Selected event details
- Speaker information
- Sponsor information
- All information is structured in JSON format

## Error Handling

The script includes error handling for:
- Browser automation issues
- API connection problems
- Data extraction failures

## Dependencies

- `browser-use`: For browser automation
- `langchain_openai`: For language model integration
- `playwright`: For web browser control
- `python-dotenv`: For environment variable management

## Notes

- The script uses a headless browser for automation
- Results are saved in JSON format for easy parsing
- The script includes a test function for Playwright setup verification

## License

[Add your license information here]

## Contributing

[Add contribution guidelines here]
