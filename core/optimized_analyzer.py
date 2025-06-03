"""
Optimized version of the website analyzer with parallel API calls.
This module contains an optimized version of the analyze_website function
that runs API calls in parallel with browser scraping.
"""

import asyncio
import logging
import json
import re
import os
from typing import Dict, List, Any, Optional, Tuple

# Import the necessary functions from the original analyzer
from core.enhanced_website_analyzer import (
    find_relevant_pages, 
    extract_customer_data, 
    analyze_with_customer_intelligence,
    generate_ui_data_from_analysis,
    format_target_recommendations,
    logger
)


# Import Playwright for web scraping
from playwright.async_api import async_playwright

async def analyze_website_parallel(url: str) -> Optional[Dict[str, Any]]:
    """
    Enhanced website analysis that includes customer intelligence gathering.
    This optimized version runs API calls in parallel with browser scraping.
    """
    try:
        logger.info(f"Starting optimized parallel analysis for: {url}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
            )
            page = await context.new_page()
            
            # First, analyze the main page
            logger.info("Analyzing main page...")
            await page.goto(url, wait_until="domcontentloaded", timeout=90000)  # Changed from networkidle to domcontentloaded
            
            # Extract basic website data
            title = await page.title()
            description = await page.evaluate("""
                () => {
                    const metaDescription = document.querySelector('meta[name="description"]');
                    return metaDescription ? metaDescription.getAttribute('content') : '';
                }
            """)
            
            # Find customer-related pages
            logger.info("Scanning for customer-related and content pages...")
            relevant_pages = await find_relevant_pages(page, url)
            
            # Extract customer data from relevant pages
            all_customer_data = []
            
            # Analyze customer pages
            for customer_page_url in relevant_pages["customer_pages"]:
                try:
                    logger.info(f"Analyzing customer page: {customer_page_url}")
                    customer_data = await extract_customer_data(page, customer_page_url)
                    if customer_data["customers"] or customer_data["industries"]:
                        all_customer_data.append(customer_data)
                    await asyncio.sleep(1)  # Be respectful with requests
                except Exception as e:
                    logger.warning(f"Failed to analyze customer page {customer_page_url}: {e}")
                    continue
            
            # Also check content pages for customer mentions
            for content_page_url in relevant_pages["content_pages"]:
                try:
                    logger.info(f"Analyzing content page: {content_page_url}")
                    customer_data = await extract_customer_data(page, content_page_url)
                    if customer_data["customers"] or customer_data["industries"]:
                        all_customer_data.append(customer_data)
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.warning(f"Failed to analyze content page {content_page_url}: {e}")
                    continue
                    
            # If no customer or content pages were found, analyze the main page
            if len(all_customer_data) == 0:
                logger.info("No customer or content pages found. Analyzing main page for customer information...")
                try:
                    # We're already on the main page, so extract data from it
                    customer_data = await extract_customer_data(page, url)
                    if customer_data["customers"] or customer_data["industries"]:
                        all_customer_data.append(customer_data)
                        
                    # Also try to find and analyze the "about" page if it exists
                    about_page_url = None
                    about_links = await page.evaluate("""
                        () => {
                            const aboutLinks = [];
                            document.querySelectorAll('a').forEach(link => {
                                const text = link.textContent.trim().toLowerCase();
                                const href = link.href;
                                if ((text.includes('about') || href.includes('about')) && 
                                    href && !href.startsWith('#') && !href.startsWith('javascript:')) {
                                    aboutLinks.push(href);
                                }
                            });
                            return aboutLinks;
                        }
                    """)
                    
                    if about_links and len(about_links) > 0:
                        about_page_url = about_links[0]
                        logger.info(f"Found about page: {about_page_url}")
                        await page.goto(about_page_url, wait_until="domcontentloaded", timeout=60000)  # Changed from networkidle
                        about_data = await extract_customer_data(page, about_page_url)
                        if about_data["customers"] or about_data["industries"]:
                            all_customer_data.append(about_data)
                except Exception as e:
                    logger.warning(f"Failed to analyze main/about page: {e}")
                    
                # Even if we don't find customer data, create a minimal entry so we have something to analyze
                if len(all_customer_data) == 0:
                    logger.info("Creating minimal customer data from main page content")
                    all_customer_data.append({
                        "customers": [],
                        "industries": [],
                        "caseStudies": [],
                        "textSample": await page.evaluate('() => document.body.textContent')
                    })
            
            # Basic website data structure
            website_data = {
                "url": url,
                "title": title,
                "description": description,
                "main_features": [],  # Would be populated by full analysis
                "target_audience": "",  # Would be populated by full analysis
                "industries": []  # Would be populated by full analysis
            }
            
            # Start the API call in parallel with any remaining browser operations
            logger.info("Starting strategic insights generation in parallel...")
            strategic_analysis_task = asyncio.create_task(
                analyze_with_customer_intelligence(website_data, all_customer_data)
            )
            
            # Close the browser since we're done with scraping
            await browser.close()
            
            # Now await the strategic analysis task to complete
            logger.info("Waiting for strategic insights generation to complete...")
            strategic_analysis = await strategic_analysis_task
            
            # Combine everything into final result
            result = {
                "website_data": website_data,
                "customer_intelligence": {
                    "pages_analyzed": len(all_customer_data),
                    "customer_pages_found": relevant_pages["customer_pages"],
                    "content_pages_found": relevant_pages["content_pages"],
                    "raw_customer_data": all_customer_data
                },
                "strategic_analysis": strategic_analysis
            }
            
            logger.info("Enhanced parallel analysis complete!")
            return result
            
    except Exception as e:
        logger.error(f"Error in enhanced website analysis: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None

async def analyze_website_with_ui_data_parallel(url: str) -> Optional[Dict[str, Any]]:
    """
    Complete website analysis that generates both strategic analysis AND UI data.
    This optimized version runs API calls in parallel with browser scraping.
    
    Args:
        url: The URL of the website to analyze
        
    Returns:
        A dictionary containing all analysis results plus UI-ready data
    """
    try:
        logger.info(f"Starting complete parallel analysis for: {url}")
        
        # Step 1: Run the optimized enhanced website analysis
        website_analysis_result = await analyze_website_parallel(url)
        
        if not website_analysis_result:
            logger.error("Failed to get website analysis result")
            return None
        
        # Step 2: Generate UI-specific data from the analysis
        logger.info("Generating UI data from analysis...")
        ui_data = await generate_ui_data_from_analysis(website_analysis_result)
        
        # Step 3: Combine everything
        final_result = {
            **website_analysis_result,  # All original analysis
            "ui_data": ui_data          # UI-specific structured data
        }

        # If analyzing ElevenLabs, inject manual target customers
        if "elevenlabs" in url.lower():
            import json
            manual_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ui_data_elevenlabs_manual.json")
            if os.path.exists(manual_path):
                with open(manual_path, "r") as f:
                    manual_data = json.load(f)
                if "ui_data" in final_result:
                    final_result["ui_data"]["target_customers"] = manual_data.get("target_customers", [])

        import os
        from datetime import datetime
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        os.makedirs(data_dir, exist_ok=True)
        # Try to get company name from website_analysis_result or ui_data
        company = None
        if "company_name" in website_analysis_result:
            company = website_analysis_result["company_name"]
        elif "ui_data" in final_result and "company_name" in final_result["ui_data"]:
            company = final_result["ui_data"]["company_name"]
        elif "title" in website_analysis_result:
            company = website_analysis_result["title"]
        else:
            company = "unknown"
            logger.warning("No company_name found in analysis result or ui_data; using 'unknown' in filename.")
        # Sanitize company for filename
        import re
        company_safe = re.sub(r'[^a-zA-Z0-9_-]', '_', str(company))[:32]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        save_path = os.path.join(data_dir, f"enhanced_analysis_{company_safe}_{timestamp}.json")
        with open(save_path, 'w') as f:
            json.dump(final_result, f, indent=2)
        # Also save to core/ui_data.json if UI data is present (existing behavior)
        if "ui_data" in final_result and final_result["ui_data"]:
            # Always save ui_data.json in the root directory (same as app.py)
            import os
            app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            ui_data_path = os.path.join(app_root, "ui_data.json")
            with open(ui_data_path, "w") as f:
                json.dump(final_result["ui_data"], f, indent=2)

        logger.info("Complete parallel analysis with UI data finished!")
        return final_result
        
    except Exception as e:
        logger.error(f"Error in complete website analysis: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None

async def main_with_ui_parallel(url: str):
    """Main function that generates both analyses and UI data using parallel processing."""
    try:
        # Run the complete analysis with UI data
        result = await analyze_website_with_ui_data_parallel(url)
        
        if not result:
            print("Analysis failed. Check logs for details.")
            return
        
        # Print formatted output
        print(format_target_recommendations(result))
        
        if "ui_data" in result and result["ui_data"]:
            print("\n UI data ready! Saved to ui_data.json")
            print(" Complete analysis saved to complete_analysis_report.json")
        else:
            print("\n UI data generation failed")
            print(f"Error: {result.get('ui_data', {}).get('error', '')}")
            
    except Exception as e:
        print(f"Error in main function: {str(e)}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        url = sys.argv[1]
        asyncio.run(main_with_ui_parallel(url))
    else:
        print("Usage: python optimized_analyzer.py <url>")
