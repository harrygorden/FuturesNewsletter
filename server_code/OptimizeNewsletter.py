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
import time

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
    """Cleans the text by removing URLs, timestamps, and specific unwanted sections."""
    text = re.sub(r'https?://\S+', '', text)   # Remove URLs
    text = re.sub(r'\d{1,2}:\d{2}\s*[AP]M\s*[A-Z]{2,}', '', text)  # Remove timestamps
    text = re.sub(r'View this post on the web at.*?\n', '', text)  # Remove "View this post" line
    text = re.sub(r'\n\s*Unsubscribe\s*(?:\n|$)', '', text, flags=re.IGNORECASE)  # Remove "Unsubscribe" line and surrounding whitespace
    text = re.sub(r'\*\*\*\*\*\*\*\*\*\*Important Housekeeping Notices\*\*\*\*\*\*\*\*.*?\*{10,}', '', text, flags=re.DOTALL)  # Remove housekeeping section
    # Clean up empty lines
    text = re.sub(r'^\s*\n', '', text)  # Remove leading empty lines
    text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)  # Replace multiple empty lines with a single empty line
    text = text.strip()  # Remove leading/trailing whitespace
    return text

def segment_text(text):
    """Discards and preserves sections for analysis.
    Discards content from 'The Run Down on The Level To Level Approach: What, Why, How' up to 'Core Structures/Levels To Engage',
    and extracts the section from 'Core Structures/Levels To Engage' to 'Trade Recap/Education'.
    """
    # Normalize line endings
    text = text.replace('\r\n', '\n')
    
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

@spacy.Language.component("market_sentiment_analyzer")
def market_sentiment_analyzer(doc):
    """Analyzes market sentiment in the text."""
    bullish_terms = ['bullish', 'upward', 'higher', 'rally', 'squeeze', 'long']
    bearish_terms = ['bearish', 'downward', 'lower', 'breakdown', 'short', 'sell']
    
    bull_count = 0
    bear_count = 0
    
    for token in doc:
        if token.text.lower() in bullish_terms:
            bull_count += 1
        elif token.text.lower() in bearish_terms:
            bear_count += 1
    
    total = bull_count + bear_count
    if total > 0:
        sentiment_score = (bull_count - bear_count) / total  # -1 to 1 scale
    else:
        sentiment_score = 0
        
    doc._.market_sentiment = {
        'score': sentiment_score,
        'bullish_mentions': bull_count,
        'bearish_mentions': bear_count
    }
    return doc

# Register the extension
if not Doc.has_extension("market_sentiment"):
    Doc.set_extension("market_sentiment", default={})

@spacy.Language.component("price_level_detector")
def price_level_detector(doc):
    """Detects price levels and their context (support/resistance/target)."""
    price_pattern = r'(\d{4}(?:\.\d{1,2})?)'  # Matches 4-digit prices with optional decimals
    level_info = []
    
    for match in re.finditer(price_pattern, doc.text):
        price = match.group(1)
        # Get surrounding context (20 chars before and after)
        start = max(0, match.start() - 20)
        end = min(len(doc.text), match.end() + 20)
        context = doc.text[start:end]
        
        level_type = 'unknown'
        if 'support' in context.lower():
            level_type = 'support'
        elif 'resistance' in context.lower():
            level_type = 'resistance'
        elif 'target' in context.lower():
            level_type = 'target'
            
        level_info.append({
            'price': price,
            'type': level_type,
            'context': context.strip()
        })
    
    doc._.price_levels = level_info
    return doc

# Register the extension for price levels
if not Doc.has_extension("price_levels"):
    Doc.set_extension("price_levels", default=[])

# Add components to pipeline in correct order
if "price_level_detector" not in nlp.pipe_names:
    nlp.add_pipe("price_level_detector", after="support_resistance_detector")

if "market_sentiment_analyzer" not in nlp.pipe_names:
    nlp.add_pipe("market_sentiment_analyzer", after="price_level_detector")

@spacy.Language.component("semantic_section_chunker")
def semantic_section_chunker(doc):
    """Identifies and chunks newsletter sections based on semantic headers and content."""
    # Define common newsletter section headers with more variations
    section_headers = {
        'core_levels': ['core structures', 'key levels', 'levels to engage', 'Core Structures', 'CORE STRUCTURES',
                       'Key Levels', 'KEY LEVELS', 'Levels to Engage', 'LEVELS TO ENGAGE'],
        'trade_recap': ['trade recap', 'trading recap', 'trade education', 'Trade Recap', 'TRADE RECAP',
                       'Trading Recap', 'TRADING RECAP', 'Trade Education', 'TRADE EDUCATION']
    }
    
    # Store identified sections
    doc._.sections = {}
    
    # Initialize trade_plan_start outside the conditional block
    trade_plan_start = -1
    
    # First find the trade plan section as it will be used as a boundary
    if doc._.trading_day:  # Only proceed if we have the trading day information
        print(f"\nLooking for trade plan section for {doc._.trading_day}")
        
        # First, let's find all instances of "Trade Plan Monday" to see the context
        plan_day_pattern = fr'Trade Plan\s+{doc._.trading_day}'
        plan_day_matches = list(re.finditer(plan_day_pattern, doc.text, re.IGNORECASE))
        if plan_day_matches:
            print(f"\nFound {len(plan_day_matches)} instances of '{plan_day_pattern}':")
            for match in plan_day_matches:
                start = max(0, match.start() - 50)
                end = min(len(doc.text), match.end() + 50)
                print(f"\nMatch at position {match.start()}:")
                print(f"...{doc.text[start:end]}...")
        else:
            print(f"No instances of '{plan_day_pattern}' found!")
            
        # Now look for "In summary for tomorrow"
        summary_matches = list(re.finditer(r'In summary for tomorrow:', doc.text, re.IGNORECASE))
        if summary_matches:
            print(f"\nFound {len(summary_matches)} instances of 'In summary for tomorrow:':")
            for match in summary_matches:
                start = max(0, match.start() - 50)
                end = min(len(doc.text), match.end() + 50)
                print(f"\nMatch at position {match.start()}:")
                print(f"...{doc.text[start:end]}...")
        else:
            print("No instances of 'In summary for tomorrow:' found!")
        
        # Try a more flexible pattern
        trade_plan_pattern = fr'(?:Trade Plan\s+{doc._.trading_day}[\s\S]*?In summary for tomorrow:[\s\S]*?)(?=\s*(?:As always no crystal balls|\n\n|\Z))'
        print(f"\nUsing pattern: {trade_plan_pattern}")
        trade_plan_match = re.search(trade_plan_pattern, doc.text, re.IGNORECASE)
        if trade_plan_match:
            trade_plan_start = trade_plan_match.start()
            doc._.sections['trade_plan'] = trade_plan_match.group(0).strip()
            print(f"Found trade plan section for {doc._.trading_day} starting at position {trade_plan_start}")
            print("\nFirst 100 chars of matched text:")
            print(doc._.sections['trade_plan'][:100] + "...")
        else:
            print(f"No trade plan section found matching pattern for {doc._.trading_day}")
            # Let's also look for just 'Trade Plan' to see if it exists in a different format
            basic_matches = re.finditer(r'Trade Plan', doc.text, re.IGNORECASE)
            print("\nFound 'Trade Plan' mentions at positions:")
            for match in basic_matches:
                start = max(0, match.start() - 30)
                end = min(len(doc.text), match.end() + 30)
                print(f"Position {match.start()}: ...{doc.text[start:end]}...")
    
    # Find section boundaries for other sections
    section_spans = []
    for section_type, headers in section_headers.items():
        for header in headers:
            # Use re.finditer for case-insensitive matching
            matches = re.finditer(re.escape(header), doc.text, re.IGNORECASE)
            for match in matches:
                section_spans.append((match.start(), section_type))
                print(f"Found {section_type} section with header: {header}")
    
    # Sort section spans by their start position
    section_spans.sort(key=lambda x: x[0])
    
    # Extract sections
    for i in range(len(section_spans)):
        start_pos = section_spans[i][0]
        section_type = section_spans[i][1]
        
        # End position is either the start of next section, trade plan start, or end of document
        if i < len(section_spans) - 1:
            end_pos = section_spans[i + 1][0]
        else:
            end_pos = len(doc.text)
        
        # If this is the trade_recap section and we found a trade plan, use trade plan start as boundary
        if section_type == 'trade_recap' and trade_plan_start != -1:
            end_pos = min(end_pos, trade_plan_start)
        
        # Find the actual start of content (skip header line)
        section_text = doc.text[start_pos:end_pos]
        content_start = section_text.find('\n')
        if content_start != -1:
            start_pos += content_start + 1
        
        # Store the section content
        section_content = doc.text[start_pos:end_pos].strip()
        doc._.sections[section_type] = section_content
        print(f"Stored {section_type} section with length: {len(section_content)} chars")
    
    # Debug print final sections
    print("Final sections found:", list(doc._.sections.keys()))
    
    return doc

# Register the section extension
if not Doc.has_extension("sections"):
    Doc.set_extension("sections", default={})

# Add semantic chunker to pipeline
if "semantic_section_chunker" not in nlp.pipe_names:
    nlp.add_pipe("semantic_section_chunker", after="market_sentiment_analyzer")

def get_newsletter_sections(text):
    """Process newsletter text and return semantically chunked sections."""
    doc = nlp(text)
    return doc._.sections

def get_newsletter_id(session_date=None):
    """
    Generates a newsletter ID in yyyymmdd format for the next trading day.
    If session_date is not provided, it uses the current date.
    Returns Monday's date when run on Friday after market close (23:00), Saturday, or Sunday.
    """
    if session_date is None:
        session_date = datetime.datetime.now()
    
    # Convert to just date if datetime
    current_date = session_date.date() if isinstance(session_date, datetime.datetime) else session_date
    
    # Get the day of week (0=Monday, 6=Sunday)
    weekday = current_date.weekday()
    
    # If it's Friday and before market close, use next trading day (Monday)
    if weekday == 4:  # Friday
        if isinstance(session_date, datetime.datetime) and session_date.hour >= 23:
            # After market close on Friday, use next Monday
            days_to_add = 3
        else:
            # Before market close on Friday, use today
            days_to_add = 0
    # If it's Saturday, use next Monday (add 2 days)
    elif weekday == 5:  # Saturday
        days_to_add = 2
    # If it's Sunday, use next Monday (add 1 day)
    elif weekday == 6:  # Sunday
        days_to_add = 1
    # For any other day, use the current date
    else:
        days_to_add = 0
    
    next_trading_day = current_date + datetime.timedelta(days=days_to_add)
    return next_trading_day.strftime("%Y%m%d")

@anvil.server.callable
def optimize_latest_newsletter(newsletter_id):
    """
    Optimizes the newsletter content and updates relevant tables.
    Now requires newsletter_id parameter for consistency.
    """
    print(f"Starting optimization for newsletter {newsletter_id}")
    
    # Get the newsletter content
    newsletter = app_tables.newsletters.get(newsletter_id=newsletter_id)
    if not newsletter:
        raise ValueError(f"No newsletter found for ID {newsletter_id}")
    
    # Get the trading day name for this newsletter - use newsletter_id instead of timestamp
    from . import utils
    # Convert newsletter_id to datetime for the trading day
    newsletter_date = datetime.datetime.strptime(newsletter_id, "%Y%m%d")
    _, trading_day = utils.get_newsletter_id(newsletter_date)
    print(f"Processing newsletter for trading day: {trading_day}")
    
    # Clean and process the content
    cleaned_body = clean_text(newsletter['newsletterbody'])
    
    # Create a custom spaCy doc with the trading day information
    doc = nlp(cleaned_body)
    doc._.trading_day = trading_day  # Store trading day for use in semantic_section_chunker
    sections = doc._.sections  # Get sections directly from the processed doc
    
    # Extract and format levels
    core_levels = sections.get('core_levels', '')
    formatted_levels = format_preserved_levels(core_levels)
    raw_levels = format_keylevels_raw(formatted_levels)
    trade_plan_text = sections.get('trade_plan', '')
    
    if trade_plan_text:
        print(f"Found trade plan text of length: {len(trade_plan_text)}")
    else:
        print("No trade plan text found in the newsletter")

    # Update the existing analysis row
    analysis_row = app_tables.newsletteranalysis.get(newsletter_id=newsletter_id)
    if analysis_row:
        analysis_row.update(
            originallevels=formatted_levels,
            tradeplan=trade_plan_text
        )
    
    # Create optimized content record
    app_tables.newsletteroptimized.add_row(
        newsletter_id=newsletter_id,
        keylevels=formatted_levels,
        keylevelsraw=raw_levels,
        tradeplan=trade_plan_text,
        optimized_content=cleaned_body,
        core_levels=sections.get('core_levels', ''),
        trade_recap=sections.get('trade_recap', ''),
        timestamp=datetime.datetime.now()
    )
    
    return "Newsletter optimization completed successfully"

# Register the trading day extension for spaCy Doc
if not Doc.has_extension("trading_day"):
    Doc.set_extension("trading_day", default=None)
