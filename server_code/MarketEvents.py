import anvil.google.auth, anvil.google.drive, anvil.google.mail
from anvil.google.drive import app_files
import anvil.secrets
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.server
import datetime
import json

# ==============================================================================
# MarketEvents Module
#
# Purpose:
#   This module calculates the next trading session's date based on the current day.
#   It follows these rules:
#     - Monday to Thursday: the next session is the following day.
#     - Friday: the next session is the following Monday.
#     - Saturday and Sunday: the next session is assumed to be the following Monday.
#
#   After determining the next session's date, the module queries the 'marketcalendar'
#   table in the Anvil database for events matching that date. If matching events are found,
#   it extracts their 'date' and 'time' values and writes them to the 'newsletteranalysis' table
#   under the 'MarketEvents' column.
#
# Testing:
#   You can test this functionality by calling the update_market_events() function directly
#   from the Anvil command line.
#
# Note: Functions marked with @anvil.server.callable can be invoked remotely via anvil.server.call().
# ==============================================================================

# This is a server module. It runs on the Anvil server,
# rather than in the user's browser.
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

@anvil.server.callable
def update_market_events():
    """Calculates next session's date and updates newsletter analysis with market event details if found."""
    today = datetime.date.today()
    weekday = today.weekday()  # Monday=0, Tuesday=1, ... Sunday=6
    
    # Determine the next session's date
    if 0 <= weekday <= 3:  # Monday to Thursday
        next_session = today + datetime.timedelta(days=1)
    elif weekday == 4:  # Friday
        next_session = today + datetime.timedelta(days=3)
    else:  # Saturday (5) or Sunday (6): assume next session is Monday
        next_session = today + datetime.timedelta(days=(7 - weekday))
    
    # Convert date to string as the 'date' column in marketcalendar is a string field
    next_session_str = next_session.strftime('%Y-%m-%d')
    # Search for market calendar events with the calculated date as a string
    events = list(app_tables.marketcalendar.search(date=next_session_str))
    
    if events:
        # Extract the time and event name from each matching record and format them
        events_data = [f"{event['time']}          {event['event']}" for event in events]
        # Join multiple events with a newline if applicable
        events_str = "\n".join(events_data)
        app_tables.newsletteranalysis.add_row(MarketEvents=events_str)
        print(f"Inserted MarketEvents for session date {next_session}: {events_str}")
    else:
        print(f"No market calendar events found for the next session date: {next_session}")
        

if __name__ == '__main__':
    update_market_events()
