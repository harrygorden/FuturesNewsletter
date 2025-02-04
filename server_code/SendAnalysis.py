import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.google.auth, anvil.google.drive, anvil.google.mail
from anvil.google.drive import app_files
import anvil.secrets
import anvil.server

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

# This module is responsible for emailing the AI analysis results to the user.
#
# Primary responsibilities:
# 1. Receives the analyzed newsletter content from Main.py
# 2. Formats the analysis into a readable email format
# 3. Sends the formatted analysis to the specified recipient
# 4. Runs as a background task to handle email sending operations
#
# The module uses Gmail API for sending emails, with credentials stored in Anvil secrets.
# All operations are logged for monitoring and debugging purposes.
#
# Required Anvil Secrets:
# - google_client_id: For Gmail API authentication
# - google_client_secret: For Gmail API authentication
# - google_refresh_token: For Gmail API authentication
# - recipient_email: The email address to send the analysis to
