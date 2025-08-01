"""
[web]
TODO: describe module functionality.
"""

from flask import Flask ,render_template ,request ,jsonify 
from pathlib import Path 
import json 
import os 


from generate_image_api import generate_image_api 
from prompt_assist import assist_prompt 


HERE =Path (__file__ ).resolve ().parent 
CLIFF_ROOT =HERE .parent .parent 

PERSONAS_PATH =CLIFF_ROOT /"personas"/"cam_image_experts"/"ai_core.personas.json"
STYLES_PATH =CLIFF_ROOT /"personas"/"cam_image_experts"/"styles.json"

print ("HERE:",HERE )
print ("CLIFF_ROOT:",CLIFF_ROOT )
print ("PERSONAS_PATH:",PERSONAS_PATH )
print ("STYLES_PATH:",STYLES_PATH )
print ("PERSONAS_PATH exists:",PERSONAS_PATH .exists ())

app =Flask (__name__ ,static_folder ="static",template_folder ="templates")


app .add_url_rule ('/generate_image',view_func =generate_image_api ,methods =['POST'])
app .add_url_rule ('/assist_prompt',view_func =assist_prompt ,methods =['POST'])

@app .route ("/")
def index ():

    with open (PERSONAS_PATH ,"r")as pf :
        personas =json .load (pf )["personas"]
    with open (STYLES_PATH ,"r")as sf :
        styles =json .load (sf )["styles"]


    models =["gpt-image-1","dall-e-3"]
    model_sizes ={
    "gpt-image-1":["1024x1024","1792x1024","1024x1792"],
    "dall-e-3":["1024x1024"]
    }
    return render_template (
    "index.html",
    personas =personas ,
    styles =styles ,
    models =models ,
    model_sizes =model_sizes 
    )

if __name__ =="__main__":
    app .run (debug =True ,port =5000 )