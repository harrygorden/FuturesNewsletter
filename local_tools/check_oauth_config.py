# check_oauth_config.py
from Uplink_Connect import *  # Import your existing connection setup
import anvil.secrets

print("\n=== Google OAuth Configuration ===")
try:
    print("Authorized domains:", anvil.secrets.get_secret('google_authorized_domains'))
    print("Configured scopes:", anvil.secrets.get_secret('google_oauth_scopes'))
    print("Client ID (partial):", anvil.secrets.get_secret('google_client_id')[:6] + "...")
except Exception as e:
    print("ERROR:", str(e))
    print("Check: 1) Uplink connection 2) Secret names 3) App permissions")