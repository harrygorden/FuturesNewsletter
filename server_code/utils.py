import datetime

def get_newsletter_id(session_date=None):
    """
    Generates a newsletter ID in yyyymmdd format for the next trading day.
    If session_date is not provided, it uses the current date.
    Returns Monday's date when run on Friday after market close (23:00), Saturday, or Sunday.
    """
    if session_date is None:
        session_date = datetime.datetime.now()
    
    current_date = session_date.date() if isinstance(session_date, datetime.datetime) else session_date
    weekday = current_date.weekday()
    
    if weekday == 4:  # Friday
        if isinstance(session_date, datetime.datetime) and session_date.hour >= 23:
            days_to_add = 3
        else:
            days_to_add = 0
    elif weekday == 5:  # Saturday
        days_to_add = 2
    elif weekday == 6:  # Sunday
        days_to_add = 1
    else:
        days_to_add = 0
    
    next_trading_day = current_date + datetime.timedelta(days=days_to_add)
    return next_trading_day.strftime("%Y%m%d") 