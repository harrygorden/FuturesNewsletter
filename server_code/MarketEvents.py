import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.server

@anvil.server.callable
@anvil.server.background_task

def process_market_events(newsletter_id):
    """
    Processes market events for a given newsletter by converting the newsletter_id 
    (in YYYYMMDD format) to YYYY-MM-DD, searching the marketcalendar table for events
    on that date, and updating the newsletteranalysis table's MarketEvents field with
    the event times and names formatted as:

    7:30AM          Event Name 1
    7:30AM          Event Name 2
    9:00AM          Event Name 3
    """
    # Validate newsletter_id format
    if len(newsletter_id) != 8:
         raise ValueError("newsletter_id must be in YYYYMMDD format")
         
    # Convert newsletter_id to YYYY-MM-DD format
    event_date = f"{newsletter_id[:4]}-{newsletter_id[4:6]}-{newsletter_id[6:]}"
    
    # Search for matching events in the marketcalendar table
    events = list(app_tables.marketcalendar.search(date=event_date))
    
    events_text = ""
    if events:
         for event in events:
             # Assuming marketcalendar table has 'time' and 'eventname' columns.
             event_time = event['time']
             event_name = event['event'] if 'event' in event else 'Unnamed Event'
             
             # Format event_time if it's a time object. Remove leading zero for hour if present.
             if hasattr(event_time, 'strftime'):
                 event_time_str = event_time.strftime("%I:%M%p").lstrip("0")
             else:
                 event_time_str = str(event_time)
             
             # Append formatted line with padded time
             events_text += f"{event_time_str:<15}{event_name}\n"
         events_text = events_text.rstrip("\n")
    else:
         events_text = ""
         
    # Update the newsletteranalysis table for the corresponding newsletter_id
    rows = list(app_tables.newsletteranalysis.search(newsletter_id=newsletter_id))
    if rows:
         row = rows[0]
         row['MarketEvents'] = events_text
    else:
         app_tables.newsletteranalysis.add_row(
              newsletter_id=newsletter_id,
              MarketEvents=events_text
         )
    
    return f"Processed market events for newsletter_id {newsletter_id}"
