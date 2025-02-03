import anvil.google.auth, anvil.google.drive, anvil.google.mail
from anvil.google.drive import app_files
import anvil.secrets
import anvil.server
import anvil.users
import anvil.tables
from anvil.tables import app_tables
import datetime

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

# This module is responsible for retrieving the latest newsletter from Gmail.
#
# Primary responsibilities:
# 1. Authenticates with Gmail using Google OAuth credentials
# 2. Searches for and retrieves the most recent email from the specified newsletter sender
# 3. Extracts the email body content for analysis
# 4. Runs as a background task to handle potential delays in email retrieval
#
# The module identifies the correct email using the newsletter_sender_email secret
# and retrieves only the most recent email from that sender.
#
# Required Anvil Secrets:
# - google_client_id: For Gmail API authentication
# - google_client_secret: For Gmail API authentication
# - google_refresh_token: For Gmail API authentication
# - newsletter_sender_email: Email address to identify the newsletter

@anvil.server.background_task
def get_latest_newsletter():
    """
    Retrieves the most recent newsletter email from the specified sender.
    Runs as a background task and logs all operations.
    
    Returns:
        dict: Contains 'subject' and 'body' of the newsletter email
    """
    print("Starting newsletter retrieval process")
    
    try:
        # Get the sender email from secrets
        sender_email = anvil.secrets.get_secret('newsletter_sender_email')
        print(f"Looking for emails from: {sender_email}")
        
        # Get the most recent email from the specified sender
        # inbox() returns messages in reverse chronological order (newest first)
        messages = anvil.google.mail.inbox(from_address=sender_email, max_results=1)
        
        if not messages:
            print("No emails found from the specified sender")
            raise Exception("No newsletter emails found")
        
        # Get the most recent email
        latest_email = messages[0]
        print(f"Found email with subject: {latest_email.subject}")
        
        # Extract the email content
        newsletter_content = {
            'subject': latest_email.subject,
            'body': latest_email.html if latest_email.html else latest_email.text,
            'date': latest_email.date
        }
        
        print("Newsletter content successfully extracted")
        return newsletter_content
        
    except Exception as e:
        print(f"Error retrieving newsletter: {str(e)}")
        raise

@anvil.server.callable
def start_newsletter_retrieval():
    """
    Initiates the background task to retrieve the newsletter.
    This is the entry point called by Main.py.
    
    Returns:
        background_task: The background task object for tracking progress
    """
    print("Initiating newsletter retrieval background task")
    return anvil.server.launch_background_task('get_latest_newsletter')
