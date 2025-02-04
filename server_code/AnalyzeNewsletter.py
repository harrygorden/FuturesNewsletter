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

# This module handles the AI analysis of the newsletter content.
#
# Primary responsibilities:
# 1. Receives the newsletter content from Main.py
# 2. Prepares and formats the content for AI analysis
# 3. Submits the content to the specified AI model (e.g., OpenAI)
# 4. Processes and formats the AI's response
# 5. Runs as a background task to handle potentially lengthy AI processing
#
# The module uses the OpenAI API for analysis, with credentials stored in Anvil secrets.
# All operations are logged for monitoring and debugging purposes.
#
# Required Anvil Secrets:
# - openai_api_key: API key for accessing OpenAI's services
