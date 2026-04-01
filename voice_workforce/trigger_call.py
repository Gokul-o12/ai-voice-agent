import os
import urllib.parse
import asyncio 
from twilio.rest import Client
from twilio.http.async_http_client import AsyncTwilioHttpClient 
from dotenv import load_dotenv

from app.models.database import SessionLocal, ProductionOrder, ProductionLine, OrderStatus, AIStatus

load_dotenv()

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_number = "+12202171605" 

NGROK_BASE_URL = "https://postabdominal-semiconsciously-jalen.ngrok-free.dev"

async def fire_twilio_call(client, webhook_url, supervisor_phone, supervisor_name, line_id):
    """This function handles the actual network request to Twilio asynchronously."""
    try:
        print(f"🚀 Dispatching schedule check call to {supervisor_name} (Line {line_id})...")
        
        # We pass line_id to the status webhook so it can reset the orders if the call fails
        status_url = f"{NGROK_BASE_URL}/voice/status?line_id={line_id}"
        
        call = await client.calls.create_async(
            url=webhook_url,
            to=supervisor_phone, 
            from_=twilio_number,
            status_callback=status_url,
            status_callback_event=['completed', 'busy', 'failed', 'no-answer']
        )
        print(f"✅ Call queued for {supervisor_name}! SID: {call.sid}")
    except Exception as e:
        print(f"❌ Failed to dispatch to {supervisor_name}: {e}")

async def async_dispatch_batch():
    """Finds lines with incomplete orders and prepares them for concurrent dispatch."""
    
    async_http_client = AsyncTwilioHttpClient()
    client = Client(account_sid, auth_token, http_client=async_http_client)
    
    db = SessionLocal()
    call_tasks = [] 
    
    try:
        # 1. Find all orders that are NOT completed and haven't been checked yet
        active_orders = db.query(ProductionOrder).filter(
            ProductionOrder.status != OrderStatus.COMPLETED,
            ProductionOrder.ai_status == AIStatus.NORMAL
        ).all()

        if not active_orders:
            print("✅ All factory schedules are completed or already being checked.")
            return

        # 2. Group by line_id so we only call a supervisor ONCE, even if they have 5 active orders
        lines_to_call = set()
        for order in active_orders:
            lines_to_call.add(order.line_id)

        print(f"⚠️ Found {len(lines_to_call)} lines needing status updates. Preparing batch dispatch...\n")

        # Track phone numbers to prevent accidental double-dialing across different lines
        active_numbers_in_batch = set()

        for line_id in lines_to_call:
            line = db.query(ProductionLine).filter(ProductionLine.line_id == line_id).first()
            
            if line and line.supervisor_phone:
                
                if line.supervisor_phone in active_numbers_in_batch:
                    print(f"⏳ Skipping Line {line.line_id}... Already calling {line.supervisor_name} in this batch.")
                    continue 
                
                active_numbers_in_batch.add(line.supervisor_phone)
                
                # 3. Mark ALL active orders for this line as 'INVESTIGATING'
                # This stops the auto-pilot from triggering another call 2 minutes later while this one is happening
                line_orders = db.query(ProductionOrder).filter(
                    ProductionOrder.line_id == line_id,
                    ProductionOrder.status != OrderStatus.COMPLETED
                ).all()
                
                for order in line_orders:
                    order.ai_status = AIStatus.INVESTIGATING
                
                # 4. Build the much simpler webhook URL
                query_params = urllib.parse.urlencode({
                    "line_id": line.line_id,
                    "supervisor": line.supervisor_name
                })
                webhook_url = f"{NGROK_BASE_URL}/voice/incoming?{query_params}"

                call_tasks.append(
                    fire_twilio_call(client, webhook_url, line.supervisor_phone, line.supervisor_name, line.line_id)
                )
        
        db.commit() 

        if call_tasks:
            await asyncio.gather(*call_tasks)
            print("\n🏁 All batch calls dispatched concurrently!")

    finally:
        db.close()
        await async_http_client.session.close()

def check_and_trigger_calls():
    asyncio.run(async_dispatch_batch())

if __name__ == "__main__":
    check_and_trigger_calls()