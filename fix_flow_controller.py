#!/usr/bin/env python3

import re

with open('core/flow_controller.py', 'r') as f:
    content = f.read()

# Find the duplicate method and remove it
pattern = r'"""Generate a recommendation for target events based on business profile and goals\.""".*?def determine_follow_up_question'
replacement = 'def determine_follow_up_question'
new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

with open('core/flow_controller.py', 'w') as f:
    f.write(new_content)

print("Successfully removed duplicate implementation of generate_target_events_recommendation")
