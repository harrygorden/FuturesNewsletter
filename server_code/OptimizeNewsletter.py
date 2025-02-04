import anvil.google.auth, anvil.google.drive, anvil.google.mail
from anvil.google.drive import app_files
import anvil.secrets
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.server

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

@anvil.server.background_task
def optimize_latest_newsletter():
    """Background task to optimize the latest extracted email newsletter.
    It fetches the newsletter with the most recent timestamp from the 'newsletters' table,
    retrieves its subject and body, and performs further optimization steps.
    """
    # Fetch all newsletters and then sort them locally by descending timestamp
    newsletters = list(app_tables.newsletters.search())
    if newsletters:
        newsletters = sorted(newsletters, key=lambda r: r['timestamp'], reverse=True)
        latest = newsletters[0]
        subject = latest['newslettersubject']
        body = latest['newsletterbody']
        print('Fetched newsletter with subject:', subject)
        # TODO: Insert optimization logic here as needed
        return {"newslettersubject": subject, "newsletterbody": body}
    else:
        print('No newsletters found for optimization.')
        return None
