# import os
# from openai import AsyncOpenAI
# from pydantic import BaseModel, Field
# from typing import List, Literal
# from dotenv import load_dotenv

# load_dotenv()

# class ExtractedFact(BaseModel):
#     fact_name: str = Field(description="Name of the data point (e.g., 'Task Name', 'Completion Percentage')")
#     fact_value: str = Field(description="The value of the data point")

# class CallAnalysis(BaseModel):
#     next_response: str = Field(description="The exact text to speak back to the user.")
#     sentiment: Literal["positive", "neutral", "negative", "frustrated"] = Field(description="The emotional state of the user.")
#     extracted_data: List[ExtractedFact] = Field(default_factory=list, description="List of facts gathered so far.")
#     unresolved_issues: List[str] = Field(default_factory=list, description="Questions asked by user or blockers that need human attention.")
#     is_complete: bool = Field(description="Set to true ONLY if the goal of the call is fully achieved.")

# class AIService:
#     def __init__(self):
#         api_key = os.getenv("OPENAI_API_KEY")
#         if not api_key:
#             raise ValueError("OPENAI_API_KEY missing from .env")
#         self.client = AsyncOpenAI(api_key=api_key)

#     async def get_ai_decision(
#         self, 
#         user_input: str, 
#         history: list, 
#         agent_persona: str, 
#         extraction_goal: str
#     ) -> CallAnalysis:
        
#         # ⚡ SPEED TWEAK 1: The Prompt Diet. 
#         # Removed all conversational fluff. LLMs process bullet points and strict commands faster.
#         system_prompt = f"""
#         {agent_persona}
#         GOAL: {extraction_goal}
#         RULES:
#         1. next_response MUST be 1 short sentence max. No filler words.
#         2. Extract 'Blocker' into extracted_data if mentioned.
#         3. If blocker is found, set is_complete=true and say ONLY: "Got it, logging that now. Have a great day!"
#         4. No follow-up questions if is_complete is true.
#         """

#         try:
#             response = await self.client.beta.chat.completions.parse(
#                 model="gpt-4o-mini", # ⚡ SPEED TWEAK 2: Swapped to the fastest model available!
#                 messages=[
#                     {"role": "system", "content": system_prompt},
#                     {"role": "user", "content": f"History: {history}\n\nUser said: {user_input}"}
#                 ],
#                 response_format=CallAnalysis, 
#                 temperature=0.2, 
#                 max_tokens=150 # ⚡ SPEED TWEAK 3: Lowered token ceiling (150 gives just enough room for the JSON formatting)
#             )

#             return response.choices[0].message.parsed
            
#         except Exception as e:
#             print(f"CRITICAL AI ERROR: {e}")
#             return CallAnalysis(
#                 next_response="I missed that. Can you repeat?",
#                 sentiment="neutral",
#                 extracted_data=[],
#                 unresolved_issues=["System connection error during processing"],
#                 is_complete=False
#             )

# ai_service = AIService()





import os
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from dotenv import load_dotenv

load_dotenv()

# 🌟 NEW: Model specifically for tracking the 5 orders per line
class OrderUpdate(BaseModel):
    order_sequence: int = Field(description="The number/sequence of the order being discussed (e.g., 1 for Order 1, 2 for Order 2)")
    status: Literal["PENDING", "IN_PROGRESS", "BLOCKED", "COMPLETED"] = Field(description="The current status of this specific order")
    blocker_reason: Optional[str] = Field(default=None, description="If status is BLOCKED, explain why. Otherwise, leave null.")

class CallAnalysis(BaseModel):
    next_response: str = Field(description="The exact text to speak back to the supervisor.")
    sentiment: Literal["positive", "neutral", "negative", "frustrated"] = Field(description="The emotional state of the user.")
    
    # 🌟 NEW: Replaced extracted_data with a strict list of order updates
    order_updates: List[OrderUpdate] = Field(default_factory=list, description="List of status updates for the orders discussed.")
    
    unresolved_issues: List[str] = Field(default_factory=list, description="Questions asked by user or blockers that need human manager attention.")
    is_complete: bool = Field(description="Set to true ONLY if you have successfully gathered the status of the current target order and any blockers.")

class AIService:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY missing from .env")
        self.client = AsyncOpenAI(api_key=api_key)

    async def get_ai_decision(
        self, 
        user_input: str, 
        history: list, 
        agent_persona: str, 
        extraction_goal: str
    ) -> CallAnalysis:
        
        # 🌟 NEW: Updated rules to handle multiple simultaneous order updates
        system_prompt = f"""
        {agent_persona}
        GOAL: {extraction_goal}
        RULES:
        1. next_response MUST be 1 short sentence max. Be conversational but brief.
        2. If the supervisor mentions completing an order, moving to the next, or facing a blocker, extract those into 'order_updates'.
        3. A supervisor might update multiple orders at once (e.g., "Order 1 is done, Order 2 is blocked"). Extract an update for EACH order mentioned.
        4. If a blocker is found, log the exact reason in 'blocker_reason'.
        5. Set is_complete=true if you have clear status updates and no further clarification is needed. If true, say a quick goodbye.
        """

        try:
            response = await self.client.beta.chat.completions.parse(
                model="gpt-4o-mini", 
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"History: {history}\n\nUser said: {user_input}"}
                ],
                response_format=CallAnalysis, 
                temperature=0.2, 
                max_tokens=250 # ⚡ SPEED TWEAK: Bumped slightly to allow for multiple order updates in JSON
            )

            return response.choices[0].message.parsed
            
        except Exception as e:
            print(f"CRITICAL AI ERROR: {e}")
            return CallAnalysis(
                next_response="I missed that. Can you repeat?",
                sentiment="neutral",
                order_updates=[],
                unresolved_issues=["System connection error during processing"],
                is_complete=False
            )

ai_service = AIService()