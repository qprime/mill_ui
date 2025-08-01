"""
[pipeline]
TODO: describe module functionality.
"""

def get_enabled_algorithms (job_cfg ):
    default ={
    "ramp":True ,
    "colinear":True ,
    "dedupe":True ,
    "adaptive_stepover":True 
    }
    return job_cfg .get ("algorithms",default )