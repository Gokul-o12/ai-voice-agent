---
name: voice-agent-workflow
description: "WORKFLOW SKILL — Manage, debug, and expand the AI Voice Supervisor system (FastAPI, Twilio, OpenAI Realtime/GPT-4o, Redis, Ngrok). USE FOR: troubleshooting call connectivity; updating AI personas; managing Redis-based session state; configuring Ngrok for local Twilio testing; and adding new production line logic."
---

# AI Voice Supervisor Workflow

This skill guides the development and maintenance of the `voice_workforce` project, a real-time AI supervisor that calls production lines via Twilio.

## Project Architecture

- **FastAPI (`main.py`)**: Core API and TwiML provider.
- **Twilio**: Triggers outbound calls and streams audio via WebSockets.
- **OpenAI (`ai_service.py`)**: GPT-4o-mini/Realtime provides the intelligence and structured parsing.
- **Redis (`redis_client.py`)**: Stores transient call states (transcripts, current step, buffer).
- **PostgreSQL (`database.py`)**: Stores long-term audit trails, orders, and line status.
- **Ngrok**: Essential for local development to expose the FastAPI server to Twilio.

## Common Workflows

### 1. Local Development & Testing
When testing outbound calls from a local machine:
1. Ensure Ngrok is running: `ngrok http 8000`.
2. Update `BASE_URL` in `.env` to match the Ngrok HTTPS URL.
3. Verify Twilio Webhook targets the `/voice/outbound` or `/voice/stream` endpoints correctly.
4. Check the logs folder or terminal for "AUTO-PILOT ENGAGED".

### 2. Debugging Call Failures
If a call is triggered but the AI doesn't talk:
- **Check Redis**: Ensure `redis_manager.set_call_state` is being called with the `call.sid`.
- **Check TwiML**: Fetch `GET /voice/outbound` to ensure it returns valid XML with the correct WebSocket URL (`wss://.../voice/stream`).
- **Check WebSocket Logs**: Look for `WebSocketDisconnect` in the console or logs.
- **Check OpenAI API**: Verify `OPENAI_API_KEY` is active and `gpt-4o-mini` is accessible.

### 3. Modifying AI Behavior
To change what the AI asks or how it extracts data:
- **Persona**: Edit the system prompt in `app/services/ai_service.py`.
- **Extraction Logic**: Update the `OrderUpdate` or `CallAnalysis` Pydantic models in `ai_service.py`.
- **State Machine**: Update the `initial_state` dictionary in `main.py` (e.g., changing the `directive` or `step`).

### 4. Database & Logic Updates
- **New Line**: Add a `ProductionLine` entry via the database or a script.
- **Order Tracking**: The AI specifically looks for `PENDING`, `IN_PROGRESS`, `BLOCKED`, and `COMPLETED` statuses.

## Quality Checklist
- [ ] `BASE_URL` in `.env` starts with `https://` (required by Twilio).
- [ ] Redis is running (local or cloud).
- [ ] Pydantic models in `ai_service.py` match the frontend expectations in the React UI.
- [ ] Database migrations are applied if models changed.

## Example Prompts
- "I'm not hearing any audio from the AI during the call. How do I debug the WebSocket stream?"
- "Add a new status 'DELAYED' to the AI's order extraction logic."
- "How do I update the supervisor's phone number for Line A?"
- "Set up a new AI persona that is more polite and focuses on safety checks."
