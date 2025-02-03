import anvil.google.auth, anvil.google.drive, anvil.google.mail
from anvil.google.drive import app_files
import anvil.secrets
import anvil.server
import anvil.users
import anvil.tables
from anvil.tables import app_tables
import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import base64
from email.mime.text import MIMEText

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

@anvil.server.background_task
def get_latest_newsletter():
    """
    Retrieves the most recent newsletter email from the specified sender.
    Runs as a background task and logs all operations.
    
    Returns:
        dict: Contains 'subject' and 'body' of the newsletter email
    """
    try:
        print("Starting newsletter retrieval process")
        
        # Get the sender email from secrets
        sender_email = anvil.secrets.get_secret('newsletter_sender_email')
        print(f"Looking for emails from: {sender_email}")
        
        # Get Gmail service
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
        
        # Extract body - following the pattern from the working example
        body = None
        if 'parts' in msg['payload']:
            # Handle multipart messages
            for part in msg['payload']['parts']:
                if part['mimeType'] in ['text/plain', 'text/html']:
                    if 'data' in part['body']:
                        body = base64.urlsafe_b64decode(
                            part['body']['data'].encode('UTF-8')
                        ).decode('UTF-8')
                        break
        elif 'body' in msg['payload']:
            # Handle plain text messages
            body = base64.urlsafe_b64decode(
                msg['payload']['body']['data'].encode('UTF-8')
            ).decode('UTF-8')
        
        if body is None:
            print("Could not extract email body")
            return None
            
        newsletter_content = {
            'subject': subject,
            'body': body,
            'date': date
        }
        
        print(f"Found email with subject: {subject}")
        print("Newsletter content successfully extracted")
        return newsletter_content
        
    except Exception as e:
        print(f"Error retrieving newsletter: {str(e)}")
        raise  # Re-raise the exception to properly signal task failure

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
