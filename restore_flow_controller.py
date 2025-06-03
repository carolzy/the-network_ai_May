#!/usr/bin/env python3

with open('core/flow_controller.py', 'r') as f:
    lines = f.readlines()

# Find the indentation error and fix it
for i, line in enumerate(lines):
    if "async def generate_target_events_recommendation" in line:
        start_index = i
    if "def determine_follow_up_question" in line and not line.startswith("    async"):
        lines[i] = "    async def determine_follow_up_question(self):\n"
        break

with open('core/flow_controller.py', 'w') as f:
    f.writelines(lines)

print("Successfully fixed indentation error in flow_controller.py")
