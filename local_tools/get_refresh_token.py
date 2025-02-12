from google_auth_oauthlib.flow import InstalledAppFlow
import json
import os

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.send']

def get_refresh_token():
    # Delete token.json if it exists to ensure a fresh token
    if os.path.exists('token.json'):
        os.remove('token.json')
    # Create a flow instance to manage the OAuth 2.0 Authorization Grant Flow steps.
    flow = InstalledAppFlow.from_client_secrets_file(
        'client_secrets.json',  # Your OAuth 2.0 client configuration file
        scopes=SCOPES
    )

    # Run the OAuth flow to get credentials
    credentials = flow.run_local_server(
        port=8080,
        access_type='offline',
        prompt='consent'
    )

    # Print the refresh token
    print("\nYour refresh token is:\n")
    print(credentials.refresh_token)
    print("\nMake sure to save this token securely and add it to your Anvil app's secrets!")

if __name__ == '__main__':
    get_refresh_token()
