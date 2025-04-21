import os
from twilio.rest import Client
from datetime import datetime
from dotenv import load_dotenv
import json
import logging
import time
# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Twilio setup
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')

if not account_sid or not auth_token:
    logger.error("Twilio credentials not found")
    raise Exception("Twilio credentials not found")

try:
    client = Client(account_sid, auth_token)
except Exception as e:
    logger.error(f"Error initializing Twilio client: {str(e)}")
    raise Exception(f"Error initializing Twilio client: {str(e)}")

def validate_whatsapp_number(number):
    """
    Validate and format WhatsApp number
    
    Parameters:
    number (str): Input phone number
    
    Returns:
    str: Formatted phone number
    """
    # Remove any spaces or special characters except '+'
    clean_number = ''.join(char for char in number if char.isdigit() or char == '+')
    
    # Validate the number format
    if not clean_number.startswith('+'):
        clean_number = '+' + clean_number
    
    # Check if number has at least 10 digits
    if sum(c.isdigit() for c in clean_number) < 10:
        logger.warning("Number may be too short for an international phone number")
    
    return clean_number

def send_access_message(username: str, doctor_name: str, emg_status: bool, phone_number_1: str, phone_number_2: str = None) -> dict:
    """
    Send access request message to WhatsApp numbers
    
    Returns:
    dict: Response containing message details and status
    """
    try:
        # Always send to primary phone number
        message = client.messages.create(
            from_='whatsapp:+14155238886',
            content_sid='HXacd7dd25760e080787d9027619af735e',
            content_variables=json.dumps({"1": username, "2": doctor_name}),
            to=f'whatsapp:{phone_number_1}'
        )
        
        sent_time = message.date_created
        phone_numbers_sent = [phone_number_1]
        
        # Send to second phone number only if emergency status is True
        if emg_status and phone_number_2:
            message2 = client.messages.create(
                from_='whatsapp:+14155238886',
                content_sid='HXacd7dd25760e080787d9027619af735e',
                content_variables=json.dumps({"1": username, "2": doctor_name}),
                to=f'whatsapp:{phone_number_2}'
            )
            phone_numbers_sent.append(phone_number_2)
        
        logger.info(f"Message sent to: {', '.join(phone_numbers_sent)}")
        
        return {
            "username": username,
            "doctor_name": doctor_name,
            "hasAccess": False,  # Initial access is false
            "sent_time": str(sent_time),
            "emg_status": emg_status
        }
        
    except Exception as e:
        logger.error(f"Error sending access message: {str(e)}")
        return {"error": str(e)}

def check_access_status(username: str, doctor_name: str, phone_numbers: list, sent_time: str) -> dict:
    """
    Check if user has confirmed access from any of the phone numbers
    """
    try:
        sent_time_dt = datetime.fromisoformat(sent_time.replace('Z', '+00:00'))
        
        for phone_number in phone_numbers:
            formatted_number = validate_whatsapp_number(phone_number)
            if not formatted_number.startswith('whatsapp:'):
                formatted_number = f'whatsapp:{formatted_number}'
                
            messages = client.messages.list(
                from_=formatted_number,
                limit=1,
                date_sent_after=sent_time_dt
            )
            
            if messages:
                message_text = messages[0].body.lower() if messages[0].body else ""
                if 'confirm' in message_text:
                    logger.info(f"Confirmation received from {phone_number}")
                    return {
                        "username": username,
                        "doctor_name": doctor_name,
                        "hasAccess": True
                    }
                elif 'cancel' in message_text:
                    logger.info(f"Cancellation received from {phone_number}")
                    return {
                        "username": username,
                        "doctor_name": doctor_name,
                        "hasAccess": False
                    }
        
        return {
            "username": username,
            "doctor_name": doctor_name,
            "hasAccess": False  # No confirmation from any number
        }
        
    except Exception as e:
        logger.error(f"Error checking access status: {str(e)}")
        return {"error": str(e)}

def main_send_message(username: str, doctor_name: str, emg_status: bool, phone_number_1: str, phone_number_2: str = None):
    """Main function to handle WhatsApp authentication flow"""
    # Validate phone numbers
    phone_number_1 = validate_whatsapp_number(phone_number_1)
    if emg_status and phone_number_2:
        phone_number_2 = validate_whatsapp_number(phone_number_2)
    
    # Send access message
    logger.info(f"Sending message to patient{' and emergency contact' if emg_status else ''}...")
    response = send_access_message(
        username=username,
        doctor_name=doctor_name,
        emg_status=emg_status,
        phone_number_1=phone_number_1,
        phone_number_2=phone_number_2
    )
    logger.info(f"Initial response: {json.dumps(response, indent=2)}")

    # Set wait time for confirmation
    wait_time = 60  # Default wait time in seconds
    phone_numbers = [phone_number_1]
    if emg_status and phone_number_2:
        phone_numbers.append(phone_number_2)
    
    # Wait a bit for message delivery
    time.sleep(5)
    
    # Check periodically for confirmation
    start_time = time.time()
    end_time = start_time + wait_time
    confirmed = False
    final_status = None
    
    while time.time() < end_time:
        remaining = int(end_time - time.time())
        logger.info(f"Checking for confirmation... ({remaining}s remaining)")
        
        status = check_access_status(
            username=response["username"],
            doctor_name=response["doctor_name"],
            phone_numbers=phone_numbers,
            sent_time=response["sent_time"]
        )
        
        final_status = status  # Store the latest status
        
        if status.get("hasAccess"):
            confirmed = True
            logger.info("Access confirmed!")
            break
            
        # Wait before checking again
        if time.time() < end_time:
            time.sleep(5)
    
    if not confirmed:
        logger.info("No confirmation received within the time limit.")
    
    # Convert the final response to proper JSON
    return json.dumps(final_status, indent=2)

if __name__ == "__main__":
    # Example usage
    result = main_send_message(
        username="John Doe",
        doctor_name="Dr. Smith",
        emg_status=False,
        phone_number_1="+918277785093",
        phone_number_2="+917795075436"  # Optional emergency contact number
    )
    
    # # Print the JSON response
    # print(result)