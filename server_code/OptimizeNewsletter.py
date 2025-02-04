import anvil.google.auth, anvil.google.drive, anvil.google.mail
from anvil.google.drive import app_files
import anvil.secrets
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.server
import spacy
import re

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

def support_resistance_detector(doc):
    """Custom spaCy pipeline component to detect support/resistance levels."""
    pattern = r"(\d+\.\d+)\s*(?:support|resistance)"
    matches = re.findall(pattern, doc.text, flags=re.IGNORECASE)
    doc._.support_resistance = matches
    return doc

if "support_resistance_detector" not in nlp.pipe_names:
    nlp.add_pipe(support_resistance_detector, last=True)

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
