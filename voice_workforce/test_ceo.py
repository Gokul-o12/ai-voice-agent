from twilio.rest import Client
import os
from dotenv import load_dotenv

load_dotenv()

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_number = os.getenv("MOBILE")
my_phone_number = os.getenv("MOBILE1") # Make sure this is your actual number!

client = Client(account_sid, auth_token)

# IMPORTANT: Use your active ngrok URL
NGROK_BASE_URL = "https://postabdominal-semiconsciously-jalen.ngrok-free.dev"

def call_ceo():
    call = client.calls.create(
        url=f"{NGROK_BASE_URL}/voice/ceo_inbound",
        to=my_phone_number,
        from_=twilio_number
    )
    print(f"📞 CEO Inbound Simulation started! SID: {call.sid}")

if __name__ == "__main__":
    call_ceo()