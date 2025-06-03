import csv
import re
import os

def clean_text(text):
    if not text:
        return ''
    # Remove Markdown images: ![Alt](URL)
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    # Remove Markdown links but keep link text: [Text](URL) => Text
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
    # Remove excessive newlines and backslashes
    text = text.replace('\\', ' ')
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    # Remove emojis (optional, can be commented out)
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
    return text.strip()

def clean_csv(input_path, output_path):
    with open(input_path, 'r', encoding='utf-8') as infile, \
         open(output_path, 'w', encoding='utf-8', newline='') as outfile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in reader:
            clean_row = {k: clean_text(v) for k, v in row.items()}
            writer.writerow(clean_row)

if __name__ == "__main__":
    input_csv = "/Users/kk/Documents/the-network_ai_May_chen_may/data/luma_events/luma_filtered_events_with_insights_0520.csv"
    output_csv = "/Users/kk/Documents/the-network_ai_May_chen_may/data/luma_events/luma_filtered_events_with_insights_0520_cleaned.csv"
    # Ensure output dir exists
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    clean_csv(input_csv, output_csv)
    print(f"Cleaned CSV saved to {output_csv}")
