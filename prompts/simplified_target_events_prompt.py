"""
Simplified prompt for generating UI variables from enhanced_website_analyzer.py results.
This consumes the output from enhanced_website_analyzer.py and generates structured UI data.
"""

def get_ui_generation_prompt(website_analysis_result: dict) -> str:
    """
    Generate the prompt that consumes website analyzer results to create UI variables.
    The prompt dynamically adapts event strategies based on the company's industry and offerings.
    
    Args:
        website_analysis_result: The complete result from enhanced_website_analyzer.py
        
    Returns:
        The formatted prompt string ready for Gemini API
    """
    
    # Extract the strategic analysis from the website analyzer result
    strategic_analysis = website_analysis_result.get("strategic_analysis", {})
    website_data = website_analysis_result.get("website_data", {})
    customer_intelligence = website_analysis_result.get("customer_intelligence", {})
    
    # Extract company name, URL, and industry information for more targeted recommendations
    company_name = website_data.get("title", "").split("|")[0].strip() if "|" in website_data.get("title", "") else website_data.get("title", "")
    company_url = website_data.get("url", "")
    company_description = website_data.get("description", "")
    industries_served = strategic_analysis.get("primary_industries", [])
    company_features = strategic_analysis.get("key_features", [])
    
    prompt = f"""
You are a business intelligence analyst. Based on the provided information, generate structured data to power a business networking dashboard UI. IMPORTANT: You must include ALL the requested fields in your response, even if you have minimal information about the company.

WEBSITE ANALYSIS INPUT:
{website_analysis_result}

COMPANY CONTEXT:
Company: {company_name}
Website: {company_url}
Industries: {', '.join(industries_served) if industries_served else 'Unknown'}
Description: {company_description}

Your task is to transform this analysis into UI-ready JSON with the following exact structure.

REQUIRED OUTPUT FORMAT:
Return a JSON object with the following structure. ALL fields are required, even with minimal information:
{
    "multi_factor_analysis": {
        "customer_analysis": "Brief analysis of the company's customer base and market position",
        "market_growth": "Brief assessment of the company's market growth potential"
    },
    "key_differentiators": [
        {
            "icon": "💡", 
            "text": "First differentiator (unique value proposition)"
        },
        {
            "icon": "⚡", 
            "text": "Second differentiator (technology, speed, accuracy, etc.)"
        },
        {
            "icon": "🌍",
            "text": "Third differentiator (scale, reach, global capabilities, etc.)"
        },
        {
            "icon": "🎭",
            "text": "Fourth differentiator (innovation, specialization, etc.)"
        }
    ],
    "target_customers": [
        // REQUIRED: Include at least 2-3 target customer examples, even if you have to make educated guesses
        {
            "industry": "Industry name",
            "company_name": "Example company name", 
            "size": "Company size (small, medium, large)",
            "why_good_fit": "Why this company would be a good fit as a customer",
            "website": "example.com"
        }
        // If website analysis provided target_recommendations, use those instead of creating examples
    ],
    "who_to_target": [
        // REQUIRED: Generate 2-3 target groups that would benefit from this company's offerings
        // Each group MUST include:
        {
            "group_title": "Decision Makers", 
            "group_detail": "Detailed description of this group and why they would be interested"
        },
        {
            "group_title": "Industry Professionals",
            "group_detail": "Detailed description of this group and why they would be interested"
        }
        // Add at least one more target group
    ],
    "event_strategies": {  
        "find_buyers": {  
            "goal_title": "For Finding Buyers/Users", 
            "goal_icon": "💰",  
            "strategy": "Attend industry-specific trade shows and conferences where potential customers gather to showcase product demos and collect leads." 
        },
        "business_partners": {
            "goal_title": "For Meeting Business Partners", 
            "goal_icon": "🤝",  
            "strategy": "Participate in conferences and integration events to connect with potential partners and build ecosystem relationships." 
        },
        "recruit_talent": {
            "goal_title": "For Recruiting Talent", 
            "goal_icon": "👥",  
            "strategy": "Attend university career fairs and industry meetups to connect with professionals who have the specific skills needed for your team." 
        },
        "investors": {
            "goal_title": "For Connecting with Investors", 
            "goal_icon": "💼",  
            "strategy": "Participate in venture capital conferences and pitch events to connect with investors who specialize in your industry." 
        },
        "networking": {
            "goal_title": "For General Networking", 
            "goal_icon": "🌐",  
            "strategy": "Join industry mixers and professional meetups to build relationships with peers, stay updated on trends, and increase visibility." 
        }
    },
    "specific_events": [
        // REQUIRED: Include at least 3 specific events relevant to the company's goals
        // Each event MUST include all these fields:
        {
            "title": "Industry Conference 2025",
            "meta": "Month 2025 • City, State • Event Type",
            "description": "Brief description of why this event is relevant to the company's goals and who they might meet there.",
            "primary_goal": "find_buyers"  // Must be one of: find_buyers, business_partners, recruit_talent, investors, networking
        },
        {
            "title": "Technology Expo 2025",
            "meta": "Month 2025 • City, State • Expo", 
            "description": "Brief description of why this event is relevant to the company's goals and who they might meet there.",
            "primary_goal": "business_partners"
        },
        {
            "title": "Industry Summit 2025",
            "meta": "Month 2025 • City, State • Summit", 
            "description": "Brief description of why this event is relevant to the company's goals and who they might meet there.",
            "primary_goal": "networking"
        }
    ]
}}

INSTRUCTIONS:
1. Use the validated_customers from the strategic_analysis to inform the multi_factor_analysis
2. Extract key_differentiators from the company's unique value propositions found in the analysis
3. Use the target_recommendations directly for the target_customers array (all of them)
4. Create who_to_target based on the primary_industries and target_audience data
5. Generate event_strategies that are specific to this company's industry focus and customer base
6. Recommend specific_events that would be most relevant for this particular business

Base all recommendations on the actual data from the website analysis - use the company's real industries, customers, and value propositions to make targeted suggestions.

Return only the JSON object, no additional text.
"""

    return prompt