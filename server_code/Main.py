import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.google.auth, anvil.google.drive, anvil.google.mail
from anvil.google.drive import app_files
import anvil.secrets
import anvil.server
import anvil.users
import anvil.tables

# This is the main orchestration module for the Futures Newsletter Analysis application.
# It coordinates the entire workflow of retrieving, analyzing, and sending newsletter analyses.
#
# Primary responsibilities:
# 1. Orchestrates the overall workflow between other modules
# 2. Initiates the newsletter retrieval process from GetNewsletter.py
# 3. Coordinates the analysis process through AnalyzeNewsletter.py
# 4. Triggers the sending of results via SendAnalysis.py
# 5. Manages background task execution and logging
#
# This module runs on the Anvil server and uses background tasks for long-running operations.
# All operations are logged through Anvil's logging system for monitoring and debugging.
#
# Required Anvil Secrets:
# - google_client_id: For GMail authentication
# - google_client_secret: For GMail authentication
# - google_refresh_token: For GMail authentication
# - newsletter_sender_email: Email address to identify the newsletter
# - openai_api_key: For AI analysis
# - recipient_email: Destination for analysis results
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
def process_newsletter():
    """
    Main orchestration function that coordinates the entire newsletter processing workflow.
    Starts with retrieving the newsletter and will be expanded to handle analysis and sending.
    
    Returns:
        dict: Status of the operation and any relevant data
    """
    print("Starting newsletter processing workflow")
    
    try:
        from . import GetNewsletter
        print("Initiating newsletter retrieval background task which will also insert the newsletter into app_tables.newsletters")
        GetNewsletter.start_newsletter_retrieval()  # Launch the background task without waiting
        return {
            'status': 'success',
            'message': "Newsletter retrieval initiated. Check background task logs and app_tables.newsletters for inserted data."
        }
            
    except Exception as e:
        print(f"Error in newsletter processing workflow: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }

# Temporary test function for optimize_latest_newsletter
@anvil.server.callable
def test_optimize_newsletter():
    """Temporary test function to launch the optimize_latest_newsletter background task from the OptimizeNewsletter module."""
    from . import OptimizeNewsletter
    return anvil.server.launch_background_task('optimize_latest_newsletter')
