#!/usr/bin/env python3

import re

# Read the backup file which should have the correct implementation
with open('core/flow_controller.py.backup', 'r') as f:
    content = f.read()

# Extract the correct implementation of generate_target_events_recommendation
generate_method_pattern = r'async def generate_target_events_recommendation\(self\):.*?(?=\s{4}async def|$)'
generate_method_match = re.search(generate_method_pattern, content, re.DOTALL)

if generate_method_match:
    generate_method = generate_method_match.group(0)
    
    # Find the determine_follow_up_question method
    determine_method_pattern = r'async def determine_follow_up_question\(self\):.*?(?=\s{4}async def|$)'
    determine_method_match = re.search(determine_method_pattern, content, re.DOTALL)
    
    if determine_method_match:
        determine_method = determine_method_match.group(0)
        
        # Create the corrected content
        with open('core/flow_controller.py', 'r') as f:
            current_content = f.read()
        
        # Replace the broken methods with the correct ones
        pattern = r'async def generate_target_events_recommendation\(self\):.*?(?=\s{4}async def|$)'
        corrected_content = re.sub(pattern, generate_method, current_content, flags=re.DOTALL)
        
        # Write the corrected content back to the file
        with open('core/flow_controller.py', 'w') as f:
            f.write(corrected_content)
        
        print("Successfully restored the generate_target_events_recommendation method")
    else:
        print("Could not find the determine_follow_up_question method")
else:
    print("Could not find the generate_target_events_recommendation method")
