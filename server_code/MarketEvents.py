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
    # Convert newsletter_id to YYYY-MM-DD format (newsletter_id is now just the string part)
    event_date = f"{newsletter_id[:4]}-{newsletter_id[4:6]}-{newsletter_id[6:]}"
    
    # Search for matching events in the marketcalendar table
    events = list(app_tables.marketcalendar.search(date=event_date))
    
    def parse_time(t):
        if isinstance(t, str):
            for fmt in ("%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M%p"):
                try:
                    return datetime.datetime.strptime(t, fmt)
                except ValueError:
                    continue
            raise ValueError(f"Time format not recognized: {t}")
        return t
    
    events_text = ""
    if events:
        events_text = "\n".join(
            f"{parse_time(event['time']).strftime('%I:%M%p').lstrip('0'):<15}{event['event']}"
            for event in sorted(events, key=lambda x: parse_time(x['time']))
        )
    
    # Update the existing analysis row
    analysis_rows = app_tables.newsletteranalysis.search(newsletter_id=newsletter_id)
    for analysis_row in analysis_rows:
        analysis_row['MarketEvents'] = events_text
    
    return events_text
