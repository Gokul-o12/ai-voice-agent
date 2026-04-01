from fastapi import FastAPI, Request, Response, Depends, WebSocket, WebSocketDisconnect, HTTPException
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream
from twilio.twiml.messaging_response import MessagingResponse
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import os
import json
import websockets
import asyncio
import base64
from twilio.rest import Client
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from pydantic import BaseModel
from typing import List
from fastapi.middleware.cors import CORSMiddleware
import os
from fastapi import HTTPException
from twilio.rest import Client
from fastapi import Request, Response


load_dotenv() 

from app.utils.redis_client import redis_manager
from app.services.ai_service import ai_service
from app.models.database import get_db, User, CallSession, CallAnalysisRecord, ProductionLine, ProductionOrder, SessionLocal, OrderStatus, AIStatus
from trigger_call import check_and_trigger_calls 

# ---------------------------------------------------------
# DATA TRANSFER OBJECTS (DTOs) FOR REAL DATA INGESTION
# ---------------------------------------------------------
class OrderSubmitDTO(BaseModel):
    order_sequence: int
    order_name: str
    # target_output: int = 0

class DailyScheduleDTO(BaseModel):
    line_id: str
    supervisor_name: str
    supervisor_phone: str
    orders: List[OrderSubmitDTO]

# ---------------------------------------------------------
# 🌟 AUTO-PILOT MANAGER
# ---------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_and_trigger_calls, 'interval', minutes=2)
    scheduler.start()
    print("\n⏰ AUTO-PILOT ENGAGED: AI will check the factory floor every 2 minutes...\n")
    yield 
    scheduler.shutdown()

app = FastAPI(title="AI Factory Voice Supervisor", lifespan=lifespan)

# 🌟 NEW: Allow the React frontend to talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# CORE API ENDPOINTS
# ---------------------------------------------------------

@app.api_route("/voice/outbound", methods=["GET", "POST"])
async def voice_outbound(request: Request, supervisor: str = "Supervisor", line_id: str = "Unknown"):
    """
    Twilio hits this endpoint the millisecond the supervisor answers the phone.
    We return TwiML telling Twilio to open a WebSocket tunnel to our AI.
    """
    host = request.headers.get("host")
    
    # Generate the XML instructions for Twilio
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <Response>
        <Connect>
            <Stream url="wss://{host}/voice/stream">
                <Parameter name="supervisor" value="{supervisor}" />
                <Parameter name="line_id" value="{line_id}" />
            </Stream>
        </Connect>
    </Response>"""
    
    return Response(content=twiml, media_type="text/xml")

from app.models.database import CallSession, OrderStatus

@app.post("/api/factory/call/{line_id}")
async def trigger_manual_call(line_id: str, db: Session = Depends(get_db)):
    """Instantly triggers an outbound call to the supervisor of a specific line."""
    
    # 1. Find the Line and Supervisor
    line = db.query(ProductionLine).filter(ProductionLine.line_id == line_id).first()
    if not line:
        raise HTTPException(status_code=404, detail="Production line not found.")

    # 2. Get Twilio Credentials
    TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_PHONE = os.getenv("TWILIO_PHONE_NUMBER")
    BASE_URL = os.getenv("BASE_URL") 

    if not all([TWILIO_SID, TWILIO_AUTH, TWILIO_PHONE, BASE_URL]):
        raise HTTPException(status_code=500, detail="Server missing Twilio credentials or BASE_URL.")

    try:
        # 3. Create a Database Call Session so the Audit Trail works later!
        new_call = CallSession(line_id=line_id, status="in-progress")
        db.add(new_call)
        db.commit()
        db.refresh(new_call)

        # 4. Gather current pending orders so the AI knows what to ask about
        pending_orders = db.query(ProductionOrder).filter(
            ProductionOrder.line_id == line_id,
            ProductionOrder.status != OrderStatus.COMPLETED
        ).order_by(ProductionOrder.order_sequence).all()
        
        schedule_text = ", ".join([f"Order {o.order_sequence}: {o.order_name}" for o in pending_orders])

        # 5. Tell Twilio to dial the phone!
        client = Client(TWILIO_SID, TWILIO_AUTH)
        call = client.calls.create(
            to=line.supervisor_phone,
            from_=TWILIO_PHONE,
            url=f"{BASE_URL}/voice/outbound?supervisor={line.supervisor_name}&line_id={line_id}" 
        )
        
        # 🌟 THE FIX: Create the AI's "Brain" in Redis so it doesn't crash!
        initial_state = {
            "step": "greeting",
            "transcript": [],
            "order_updates": [],
            "db_session_id": new_call.id, # Link it to the database
            "factory_context": {
                "line_id": line_id,
                "schedule": schedule_text,
                # Give the AI a specific opening line since this is a manual override
                "directive": f"Hello {line.supervisor_name}, I am calling manually from the Command Center to check on your line. How are things going?"
            }
        }
        await redis_manager.set_call_state(call.sid, initial_state)
        
        return {"message": f"Successfully dialing {line.supervisor_name}...", "call_sid": call.sid}
        
    except Exception as e:
        print(f"❌ Twilio API / Redis Error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger call: {str(e)}")

@app.get("/api/audit-trail")
def get_audit_trail(db: Session = Depends(get_db)):
    """Fetches the history of AI calls, including sentiment and transcripts."""
    # Grab the 50 most recent calls
    calls = db.query(CallSession).order_by(CallSession.start_time.desc()).limit(50).all()
    audit_data = []
    
    for call in calls:
        # Find the matching analysis and line data
        analysis = db.query(CallAnalysisRecord).filter(CallAnalysisRecord.call_id == call.id).first()
        line = db.query(ProductionLine).filter(ProductionLine.line_id == call.line_id).first()
        
        audit_data.append({
            "call_id": call.id,
            "line_id": call.line_id or "Unknown",
            "supervisor": line.supervisor_name if line else "Unknown",
            "status": call.status,
            "start_time": call.start_time.isoformat() if call.start_time else None,
            "sentiment": analysis.sentiment if analysis else "pending",
            "unresolved_issues": analysis.unresolved_issues if analysis else [],
            "transcript": analysis.transcript if analysis else []
        })
        
    return audit_data

@app.get("/api/factory/status")
def get_factory_status(db: Session = Depends(get_db)):
    """Fetches the real-time status of all production lines for the React UI."""
    lines = db.query(ProductionLine).all()
    dashboard_data = []
    
    for line in lines:
        pending_count = db.query(ProductionOrder).filter(
            ProductionOrder.line_id == line.line_id,
            ProductionOrder.status != OrderStatus.COMPLETED
        ).count()

        # 🌟 NEW: Count how many orders are explicitly BLOCKED
        blocked_count = db.query(ProductionOrder).filter(
            ProductionOrder.line_id == line.line_id,
            ProductionOrder.status == OrderStatus.BLOCKED
        ).count()

        # Determine the highest-priority status
        if blocked_count > 0:
            current_status = "Blocked"
        elif pending_count > 0:
            current_status = "Active"
        else:
            current_status = "Idle"

        dashboard_data.append({
            "id": line.line_id,
            "supervisor": line.supervisor_name,
            "status": current_status,
            "orders": pending_count
        })
        
    return dashboard_data

@app.post("/api/schedule/upload")
async def upload_real_schedule(schedule: DailyScheduleDTO, db: Session = Depends(get_db)):
    """API endpoint to receive real daily schedules from an external system or dashboard."""
    
    # 1. Check if the Production Line already exists, if not, create it.
    db_line = db.query(ProductionLine).filter(ProductionLine.line_id == schedule.line_id).first()
    
    if not db_line:
        db_line = ProductionLine(
            line_id=schedule.line_id,
            supervisor_name=schedule.supervisor_name,
            supervisor_phone=schedule.supervisor_phone
        )
        db.add(db_line)
        db.commit()
    else:
        # Update phone/name just in case there's a new supervisor today
        db_line.supervisor_name = schedule.supervisor_name
        db_line.supervisor_phone = schedule.supervisor_phone
        db.commit()

    # 2. Insert the real orders for today
    inserted_orders = []
    for order_data in schedule.orders:
        new_order = ProductionOrder(
            line_id=schedule.line_id,
            order_sequence=order_data.order_sequence,
            order_name=order_data.order_name,
            # target_output=order_data.target_output,
            status=OrderStatus.PENDING,
            ai_status=AIStatus.NORMAL
        )
        db.add(new_order)
        inserted_orders.append(new_order)
    
    db.commit()
    
    return {
        "message": "Real schedule successfully uploaded!",
        "line_id": schedule.line_id,
        "orders_added": len(inserted_orders)
    }

@app.post("/voice/incoming")
async def handle_incoming_call(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    call_sid = form_data.get("CallSid")
    user_phone = form_data.get("Called") or form_data.get("To") or "Unknown"

    line_id = request.query_params.get("line_id", "Unknown Line")
    supervisor_name = request.query_params.get("supervisor", "Supervisor")

    user = db.query(User).filter(User.phone_number == user_phone).first()
    if not user:
        user = User(phone_number=user_phone, name=supervisor_name, role="supervisor")
        db.add(user)
        db.commit()
        db.refresh(user)

    call_session = CallSession(call_sid=call_sid, user_id=user.id, line_id=line_id, status="in_progress")
    db.add(call_session)
    
    # Fetch ALL orders for this line to give the AI context
    active_orders = db.query(ProductionOrder).filter(ProductionOrder.line_id == line_id).order_by(ProductionOrder.order_sequence).all()
    
    # Build a readable schedule for the AI Prompt
    schedule_context = ""
    has_blocker = False
    blocker_msg = ""
    
    for order in active_orders:
        if order.status == OrderStatus.BLOCKED:
            has_blocker = True
            blocker_msg = f"Order {order.order_sequence} ({order.order_name}) is blocked due to '{order.blocker_reason}'"
            schedule_context += f"Order {order.order_sequence} ({order.order_name}): BLOCKED ({order.blocker_reason}). "
        else:
            schedule_context += f"Order {order.order_sequence} ({order.order_name}): {order.status.value}. "

    # Find the actual next order they are working on
    next_order = next((o for o in active_orders if o.status != OrderStatus.COMPLETED), None)

    # 🌟 NEW: Dynamic exact opening sentence based on the database
    if has_blocker:
        ai_opening_directive = f"Hello {supervisor_name}. I see {blocker_msg}. Have you been able to fix this, or is it still blocked today?"
    elif next_order:
        ai_opening_directive = f"Hello {supervisor_name}. Checking in on Line {line_id}. I see you are currently on Order {next_order.order_sequence}. How is that going?"
    else:
        ai_opening_directive = f"Hello {supervisor_name}. It looks like all orders are completed for today. Great job!"

    db.commit()
    db.refresh(call_session)

    # Save the expanded context into Redis
    await redis_manager.set_call_state(call_sid, {
        "step": "greeting",
        "attempts": 0,
        "transcript": [],
        "db_session_id": call_session.id,
        "user_id": user.id,
        "factory_context": {
            "line_id": line_id,
            "supervisor": supervisor_name,
            "schedule": schedule_context,
            "directive": ai_opening_directive  # 🌟 NEW DIRECTIVE
        }
    })

    response = VoiceResponse()
    
    # Brief pause to let the connection stabilize
    response.pause(length=1) 
    
    connect = Connect()
    host = request.headers.get("host") 
    stream = Stream(url=f"wss://{host}/voice/stream")
    
    stream.parameter(name="supervisor", value=supervisor_name)
    stream.parameter(name="line_id", value=line_id)
    
    connect.append(stream)
    response.append(connect)
    
    return Response(content=str(response), media_type="application/xml")


@app.post("/voice/ceo_inbound")
async def ceo_inbound_call(request: Request, db: Session = Depends(get_db)):
    """The CEO calls in for an audio report of blocked or pending orders."""
    total_lines = db.query(ProductionLine).count()
    
    # Find orders that are explicitly BLOCKED or behind schedule
    problem_orders = db.query(ProductionOrder).filter(
        ProductionOrder.status == OrderStatus.BLOCKED
    ).all()

    delay_count = len(problem_orders)

    if delay_count == 0:
        report = f"Good morning, CEO. All {total_lines} production lines are currently running smoothly. There are no blocked orders to report."
    else:
        report = f"Good morning. Out of {total_lines} lines, we currently have {delay_count} blocked orders. "
        
        for order in problem_orders:
            line = db.query(ProductionLine).filter(ProductionLine.line_id == order.line_id).first()
            supervisor = line.supervisor_name if line else "Unknown"
            reason = order.blocker_reason if order.blocker_reason else "Pending investigation."

            report += f"Line {order.line_id}, Order {order.order_sequence} is blocked. Supervisor {supervisor} reported the following issue: {reason}. "

    print(f"\n📢 CEO REPORT GENERATED: {report}\n")
    response = VoiceResponse()
    response.say(report)
    response.hangup()

    return Response(content=str(response), media_type="application/xml")


@app.post("/sms/ceo_report")
async def ceo_sms_report(request: Request, db: Session = Depends(get_db)):
    """The CEO texts for a written report."""
    form_data = await request.form()
    incoming_msg = form_data.get("Body", "").strip().lower()
    
    if incoming_msg not in ["status", "report", "update"]:
        response = MessagingResponse()
        response.message("Unrecognized command. Reply with 'Status' for the factory report.")
        return Response(content=str(response), media_type="application/xml")

    total_lines = db.query(ProductionLine).count()
    problem_orders = db.query(ProductionOrder).filter(
        ProductionOrder.status == OrderStatus.BLOCKED
    ).all()

    delay_count = len(problem_orders)

    if delay_count == 0:
        report = f"✅ *Factory Status Update*\nAll {total_lines} lines are running smoothly. No blocked orders."
    else:
        report = f"⚠️ *Factory Status Update*\nWe have {delay_count} blocked orders requiring attention:\n\n"
        
        for order in problem_orders:
            line = db.query(ProductionLine).filter(ProductionLine.line_id == order.line_id).first()
            supervisor = line.supervisor_name if line else "Unknown"
            reason = order.blocker_reason if order.blocker_reason else "Pending investigation."

            report += f"🛑 *Line {order.line_id} - Order {order.order_sequence}*\n"
            report += f"👨‍🔧 Supervisor: {supervisor}\n"
            report += f"📝 Issue: {reason}\n\n"

    print(f"\n📱 SMS REPORT GENERATED:\n{report}\n")
    response = MessagingResponse()
    response.message(report)

    return Response(content=str(response), media_type="application/xml")


@app.post("/voice/status")
async def call_status_webhook(request: Request, db: Session = Depends(get_db)):
    """Twilio hits this if the call drops, is busy, goes to voicemail, or finishes."""
    form_data = await request.form()
    call_status = form_data.get("CallStatus")
    line_id = request.query_params.get("line_id")

    # 🌟 FIX: We added "completed" to catch users who hang up early!
    if call_status in ["busy", "failed", "no-answer", "completed"]:
        print(f"\n⚠️ CALL ENDED ({call_status}). Checking if Line {line_id} needs a reset...\n")
        
        # Find any orders still stuck in INVESTIGATING
        stuck_orders = db.query(ProductionOrder).filter(
            ProductionOrder.line_id == line_id,
            ProductionOrder.ai_status == AIStatus.INVESTIGATING
        ).all()
        
        # If we found stuck orders, the human hung up before the AI finished saving data!
        if stuck_orders:
            print(f"🔄 Human hung up early! Resetting AI status so Auto-Pilot tries again later.")
            for order in stuck_orders:
                order.ai_status = AIStatus.NORMAL
            
            db.commit()
        else:
            print("✅ Call ended normally and AI already saved the data.")

    return Response(status_code=200)


@app.websocket("/voice/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("\n🟢 WEBSOCKET CONNECTED! Twilio tunnel opened.")
    
    try:
        DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
        if not DEEPGRAM_API_KEY:
            print("❌ ERROR: DEEPGRAM_API_KEY is missing!")
            await websocket.close()
            return

        dg_url = "wss://api.deepgram.com/v1/listen?model=nova-2&encoding=mulaw&sample_rate=8000&channels=1&endpointing=500"
        headers = {"Authorization": f"Token {DEEPGRAM_API_KEY}"}

        try:
            dg_connection = websockets.connect(dg_url, additional_headers=headers)
        except Exception as e:
            print(f"❌ DEEPGRAM CONNECTION FAILED: {e}")
            await websocket.close()
            return

        async with dg_connection as dg_ws:
            print("🧠 Connected to Deepgram Nova-2 Engine!")
            
            call_sid = None
            stream_sid = None
            supervisor = "Supervisor"
            line_id = "Unknown"
            transcript_buffer = ""
            
            is_ai_speaking = False 
            
            # 🌟 NEW: The Conveyor Belt for STT -> LLM
            phrase_queue = asyncio.Queue()

            async def unlock_microphone(seconds):
                nonlocal is_ai_speaking
                await asyncio.sleep(seconds)
                is_ai_speaking = False
                print("\n🟢 AI finished speaking. Microphone unlocked.")

            # --- TASK 1: TWILIO LISTENER ---
            async def receive_from_twilio():
                nonlocal call_sid, stream_sid, supervisor, line_id, is_ai_speaking
                try:
                    while True:
                        data = await websocket.receive_text()
                        msg = json.loads(data)

                        if msg['event'] == 'start':
                            stream_sid = msg['start']['streamSid']
                            call_sid = msg['start']['callSid']
                            custom_params = msg['start'].get('customParameters', {})
                            supervisor = custom_params.get('supervisor', 'Supervisor')
                            line_id = custom_params.get('line_id', 'Unknown')
                            print(f"🎬 LISTENING TO: {supervisor} (Line {line_id})...")
                            
                            state = await redis_manager.get_call_state(call_sid)
                            
                            if state.get("step") == "greeting":
                                ctx = state.get("factory_context", {})
                                greeting_text = ctx.get("directive", f"Hello {supervisor}, how is everything going?")
                                print(f"🤖 SYSTEM GREETING: {greeting_text}")
                                
                                state["transcript"].append({"user": "System called the supervisor.", "ai": greeting_text})
                                state["step"] = "chatting"
                                await redis_manager.set_call_state(call_sid, state)
                                
                                word_count = len(greeting_text.split())
                                talk_time = (word_count / 2.5) + 1.0
                                is_ai_speaking = True
                                asyncio.create_task(unlock_microphone(talk_time))

                                host = websocket.headers.get("host")
                                TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
                                TWILIO_AUTH = os.getenv("TWILIO_AUTH_TOKEN")
                                twilio_client = Client(TWILIO_SID, TWILIO_AUTH)
                                
                                twiml = f'<Response><Say>{greeting_text}</Say><Connect><Stream url="wss://{host}/voice/stream"><Parameter name="supervisor" value="{supervisor}"/><Parameter name="line_id" value="{line_id}"/></Stream></Connect></Response>'
                                twilio_client.calls(call_sid).update(twiml=twiml)

                        elif msg['event'] == 'media':
                            audio_bytes = base64.b64decode(msg['media']['payload'])
                            await dg_ws.send(audio_bytes)

                        elif msg['event'] == 'stop':
                            break
                except WebSocketDisconnect:
                    print("🔴 Twilio disconnected.")
                except Exception as e:
                    print(f"❌ ERROR IN TWILIO STREAM: {e}")

            # --- TASK 2: DEEPGRAM LISTENER (The Ears) ---
            async def receive_from_deepgram():
                nonlocal transcript_buffer, call_sid, supervisor, line_id, is_ai_speaking
                silence_count = 0  
                
                try:
                    while True:
                        try:
                            dg_msg_str = await asyncio.wait_for(dg_ws.recv(), timeout=15.0)
                        except asyncio.TimeoutError:
                            if not call_sid or is_ai_speaking:
                                continue 
                                
                            silence_count += 1
                            print(f"\n⚠️ SILENCE DETECTED (Strike {silence_count})")
                            
                            TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
                            TWILIO_AUTH = os.getenv("TWILIO_AUTH_TOKEN")
                            twilio_client = Client(TWILIO_SID, TWILIO_AUTH)
                            host = websocket.headers.get("host")
                            
                            if silence_count == 1:
                                print("🤖 AI: Are you still there?")
                                twiml = f'<Response><Say>Are you still there?</Say><Connect><Stream url="wss://{host}/voice/stream"><Parameter name="supervisor" value="{supervisor}"/><Parameter name="line_id" value="{line_id}"/></Stream></Connect></Response>'
                                is_ai_speaking = True
                                asyncio.create_task(unlock_microphone(2.5)) 
                                await asyncio.to_thread(twilio_client.calls(call_sid).update, twiml=twiml)
                                continue 
                                
                            elif silence_count >= 2:
                                print("🔴 AI: Hanging up due to inactivity. Resetting database.")
                                twiml = '<Response><Say>I haven\'t heard anything, so I will check back later. Goodbye.</Say><Hangup/></Response>'
                                await asyncio.to_thread(twilio_client.calls(call_sid).update, twiml=twiml)
                                
                                def reset_stuck_db():
                                    db = SessionLocal()
                                    stuck_orders = db.query(ProductionOrder).filter(
                                        ProductionOrder.line_id == line_id,
                                        ProductionOrder.ai_status == AIStatus.INVESTIGATING
                                    ).all()
                                    for o in stuck_orders:
                                        o.ai_status = AIStatus.NORMAL
                                    db.commit()
                                    db.close()
                                    
                                await asyncio.to_thread(reset_stuck_db)
                                break 

                        dg_msg = json.loads(dg_msg_str)

                        if dg_msg.get('type') == 'Results':
                            is_final = dg_msg.get('is_final', False)
                            speech_final = dg_msg.get('speech_final', False)
                            
                            try:
                                transcript = dg_msg['channel']['alternatives'][0]['transcript']
                            except (KeyError, IndexError):
                                transcript = ""

                            if transcript and is_final:
                                transcript_buffer += transcript + " "

                            if speech_final and transcript_buffer.strip():
                                final_text = transcript_buffer.strip()
                                
                                if is_ai_speaking:
                                    print(f"🔇 Ignored factory noise while AI was talking: '{final_text}'")
                                    transcript_buffer = "" 
                                    continue 

                                # 🌟 THE FIX: Put the text on the conveyor belt and immediately go back to listening!
                                await phrase_queue.put(final_text)
                                print(f"\n🗣️ STT DETECTED: {final_text} (Sent to LLM Queue)")
                                
                                transcript_buffer = "" 
                                silence_count = 0  

                except websockets.exceptions.ConnectionClosed:
                    print("🔴 Deepgram disconnected.")
                except Exception as e:
                    print(f"❌ ERROR IN DEEPGRAM STREAM: {e}")

            # --- TASK 3: LLM WORKER (The Brain) ---
            async def llm_worker():
                nonlocal call_sid, supervisor, line_id, is_ai_speaking
                try:
                    while True:
                        # 1. Wait for words to arrive on the conveyor belt
                        text_to_process = await phrase_queue.get()
                        
                        # 2. If the user said multiple sentences quickly, combine them into one request!
                        while not phrase_queue.empty():
                            text_to_process += " " + await phrase_queue.get()

                        print(f"🧠 LLM PROCESSING: {text_to_process}")
                        
                        state = await redis_manager.get_call_state(call_sid)
                        ctx = state.get("factory_context", {})
                        
                        factory_goal = "Extract status updates for the orders and log any blockers."
                        factory_persona = f"You are speaking with {supervisor} about Line {line_id}. Current Schedule: {ctx.get('schedule')}"
                        
                        ai_data = await ai_service.get_ai_decision(text_to_process, state["transcript"], factory_persona, factory_goal)
                        print(f"🤖 AI RESPONDED: {ai_data.next_response}")

                        word_count = len(ai_data.next_response.split())
                        talk_time = (word_count / 2.5) + 1.0 
                        is_ai_speaking = True
                        asyncio.create_task(unlock_microphone(talk_time))
                        print(f"🔴 Locking mic for {talk_time:.1f}s while AI speaks.")

                        host = websocket.headers.get("host")
                        TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
                        TWILIO_AUTH = os.getenv("TWILIO_AUTH_TOKEN")
                        twilio_client = Client(TWILIO_SID, TWILIO_AUTH)

                        line_id_context = ctx.get("line_id")

                        if ai_data.is_complete:
                            twiml = f'<Response><Say>{ai_data.next_response}</Say><Hangup/></Response>'
                        else:
                            twiml = f'<Response><Say>{ai_data.next_response}</Say><Connect><Stream url="wss://{host}/voice/stream"><Parameter name="supervisor" value="{supervisor}"/><Parameter name="line_id" value="{line_id_context}"/></Stream></Connect></Response>'
                        
                        await asyncio.to_thread(twilio_client.calls(call_sid).update, twiml=twiml)

                        # DB Background Save
                        async def save_db_in_background(current_call_sid, current_state, current_ctx, ai_result, text_said):
                            try:
                                current_state["transcript"].append({"user": text_said, "ai": ai_result.next_response})
                                extracted_updates = [update.model_dump() for update in ai_result.order_updates]
                                current_state["order_updates"] = current_state.get("order_updates", []) + extracted_updates
                                current_state["unresolved_issues"] = ai_result.unresolved_issues 
                                await redis_manager.set_call_state(current_call_sid, current_state)

                                if ai_result.is_complete:
                                    db = SessionLocal()
                                    db_session_id = current_state.get("db_session_id")
                                    line_id_context = current_ctx.get("line_id")
                                    
                                    if db_session_id:
                                        db_call = db.query(CallSession).filter(CallSession.id == db_session_id).first()
                                        if db_call:
                                            db_call.status = "completed"
                                        
                                        for update in ai_result.order_updates:
                                            db_order = db.query(ProductionOrder).filter(
                                                ProductionOrder.line_id == line_id_context,
                                                ProductionOrder.order_sequence == update.order_sequence
                                            ).first()
                                            
                                            if db_order:
                                                db_order.status = update.status
                                                db_order.blocker_reason = update.blocker_reason
                                                db_order.ai_status = AIStatus.RESOLVED
                                        
                                        stuck_orders = db.query(ProductionOrder).filter(
                                            ProductionOrder.line_id == line_id_context,
                                            ProductionOrder.ai_status == AIStatus.INVESTIGATING
                                        ).all()
                                        for stuck_order in stuck_orders:
                                            stuck_order.ai_status = AIStatus.NORMAL
                                        
                                        analysis_record = CallAnalysisRecord(
                                            call_id=db_session_id,
                                            sentiment=ai_result.sentiment,
                                            extracted_data=current_state.get("order_updates", []),      
                                            unresolved_issues=current_state.get("unresolved_issues", []), 
                                            transcript=current_state.get("transcript", [])               
                                        )
                                        db.add(analysis_record)
                                        db.commit()
                                        db.close()
                            except Exception as ex:
                                print(f"❌ Background DB Error: {ex}")

                        asyncio.create_task(save_db_in_background(call_sid, state, ctx, ai_data, text_to_process))
                        
                except Exception as e:
                    print(f"❌ ERROR IN LLM WORKER: {e}")

            # 🌟 RUN ALL 3 TASKS AT THE SAME TIME
            await asyncio.gather(receive_from_twilio(), receive_from_deepgram(), llm_worker())

    except Exception as e:
        print(f"❌ FATAL WEBSOCKET CRASH: {e}")