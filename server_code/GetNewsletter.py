import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.google.auth, anvil.google.drive, anvil.google.mail
from anvil.google.drive import app_files
import anvil.secrets
import anvil.server
import anvil.users
import anvil.tables
import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import base64
from email.mime.text import MIMEText
import json
from email.utils import parsedate_to_datetime

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

def find_body(payload):
    """Recursively search the payload for a body with data."""
    if 'body' in payload and 'data' in payload['body']:
        return base64.urlsafe_b64decode(payload['body']['data'].encode('UTF-8')).decode('UTF-8')
    if 'parts' in payload:
        for part in payload['parts']:
            result = find_body(part)
            if result:
                return result
    return None

def get_gmail_service():
    """
    Creates and returns an authenticated Gmail service using our OAuth credentials.
    Similar to the non-Anvil version but using Anvil secrets instead of local files.
    """
    try:
        # Create credentials from our Anvil secrets
        creds = Credentials(
            token=None,
            refresh_token=anvil.secrets.get_secret('google_refresh_token'),
            client_id=anvil.secrets.get_secret('google_client_id'),
            client_secret=anvil.secrets.get_secret('google_client_secret'),
            token_uri='https://oauth2.googleapis.com/token',
            scopes=['https://www.googleapis.com/auth/gmail.readonly', 
                   'https://www.googleapis.com/auth/gmail.send']
        )
        
        # Refresh the credentials
        creds.refresh(Request())
        
        # Return the Gmail service
        return build('gmail', 'v1', credentials=creds)
        
    except Exception as e:
        print(f"Error creating Gmail service: {str(e)}")
        raise

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

def _get_latest_newsletter():
    """Synchronous helper function to retrieve the newsletter."""
    try:
        print("Starting newsletter retrieval process")
        sender_email = anvil.secrets.get_secret('newsletter_sender_email')
        print(f"Looking for emails from: {sender_email}")

        service = get_gmail_service()

        # Search for the most recent email from the sender
        query = f"from:{sender_email}"
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=1
        ).execute()

        messages = results.get('messages', [])

        if not messages:
            print("No emails found from the specified sender")
            return None

        # Get the full email content
        msg = service.users().messages().get(
            userId='me',
            id=messages[0]['id'],
            format='full'
        ).execute()

        # Extract headers
        headers = msg['payload']['headers']
        subject = next(h['value'] for h in headers if h['name'].lower() == 'subject')
        date = next(h['value'] for h in headers if h['name'].lower() == 'date')

        # Check for duplicates BEFORE processing the email body
        latest_rows = list(app_tables.newsletters.search())
        if latest_rows:
            latest = sorted(latest_rows, key=lambda row: row['timestamp'], reverse=True)[0]
            if latest['newslettersubject'] == subject:
                print("Duplicate email detected. Latest email subject matches the retrieved email subject.")
                print("Stopping all processing to prevent duplicate entries.")
                return "DUPLICATE"

        # Extract body only if not a duplicate
        body = find_body(msg['payload'])
        if body is None:
            print("Could not extract email body")
            return None

        try:
            news_timestamp = parsedate_to_datetime(date)
        except Exception as e:
            print("Error parsing date, storing raw date string:", e)
            news_timestamp = date

        newsletter_id = get_newsletter_id()
        app_tables.newsletters.add_row(
            newsletter_id=newsletter_id,
            timestamp=news_timestamp,
            newslettersubject=subject,
            newsletterbody=body
        )
        print("Newsletter row inserted into app_tables.newsletters")
        print("Newsletter content being returned")
        
        return {
            'subject': subject,
            'body': body,
            'date': date
        }

    except Exception as e:
        print("Error retrieving newsletter: " + str(e))
        raise

@anvil.server.callable
@anvil.server.background_task
def get_latest_newsletter():
    result = _get_latest_newsletter()
    if result is None:
        print("No new newsletter found.")
        return "No new newsletter to process."
    elif result == "DUPLICATE":
        print("Duplicate newsletter detected, stopping all processing.")
        return "Duplicate newsletter detected."
    else:
        print("Newsletter processed successfully.")
        # Chain the optimization task after successful retrieval
        print("Launching optimization task...")
        anvil.server.launch_background_task('optimize_latest_newsletter')
        return "Newsletter retrieved and optimization task launched."

@anvil.server.callable
def start_newsletter_retrieval():
    """
    Initiates the background task to retrieve the newsletter.
    This is the entry point called by Main.py.
    
    Returns:
        background_task: The background task object for tracking progress
    """
    print("Initiating newsletter retrieval background task")
    return anvil.server.launch_background_task("get_latest_newsletter")
