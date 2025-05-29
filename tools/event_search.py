"""
Event Search Module using browser-use library
"""

import os
import json
import asyncio
from typing import Optional, Dict, List
from pydantic import BaseModel, SecretStr
from langchain_openai import ChatOpenAI
from browser_use import Agent
from browser_use.browser import BrowserSession, BrowserProfile
from dotenv import load_dotenv
from prompts import event_search_prompt, event_details_prompt

# Load environment variables
load_dotenv()

class EventDetails(BaseModel):
    """Model for event details"""
    title: str
    url: str
    date: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    speakers: Optional[List[Dict]] = None
    sponsors: Optional[List[Dict]] = None
    category: Optional[str] = None
    price: Optional[str] = None

class EventSearch:
    def __init__(
        self,
        api_key: str,
        model_name: str = "DeepSeek-V3-0324"
    ):
        """Initialize the event search with browser-use configuration"""
        # Set OpenAI API key for memory
        os.environ["OPENAI_API_KEY"] = api_key
        
        self.browser_profile = BrowserProfile(
            executable_path=(
                '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
            ),
            user_data_dir='~/.config/browseruse/profiles/default',
            headless=False,
        )
        self.browser_session = BrowserSession(
            browser_profile=self.browser_profile
        )
        
        self.llm = ChatOpenAI(
            base_url="https://api.sambanova.ai/v1",
            api_key=SecretStr(api_key),
            model=model_name,
            temperature=0.0,
        )

    async def search_events(
        self,
        query: str,
        location: Optional[str] = None,
        category: Optional[str] = None,
        max_results: int = 5
    ) -> List[EventDetails]:
        """
        Search for events using browser-use library
        
        Args:
            query: Search query for events
            location: Optional location filter
            category: Optional category filter
            max_results: Maximum number of results to return
            
        Returns:
            List of EventDetails objects
        """
        task_prompt = event_search_prompt.format(
            query=query,
            location=location if location else "Any",
            category=category if category else "Any",
            max_results=max_results
        )
        
        agent = Agent(
            task=task_prompt,
            llm=self.llm,
            use_vision=False,  # Disable vision for DeepSeek model
            enable_memory=True,
            save_conversation_path="tools/logs/conversation",
            initial_actions=[{'open_tab': {'url': "https://lu.ma/discover"}}],
        )

        await agent.browser_session.start()
        history = await agent.run()
        
        # Parse the results from the agent's response
        events = self._parse_agent_response(history.final_result())
        return events

    async def get_event_details(self, url: str) -> EventDetails:
        """
        Get detailed information about a specific event
        
        Args:
            url: URL of the event to get details for
            
        Returns:
            EventDetails object with complete information
        """
        agent = Agent(
            task=event_details_prompt,
            llm=self.llm,
            use_vision=False,  # Disable vision for DeepSeek model
            enable_memory=True,
            save_conversation_path="tools/logs/conversation",
            initial_actions=[{'open_tab': {'url': url}}],
        )

        await agent.browser_session.start()
        history = await agent.run()
        
        # Parse the results from the agent's response
        try:
            event_data = json.loads(history.final_result())
            return EventDetails(**event_data)
        except json.JSONDecodeError:
            return EventDetails(title="Error", url=url)

    def _parse_agent_response(self, response: str) -> List[EventDetails]:
        """Parse the agent's response into EventDetails objects"""
        try:
            events_data = json.loads(response)
            return [EventDetails(**event) for event in events_data]
        except json.JSONDecodeError:
            # If the response isn't valid JSON, try to extract structured data
            # This is a fallback for when the agent returns formatted text
            events = []
            # Add parsing logic here if needed
            return events

async def main():
    """Example usage of the EventSearch class"""
    api_key = os.getenv(
        "OPENAI_API_KEY",
        "042ca35c-beaf-4f5b-8033-9170556e5251"
    )
    event_search = EventSearch(api_key)
    
    events = await event_search.search_events(
        query="AI and Machine Learning",
        location="San Francisco",
        category="Technology",
        max_results=3
    )
    
    # Print results
    for event in events:
        print(f"\nEvent: {event.title}")
        print(f"Date: {event.date}")
        print(f"Location: {event.location}")
        print(f"URL: {event.url}")
        if event.speakers:
            print("\nSpeakers:")
            for speaker in event.speakers:
                print(
                    f"- {speaker['name']} "
                    f"({speaker['title']} at {speaker['company']})"
                )

    # Save results to file
    output_dir = "results"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "event_results.json")
    with open(output_file, "w") as f:
        json.dump([event.dict() for event in events], f, indent=2)
    print(f"\nResults saved to {output_file}")

if __name__ == "__main__":
    asyncio.run(main()) 