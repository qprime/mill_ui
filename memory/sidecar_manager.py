"""
[memory]
TODO: describe module functionality.
"""

import json 
from pathlib import Path 
from ai_core .distillation_manager import distill 


SIDECAR_DIR =Path ("memory/sidecar")

def get_sidecar_path (chat_id ,persona ="sidecar"):

    return SIDECAR_DIR /f"{chat_id }_{persona }.json"

def load_sidecar (chat_id ,persona ="sidecar"):
    path =get_sidecar_path (chat_id ,persona )
    if not path .exists ():
        return []
    with open (path ,"r",encoding ="utf-8")as f :
        data =json .load (f )

    if isinstance (data ,dict )and "turns"in data :
        return data ["turns"]
    return data 

def save_distilled_sidecar (chat_id ,distilled ,persona ="sidecar"):
    out_path =get_sidecar_path (chat_id ,f"{persona }_distilled")
    with open (out_path ,"w",encoding ="utf-8")as f :

        try :
            obj =json .loads (distilled )
            json .dump (obj ,f ,indent =2 )
        except Exception :
            f .write (distilled )

def format_entries_for_distillation (entries ):
    return json .dumps (entries ,indent =2 )

def distill_sidecar (chat_id ,persona ="sidecar"):
    entries =load_sidecar (chat_id ,persona )
    if not entries :
        print (f"[sidecar_manager] No sidecar entries for chat_id={chat_id }, persona={persona }")
        return None 

    prompt =format_entries_for_distillation (entries )
    distilled_output =distill (prompt ,persona_name =persona )
    save_distilled_sidecar (chat_id ,distilled_output ,persona )
    return distilled_output 

def add_sidecar_entry (chat_id ,persona ,entry ):
    turns =load_sidecar (chat_id ,persona )
    turns .append (entry )
    path =get_sidecar_path (chat_id ,persona )
    path .parent .mkdir (parents =True ,exist_ok =True )
    with open (path ,"w",encoding ="utf-8")as f :
        json .dump ({"turns":turns },f ,indent =2 )

def prune_sidecar (chat_id ,persona ="sidecar",max_turns =5 ):
    turns =load_sidecar (chat_id ,persona )
    trimmed =turns [-max_turns :]
    path =get_sidecar_path (chat_id ,persona )
    path .parent .mkdir (parents =True ,exist_ok =True )
    with open (path ,"w",encoding ="utf-8")as f :
        json .dump ({"turns":trimmed },f ,indent =2 )

    print (f"[sidecar_manager] Pruned sidecar for chat_id={chat_id }, persona={persona } to {len (trimmed )} turns.")


if __name__ =="__main__":
    import sys 
    chat_id =sys .argv [1 ]
    print (f"Distilling sidecar for chat_id={chat_id } (persona='sidecar')...")
    output =distill_sidecar (chat_id ,persona ="sidecar")
    print ("\n[Distilled Sidecar Output]:\n",output )
