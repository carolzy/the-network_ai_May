event_task_prompt = """
You are a helpful assistant that helps me find events on lu.ma with given information:

User Intent: {user_intent}

User Location: {user_location}

User Featured Calendars: {user_featured_calendars}

User Category: {user_category}

Enumerate all the events in the 'Discover Events' page.

In the 'Discover Events' page, you can filter events by popular, location, category, and featured calendars.

If I am not providing a location, you should use the location of the user, otherwise you should use the location I provided.

If I am provideing a Featured Calendars, you should use the Featured Calendars I provided.

If I am providing a category, you should use the current category in the 'Discover Events' page, otherwise you should use the category I provided.

As for the popular events in the 'Discover Events' page,Open 'View All' to list all the events to get all available events.

Several steps to find all related events:
  1. Continue scroll down to get all the events.
  2. Click on the event to open the event page. Pick the event(s) likely to be relevant to the user intent based on the event title, event description, event speakers, event sponsors, event category, event location, event date, event time.
  3. Repeat the process until all events are examined
  4. Store all the events in a list.

Select the Top 1 event(s) most likely to be relevant to the user intent among all the selected events.

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
