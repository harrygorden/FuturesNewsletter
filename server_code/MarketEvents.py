import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.server
import time
import datetime

@anvil.server.callable
@anvil.server.background_task

def process_market_events(newsletter_id):
    """
    Processes market events for a given newsletter and updates the newsletteranalysis table.
    """
    # Convert newsletter_id to YYYY-MM-DD format
    event_date = f"{newsletter_id[:4]}-{newsletter_id[4:6]}-{newsletter_id[6:]}"
    
    # Search for matching events in the marketcalendar table
    events = list(app_tables.marketcalendar.search(date=event_date))
    
    events_text = ""
    if events:
        events_text = "\n".join(
            f"{event['time'].strftime('%I:%M%p').lstrip('0'):<15}{event['event']}"
            for event in sorted(events, key=lambda x: x['time'])
        )
    
    # Update the existing analysis row
    analysis_row = app_tables.newsletteranalysis.get(newsletter_id=newsletter_id)
    if analysis_row:
        analysis_row['MarketEvents'] = events_text
    
    return events_text
