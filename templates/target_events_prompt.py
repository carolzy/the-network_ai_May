"""
Prompt for generating target events recommendations based on business profile and event goals.
"""

TARGET_EVENTS_PROMPT = """
Based on the business profile and the selected event goals, provide a detailed recommendation for:

1. The types of people/organizations this business should be looking to connect with at events (based on their primary goal of {primary_goal})
2. The types of events (local events or national trade shows) where they are most likely to successfully connect with these targets

Format your response as a clear, concise paragraph that explains:
- Who specifically they should target (e.g., specific types of buyers, business partners, talent, or investors)
- Why these targets are a good match for their business
- What types of events would be most effective for meeting these targets
- Any specific strategies they might use at these events

Keep your response focused, practical, and directly related to their business and goals.

IMPORTANT: Highlight key information using the following format:
- For important sectors/industries: <span class="highlight-sector">sector name</span>
- For product lines: <span class="highlight-product">product name</span>
- For target companies: <span class="highlight-company">company name</span>
- For important events: <span class="highlight-event">event name</span>
- For key speakers/exhibitors: <span class="highlight-person">person name/title</span>

Make sure to highlight at least 5-7 important terms in each section of your response.

After providing the general recommendation above, include a section titled "Goal-Targeted Recommendations" with specific advice for each of their selected goals. Format each goal recommendation as a separate section with a clear heading:

If "find_buyers" is one of their goals, include:
<h2 class="section-title">Goal-Targeted Recommendations</h2>

<h3>For Finding Buyers/Users</h3>
<p>Specifically, for the founder of this business to meet future buyers - describe what are the best events that are most likely for them to meet many potential customers together. Include 2-3 specific types of events and explain why these would be effective for connecting with buyers in their industry. Highlight specific event names, companies, and sectors that would be most relevant.</p>

<p>Categorize the types of events in bullet points by the type of attendees who will typically attend these events. For example:</p>
<ul>
<li>Contact center and customer support service related events</li>
<li>Consumer hardware and edge device conferences</li>
<li>Industry-specific technology showcases</li>
</ul>
<p>Make these categories specific to the business profile and ensure they represent different segments of potential buyers.</p>

If "recruit_talent" is one of their goals, include:
<h3>For Recruiting Talent</h3>
<p>Specifically, for the founder of this business to recruit talent - describe what type of events they should attend to find qualified candidates. Include advice on how to position their company at these events to attract the right talent, and which types of events tend to draw the specific skill sets they might need. Highlight specific job titles, skill sets, and relevant recruitment events.</p>

<p>Categorize the types of events in bullet points by the type of attendees who will typically attend these events. For example:</p>
<ul>
<li>Technical conferences attracting AI/ML engineers and data scientists</li>
<li>University career fairs at top computer science programs</li>
<li>Industry-specific hackathons and coding competitions</li>
</ul>
<p>Make these categories specific to the talent needs in the business profile.</p>

If "business_partners" is one of their goals, include:
<h3>For Meeting Business Partners</h3>
<p>For them to meet future business partners, first list what makes a good business partner for this specific company based on their profile, then suggest what types of events would be the best to meet those potential partners. Include advice on how to identify complementary businesses at events. Highlight specific partner types, complementary industries, and relevant partnership events.</p>

<p>Categorize the types of events in bullet points by the type of attendees who will typically attend these events. For example:</p>
<ul>
<li>Industry alliance and ecosystem partnership events</li>
<li>Technology integration and API-focused conferences</li>
<li>Channel partner and reseller networking events</li>
</ul>
<p>Make these categories specific to the partnership needs in the business profile.</p>

If "investors" is one of their goals, include:
<h3>For Connecting with Investors</h3>
<p>For connecting with strategic investors, describe the specific types of investment-focused events that would be most appropriate for their business stage and industry. Include advice on how to prepare for investor conversations at these events and what materials they should bring. Highlight specific investor types, investment firms, and relevant investment events.</p>

<p>Categorize the types of events in bullet points by the type of attendees who will typically attend these events. For example:</p>
<ul>
<li>Venture capital pitch events and startup showcases</li>
<li>Industry-specific investment forums and summits</li>
<li>Corporate venture capital networking events</li>
</ul>
<p>Make these categories specific to the investment needs and stage of the business in the profile.</p>

If "networking" is one of their goals, include:
<h3>For General Networking</h3>
<p>For general networking purposes, suggest diverse event types that would help them build a well-rounded professional network in their industry. Include advice on how to make the most of these networking opportunities and follow up effectively. Highlight specific networking events, industry associations, and key networking contacts.</p>

<p>Categorize the types of events in bullet points by the type of attendees who will typically attend these events. For example:</p>
<ul>
<li>Industry thought leadership conferences and panels</li>
<li>Professional association meetups and social events</li>
<li>Cross-industry innovation forums and workshops</li>
</ul>
<p>Make these categories specific to the networking needs and industry focus in the business profile.</p>

Make sure to emphasize the recommendations for their primary goal, providing more detailed advice for that section. Remember to highlight important terms throughout your response using the span classes specified above.
"""
