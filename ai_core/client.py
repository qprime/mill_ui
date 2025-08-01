"""
[AI core]
TODO: describe module functionality.
"""

import os 

def get_chat_completion (messages ,model ="gpt-4.1-mini",**kwargs ):
    import openai 
    api_key =os .getenv ("OPENAI_API_KEY")
    if not api_key :
        raise RuntimeError ("OPENAI_API_KEY not set in environment.")
    client =openai .OpenAI (api_key =api_key )
    resp =client .chat .completions .create (
    model =model ,messages =messages ,**kwargs 
    )
    return resp .choices [0 ].message .content 

def get_embedding (input ,model ="text-embedding-3-small",**kwargs ):
    import openai 
    api_key =os .getenv ("OPENAI_API_KEY")
    if not api_key :
        raise RuntimeError ("OPENAI_API_KEY not set in environment.")
    client =openai .OpenAI (api_key =api_key )
    resp =client .embeddings .create (input =input ,model =model ,**kwargs )
    return [d .embedding for d in resp .data ]
