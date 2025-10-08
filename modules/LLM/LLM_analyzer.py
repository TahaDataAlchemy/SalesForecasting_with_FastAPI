import os 
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage,SystemMessage
from modules.LLM.prompt import SYSTEM_PROMPT
from config import CONFIG
import json
from core.logger.logger import LOG
# os.environ["GROQ_API_KEY"] = CONFIG.groq_api_key

# llm = ChatGroq(model=CONFIG.model_name)

# def analyze_forecast(user_input:str):
#     messages = [
#         SystemMessage(content=SYSTEM_PROMPT),
#         HumanMessage(content=user_input)
#     ]
#     response = llm.invoke(messages,
#                           response_format = {"type":"json_object"})
#     return response.content

os.environ["GROQ_API_KEY"] = CONFIG.groq_api_key

# --- Initialize LLM ---
llm = ChatGroq(model=CONFIG.model_name)

# --- Helper function to analyze forecast with Groq ---
def analyze_forecast(user_input: str):
    try:
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_input)
        ]

        response = llm.invoke(
            messages,
            response_format={"type": "json_object"}  # ensures Groq tries to send valid JSON
        )

        # --- Try to parse the JSON ---
        try:
            parsed = json.loads(response.content)
        except json.JSONDecodeError:
            # If escaped or formatted badly, clean and re-parse
            cleaned = response.content.strip()
            cleaned = cleaned.replace("\n", "").replace("\\n", "").replace("\\", "")
            parsed = json.loads(cleaned)

        return parsed

    except Exception as e:
        LOG.error(f"LLM analysis failed: {e}")
        return {"error": "LLM analysis failed", "details": str(e)}
