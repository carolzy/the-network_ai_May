import asyncio
import os
import sys
import json

from langchain_openai import ChatOpenAI
from browser_use import Agent
from browser_use.browser import BrowserSession
from playwright.sync_api import sync_playwright

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv

load_dotenv()

def test_playwright():
	try:
		with sync_playwright() as p:

			browser = p.chromium.launch(headless=False)
			context = browser.new_context()
			page = context.new_page()
			page.goto("https://www.google.com")
			print("Title:", page.title())
			browser.close()
		print("Playwright is working correctly!")

	except Exception as e:
		print("Error:", e)
		print("Playwright might not be working as expected.")

# Initialize the model
llm = ChatOpenAI(
	base_url = "https://api.sambanova.ai/v1",
	api_key="042ca35c-beaf-4f5b-8033-9170556e5251",
	model='DeepSeek-V3-0324',
	temperature=0.0,
)

# planner_llm = ChatOpenAI(
# 	base_url = "https://api.sambanova.ai/v1",
# 	api_key="042ca35c-beaf-4f5b-8033-9170556e5251",
# 	model='DeepSeek-R1',
# 	temperature=0.0,
# )

# messages=[{"role":"system","content":"You are a helpful assistant"},{"role":"user","content":"Hello"}]
# ai_msg = llm.invoke(messages)
# print(ai_msg.content)
# task = 'Go to kayak.com and find the cheapest one-way flight from Zurich to San Francisco in 3 weeks.'
event_task = """
You are a helpful assistant that helps me find events on luma with given information:

User Intent: {user_intent}

User Location: {user_location}

User Featured Calendars: {user_featured_calendars}

User Category: {user_category}

Enumerate all the events in the 'Explore Events' tab.

The events list is in the 'Explore Events' tab is most likely the popular events in your current location. 

Frist, Open 'View All' to list all the events to get the latest events. Continue scroll down to get all the events.
Click on the event to open the event page. Pick Top 1 event(s) most likely to be relevant to the user intent based on the event title, event description, event speakers, event sponsors, event category, event location, event date, event time.

If I am not providing a location, you should use the location of the user, otherwise you should use the location I provided, 
list all the events to get the latest events in the provided location (continue scroll down to get all the events if needed).
Pick Top 1 event(s) most likely to be relevant to the user intent.

If I am provideing a Featured Calendars, you should use the Featured Calendars I provided, 
list all the events to get the latest events in the provided location (continue scroll down to get all the events if needed).
Pick Top 1 event(s) most likely to be relevant to the user intent.

If I am providing a category, you should use the current category in the 'Explore Events' tab, otherwise you should use the category I provided,
list all the events to get the latest events in the provided location (continue scroll down to get all the events if needed).
Pick Top 1 event(s) most likely to be relevant to the user intent.

Open the selected event(s) and gather all the following information:

Event Title 
Event URL (prefer to find the correct event URL if the original one is corrupted)
Event Date
Event Sponsor (companies) 
Event Speakers and Speaker Titles, the names of the companies they work for 

For each speakers, just visit the speaker's profile page if it is available (with speaker's personal website), and gather the following information:
Speaker Name
Speaker Title
Speaker Company
Speaker Bio
Speaker Image
Speaker Website
Speaker Profile (if Linkedin is available, then get the information from the linkedin page, if there is a login required, then skip it)

For each sponsor, just visit the sponsor's profile page if it is available (with sponsor's website), and gather the following information:
Sponsor Name
Sponsor Title
Sponsor Company
Sponsor Bio
Sponsor Image
Sponsor Website

If there is an error, return 'Error'.

return the results in with json format.

"""


initial_actions = [
	{'open_tab': {'url': "https://lu.ma/discover"}},
	]

event_agent = Agent(task=event_task, 
					llm=llm, 
					# planner_llm=planner_llm,  
					use_vision=False,
					save_conversation_path="logs/conversation",
					initial_actions=initial_actions,
					# enable_memory=True,
					)


async def main():
	await event_agent.browser_session.start()

	# Example of accessing history
	history = await event_agent.run()

	# Access (some) useful information
	# print(history.urls())              # List of visited URLs
	# print(history.screenshots())       # List of screenshot paths
	# print(history.action_names())     # Names of executed actions
	# print(history.extracted_content()) # Content extracted during execution
	# print(history.errors())         # Any errors that occurred
	# print(history.model_actions())     # All actions with their parameters

	# print(history.final_result())

	# save the final result to a json file
	with open('results.json', 'w') as f:
		# json.dump(history.final_result(), f)
		f.write(history.final_result())

if __name__ == '__main__':

	# import os
	# import openai

	# client = openai.OpenAI(
	# 	api_key="042ca35c-beaf-4f5b-8033-9170556e5251",
	# 	base_url="https://api.sambanova.ai/v1",
	# )

	# response = client.chat.completions.create(
	# 	model="DeepSeek-R1",
	# 	messages=[{"role":"system","content":"You are a helpful assistant"},{"role":"user","content":"Hello"}],
	# 	temperature=0.1,
	# 	top_p=0.1
	# )

	user_intent = "I want to find an event about AI, our company is focused on speech generation."
	user_location = None #"San Francisco"
	user_featured_calendars = None #"AI"
	user_category = None #"AI"

	event_task = event_task.format(user_intent=user_intent, 
					user_location=user_location if user_location else "", 
					user_featured_calendars=user_featured_calendars if user_featured_calendars else "", 
					user_category=user_category if user_category else "")
	
	# print(response.choices[0].message.content)

	asyncio.run(main())
	# test_playwright()




		