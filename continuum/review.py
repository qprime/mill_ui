"""
[pipeline]
TODO: describe module functionality.
"""

import os 
from .diff_tools import get_unified_diff 

def dump_diff_for_review (file :str ,old :str ,new :str ,out_dir :str ="continuum_review")->str :
    os .makedirs (out_dir ,exist_ok =True )
    diff_path =os .path .join (out_dir ,file .replace ("/","__")+".diff")
    with open (diff_path ,"w",encoding ="utf-8")as f :
        f .write (get_unified_diff (old ,new ,filename =file ))
    return diff_path 

def summarize_changes (file :str ,old :str ,new :str )->str :
    old_lines =len (old .splitlines ())
    new_lines =len (new .splitlines ())
    delta =new_lines -old_lines 
    if delta ==0 :
        return f"{file }: {old_lines } lines (no net change)"
    sign ="+"if delta >0 else "-"
    return f"{file }: {old_lines }->{new_lines } lines ({sign }{abs (delta )})"

def request_human_review (file :str ,diff_path :str ):
    print (f"Please review changes for {file }:\n  {diff_path }")
