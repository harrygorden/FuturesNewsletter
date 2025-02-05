import anvil.google.auth, anvil.google.drive, anvil.google.mail
from anvil.google.drive import app_files
import anvil.secrets
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.server
import spacy
import re
import datetime  # <--- Added datetime import for timestamp handling

# This module is part of our newsletter processing pipeline.
# It runs on the Anvil server and is responsible for optimizing the extracted newsletter text,
# preparing it for ingestion by AI models. The optimization process may include cleaning,
# formatting, and standardizing the newsletter data.
#
# Functions in this module can be invoked via @anvil.server.callable from client-side code.
#
# To allow anvil.server.call() to call functions here, we mark
# them with @anvil.server.callable.
# Here is an example - you can replace it with your own:
#
# @anvil.server.callable
# def say_hello(name):
#   print("Hello, " + name + "!")
#   return 42
#

# Initialize spaCy model for newsletter analysis
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    import spacy.cli
    spacy.cli.download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")
from spacy.tokens import Doc
if not Doc.has_extension("support_resistance"):
    Doc.set_extension("support_resistance", default=[])

# Register the custom pipeline component with a name using the decorator
@spacy.Language.component("support_resistance_detector")
def support_resistance_detector(doc):
    """Custom spaCy pipeline component to detect support/resistance levels."""
    pattern = r"(\d+\.\d+)\s*(?:support|resistance)"
    matches = re.findall(pattern, doc.text, flags=re.IGNORECASE)
    doc._.support_resistance = matches
    return doc

# Add the custom component by its name instead of passing the function
if "support_resistance_detector" not in nlp.pipe_names:
    nlp.add_pipe("support_resistance_detector", last=True)

def clean_text(text):
    """Cleans the text by removing URLs and timestamps."""
    text = re.sub(r'https?://\S+', '', text)   # Remove URLs
    text = re.sub(r'\d{1,2}:\d{2}\s*[AP]M\s*[A-Z]{2,}', '', text)  # Remove timestamps
    return text

def segment_text(text):
    """Discards and preserves sections for analysis.
    Discards content from 'The Run Down on The Level To Level Approach: What, Why, How' up to 'Core Structures/Levels To Engage',
    and extracts the section from 'Core Structures/Levels To Engage' to 'Trade Recap/Education'.
    """
    text_without_discard = re.sub(r'The Run Down on The Level To Level Approach: What, Why, How.*?Core Structures/Levels To Engage',
                                  "Core Structures/Levels To Engage", text, flags=re.DOTALL)
    m = re.search(r'(Core Structures/Levels To Engage.*?Trade Recap/Education)', text_without_discard, flags=re.DOTALL)
    preserved_section = m.group(1) if m else ""
    return text_without_discard, preserved_section

def format_preserved_levels(text):
    """
    Processes the preserved section to remove unwanted text and format level entries.
    Specifically:
    - It removes an introductory paragraph (if any) by only retaining lines that start with a digit.
    - It splits the text into lines, trims whitespace, and rejoins them with newline breaks.
    Returns the formatted levels string.
    """
    lines = text.splitlines()
    # Retain only lines that begin with a digit (representing level entries)
    formatted_lines = [line.strip() for line in lines if line.strip() and line.strip()[0].isdigit()]
    return "\n".join(formatted_lines)

def format_keylevels_raw(text):
    """
    Processes the formatted levels string to extract only the numbers and ranges.
    For each line, it retains only the text before the first colon.
    Returns the processed raw levels as a string with one entry per line.
    """
    lines = text.splitlines()
    raw_levels = []
    for line in lines:
        if ":" in line:
            # Extract portion before the colon.
            raw = line.split(":", 1)[0].strip()
            raw_levels.append(raw)
        else:
            raw_levels.append(line.strip())
    return "\n".join(raw_levels)

def extract_key_levels(text):
    """Extracts key support/resistance levels using the custom spaCy pipeline."""
    doc = nlp(text)
    return doc._.support_resistance

def identify_trade_setups(text):
    """Identifies potential trade setups from the text."""
    setups = re.findall(r'Trade Setup:\s*(.*)', text, flags=re.IGNORECASE)
    return setups

def calculate_risk_factors(text):
    """Calculates risk factors based on occurrences of the word 'risk'."""
    risk_count = len(re.findall(r'\brisk\b', text, flags=re.IGNORECASE))
    return {"risk_score": risk_count}

# NEW FUNCTION FOR EXTRACTING TRADE PLAN

def extract_trade_plan(text):
    """Extracts the trade plan from the newsletter text.
    It extracts text starting with a line 'Trade Plan [DAY]' (e.g., 'Trade Plan Monday')
    through the paragraph that starts with 'In summary for tomorrow:', including that paragraph.
    """
    import re
    start_match = re.search(r"(?m)^Trade Plan (?:Monday|Tuesday|Wednesday|Thursday|Friday)$", text)
    if not start_match:
        return ""
    start_index = start_match.start()
    rest_text = text[start_index:]
    end_match = re.search(r"(?m)^In summary for tomorrow:.*", rest_text)
    if not end_match:
        return rest_text.strip()
    # Find the end of the paragraph that starts with 'In summary for tomorrow:' (ends at the first blank line)
    paragraph_end = re.search(r"(?:\r?\n){2,}", rest_text[end_match.start():])
    if paragraph_end:
        end_index = end_match.start() + paragraph_end.start()
    else:
        end_index = len(rest_text)
    return rest_text[:end_index].strip()

@anvil.server.background_task
def optimize_latest_newsletter():
    """Background task to optimize the latest extracted email newsletter.
    It fetches the newsletter with the most recent timestamp, cleans and segments the text,
    and generates analysis data using spaCy-based components.
    """
    print("Starting optimize_latest_newsletter background task")
    # Fetch all newsletters and sort locally by descending timestamp
    newsletters = list(app_tables.newsletters.search())
    if newsletters:
        newsletters = sorted(newsletters, key=lambda r: r['timestamp'], reverse=True)
        latest = newsletters[0]
        subject = latest['newslettersubject']
        body = latest['newsletterbody']
        print('Fetched newsletter with subject:', subject)

        # Apply spaCy-based optimization
        cleaned_body = clean_text(body)
        text_without_discard, preserved_section = segment_text(cleaned_body)
        formatted_levels = format_preserved_levels(preserved_section)
        raw_levels = format_keylevels_raw(formatted_levels)
        
        # Write the formatted levels to the newsletteranalysis table
        app_tables.newsletteranalysis.add_row(
            originallevels=formatted_levels,
            timestamp=datetime.datetime.now()
        )
        
        # Extract trade plan from the newsletter text
        trade_plan = extract_trade_plan(cleaned_body)

        # Also write the formatted levels, the raw numbers, and the trade plan to the newsletteroptimized table
        app_tables.newsletteroptimized.add_row(
            keylevels=formatted_levels,
            keylevelsraw=raw_levels,
            tradeplan=trade_plan,
            timestamp=datetime.datetime.now()
        )
        
        key_levels = extract_key_levels(cleaned_body)
        trade_setups = identify_trade_setups(cleaned_body)
        risk_factors = calculate_risk_factors(cleaned_body)

        optimized_data = {
            "newslettersubject": subject,
            "original_body": body,
            "cleaned_body": cleaned_body,
            "text_without_discard": text_without_discard,
            "preserved_section": preserved_section,
            "key_levels": key_levels,
            "trade_setups": trade_setups,
            "risk_factors": risk_factors
        }

        print("Optimized newsletter data:", optimized_data)
        print("Returning optimized result with subject:", subject)
        return optimized_data
    else:
        print('No newsletters found for optimization.')
        return None
