"""
[misc]
TODO: describe module functionality.
"""

import sys 
import subprocess 
import os 

PROJECT_ROOT =os .path .dirname (os .path .abspath (__file__ ))


ENTRYPOINTS ={
"web":"web.cliff_server.app",
"whisper":"local_services.whisper.whisper_server",
"context":"continuum.code_context",
"graph":"continuum.project_graph",



}

def usage ():
    print ("Usage: run.py [entrypoint] [args...]")
    print ("Available entrypoints:")
    for k in ENTRYPOINTS :
        print (f"  {k }: {ENTRYPOINTS [k ]}")
    sys .exit (1 )

def main ():
    if len (sys .argv )<2 or sys .argv [1 ]not in ENTRYPOINTS :
        usage ()
    entry =sys .argv [1 ]
    module =ENTRYPOINTS [entry ]
    args =sys .argv [2 :]


    os .chdir (PROJECT_ROOT )
    env =os .environ .copy ()
    env ["PYTHONPATH"]=PROJECT_ROOT 


    cmd =[sys .executable ,"-m",module ]+args 
    print (f"[RUN] {' '.join (cmd )} (cwd: {PROJECT_ROOT })")
    subprocess .run (cmd ,env =env )

if __name__ =="__main__":
    main ()
