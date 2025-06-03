"""
Simplified prompt for generating UI variables from enhanced_website_analyzer.py results.
This consumes the output from enhanced_website_analyzer.py and generates structured UI data.
"""

def get_ui_generation_prompt(website_analysis_result: dict) -> str:
    """
    Generate the prompt that consumes website analyzer results to create UI variables.
    
    Args:
        website_analysis_result: The complete result from enhanced_website_analyzer.py
        
    Returns:
        The formatted prompt string ready for Gemini API
    """
    
    # Extract the strategic analysis from the website analyzer result
    strategic_analysis = website_analysis_result.get("strategic_analysis", {})
    website_data = website_analysis_result.get("website_data", {})
    customer_intelligence = website_analysis_result.get("customer_intelligence", {})
    
    prompt = f"""
You are a business intelligence analyst. Based on the comprehensive website analysis provided below, generate structured data to power a business networking dashboard UI.

WEBSITE ANALYSIS INPUT:
{website_analysis_result}

Your task is to transform this analysis into UI-ready JSON with the following exact structure:

{{
    "multi_factor_analysis": {{
        "customer_analysis": "Brief analysis of existing customers and patterns from the validated_customers data (2-3 sentences)",
        "market_growth": "Key market growth insights based on the primary_industries (1-2 sentences with growth percentages if possible)"
    }},
    "key_differentiators": [
        {{
            "icon": "🎯",
            "text": "First key differentiator based on the company's unique value proposition"
        }},
        {{
            "icon": "⚡", 
            "text": "Second differentiator (technology, speed, accuracy, etc.)"
        }},
        {{
            "icon": "🌍",
            "text": "Third differentiator (scale, reach, global capabilities, etc.)"
        }},
        {{
            "icon": "🎭",
            "text": "Fourth differentiator (innovation, specialization, etc.)"
        }}
    ],
    "target_customers": [
        // Use the target_recommendations from the website analysis, keeping the same structure
        {{
            "industry": "Industry from target_recommendations",
            "company_name": "Company name from target_recommendations", 
            "size": "Size from target_recommendations",
            "why_good_fit": "Why_good_fit from target_recommendations",
            "website": "Website from target_recommendations"
        }}
        // Include all target_recommendations from the analysis
    ],
    "who_to_target": [
        {{
            "group_title": "Media & Content Companies",
            "group_detail": "Video producers, audiobook publishers, podcasters needing voice technology"
        }},
        {{
            "group_title": "Customer Service Leaders", 
            "group_detail": "Call center managers, CX executives implementing AI solutions"
        }},
        {{
            "group_title": "AI/Tech Developers",
            "group_detail": "Chatbot platforms, e-learning companies integrating voice AI"
        }}
    ],
    "event_strategies": {{
        "find_buyers": {{
            "goal_title": "For Finding Buyers/Users",
            "goal_icon": "💰",
            "event_types": [
                {{
                    "type_title": "Customer Service Events",
                    "type_subtitle": "Call center managers, CX executives",
                    "examples": [
                        "Call & Contact Center Expo",
                        "Genesys/Five9 user conferences", 
                        "Customer Experience summits"
                    ],
                    "why_works": "These managers have voice AI budgets and immediate pain points that your solution addresses"
                }},
                {{
                    "type_title": "Content Creation Conferences",
                    "type_subtitle": "Video producers, e-learning professionals",
                    "examples": [
                        "NAB Show (80,000 attendees)",
                        "ATD International Conference",
                        "Content Marketing World"
                    ],
                    "why_works": "They spend thousands on voice-overs monthly - easy ROI story for voice AI solutions"
                }},
                {{
                    "type_title": "AI Technology Showcases", 
                    "type_subtitle": "Tech leaders, AI developers",
                    "examples": [
                        "AI Summit (25,000 attendees)",
                        "EmTech MIT",
                        "Developer conferences"
                    ],
                    "why_works": "Early adopters who understand the technology value and integration potential"
                }}
            ]
        }},
        "business_partners": {{
            "goal_title": "For Meeting Business Partners",
            "goal_icon": "🤝",
            "event_types": [
                {{
                    "type_title": "API & Integration Events",
                    "type_subtitle": "Developers, platform builders",
                    "examples": [
                        "API World (5,000 developers)",
                        "Platform summit events",
                        "Integration conferences"
                    ],
                    "why_works": "Perfect for finding chatbot platforms, video editing software for integrations"
                }},
                {{
                    "type_title": "Industry Ecosystem Events",
                    "type_subtitle": "Cross-industry partnerships", 
                    "examples": [
                        "SaaS partnership summits",
                        "Technology ecosystem events",
                        "Channel partner meetups"
                    ],
                    "why_works": "Ideal for finding e-learning platforms, customer service solution providers as partners"
                }}
            ]
        }},
        "recruit_talent": {{
            "goal_title": "For Recruiting Talent",
            "goal_icon": "👥",
            "event_types": [
                {{
                    "type_title": "AI/ML Engineering Events",
                    "type_subtitle": "AI engineers, data scientists",
                    "examples": [
                        "PyTorch Conference",
                        "MLOps World",
                        "AI Engineering summits"
                    ],
                    "why_works": "Target top AI talent working on cutting-edge voice and ML technologies"
                }}
            ]
        }},
        "investors": {{
            "goal_title": "For Connecting with Investors",
            "goal_icon": "💼",
            "event_types": [
                {{
                    "type_title": "AI/Enterprise Investment Events",
                    "type_subtitle": "Enterprise-focused VCs, AI investors",
                    "examples": [
                        "AI/Enterprise pitch events",
                        "SaaS investment forums",
                        "B2B startup showcases"
                    ],
                    "why_works": "VCs focused on enterprise AI solutions with proven market demand and clear ROI"
                }}
            ]
        }},
        "networking": {{
            "goal_title": "For General Networking", 
            "goal_icon": "🌐",
            "event_types": [
                {{
                    "type_title": "Industry Leadership Events",
                    "type_subtitle": "Thought leaders, industry executives",
                    "examples": [
                        "Industry association meetups",
                        "Executive networking events",
                        "Innovation forums"
                    ],
                    "why_works": "Build relationships with industry leaders who can provide strategic guidance and connections"
                }}
            ]
        }}
    }},
    "specific_events": [
        {{
            "title": "NAB Show 2025",
            "meta": "April 2025 • Las Vegas, NV • Trade Show",
            "description": "Perfect for showcasing voice technology to media and content creation professionals. Expected 80,000+ attendees including video producers, broadcasters, and content creators who need voice AI solutions.",
            "primary_goal": "find_buyers"
        }},
        {{
            "title": "Call & Contact Center Expo 2025",
            "meta": "May 2025 • Chicago, IL • Conference", 
            "description": "Connect with customer service executives and call center managers looking for AI automation solutions. Focus on voice AI for customer interactions and support automation.",
            "primary_goal": "find_buyers"
        }}
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