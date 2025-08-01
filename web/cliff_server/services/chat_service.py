"""
[web]
TODO: describe module functionality.
"""

import logging 
import json 
from ai_core .context_manager import route_context 
from ai_core .distill_text import distill_text 
from ai_core .client import get_chat_completion 
from memory .chat_manager import log_chat_turn 
from memory .sidecar_manager import add_sidecar_entry ,load_sidecar ,distill_sidecar 

MAIN_CHAT_MODEL ="gpt-4.1-mini"
SIDECAR_PERSONA ="system"

def generate_chat_reply (data :dict )->dict :
    persona =data .get ("persona","cliff_core")
    raw_input =data .get ("input")or data .get ("prompt")or ""
    chat_id =data .get ("chat_id",None )

    distilled_result =distill_text (
    raw_input ,
    {"persona":persona ,"task_type":"chat"},
    strict_mode =True ,
    )

    cleaned =(
    distilled_result .get ("original_input",{}).get ("cleaned_text",raw_input )
    if isinstance (distilled_result ,dict )
    else raw_input 
    )
    distilled_prompt =(
    distilled_result .get ("distilled_text",cleaned )
    if isinstance (distilled_result ,dict )
    else cleaned 
    )

    routing =route_context (distilled_prompt ,persona )

    messages =[]
    system_prompt =routing .get ("system_prompt")if isinstance (routing ,dict )else None 
    if system_prompt :
        messages .append ({"role":"system","content":system_prompt })
    messages .append ({"role":"user","content":distilled_prompt })

    try :
        reply =get_chat_completion (
        messages =messages ,
        model =MAIN_CHAT_MODEL ,
        )
    except Exception as e :
        logging .error (f"Model call failed: {e }")
        reply ="[Model error: see logs]"

    log_chat_turn (
    persona =persona ,
    chat_id =chat_id ,
    user_input =raw_input ,
    cleaned =cleaned ,
    distilled =distilled_prompt ,
    routing =routing ,
    response =reply ,
    model =MAIN_CHAT_MODEL 
    )


    return {
    "persona":persona ,
    "chat_id":chat_id ,
    "user_input":raw_input ,
    "cleaned":cleaned ,
    "distilled":distilled_prompt ,
    "routing":routing ,
    "response":reply ,
    "model":MAIN_CHAT_MODEL ,
    "original_input":{
    "cleaned_text":cleaned ,
    "raw_input":raw_input ,
    },
    "distilled_input":distilled_prompt ,
    "CliffsDistillation":distilled_prompt ,
    "Response":reply ,
    }

def update_chat_summary (chat_id ,summary ):
    """
    Update chat summary in sidecar.
    """
    entry ={"summary":summary }
    add_sidecar_entry (chat_id ,SIDECAR_PERSONA ,entry )
    distill_sidecar (chat_id ,SIDECAR_PERSONA )
    logging .info (f"Updated summary for chat {chat_id }")

def update_chat_facts (chat_id ,facts_json ):
    """
    Update chat facts in sidecar.
    """
    if isinstance (facts_json ,str ):
        facts =json .loads (facts_json )
    else :
        facts =facts_json 
    entry ={"facts":facts }
    add_sidecar_entry (chat_id ,SIDECAR_PERSONA ,entry )
    distill_sidecar (chat_id ,SIDECAR_PERSONA )
    logging .info (f"Updated facts for chat {chat_id }")

def get_sidecar_data (chat_id ):
    """
    Return all sidecar entries (summary, facts, etc) for the chat.
    """
    try :
        turns =load_sidecar (chat_id ,SIDECAR_PERSONA )

        meta ={}
        for entry in turns :
            meta .update (entry )
        return meta 
    except Exception as e :
        logging .error (f"Failed to load sidecar for {chat_id }: {e }")
        return {}

