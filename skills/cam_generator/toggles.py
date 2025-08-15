# path: skills/cam_generator/core/toggles.py
# # desc: Return enabled algorithm toggles.
# api: get_enabled_algorithms
# tags: cam

def get_enabled_algorithms(job_cfg):
    default = {
        "ramp": True,
        "colinear": True,
        "dedupe": True,
        "adaptive_stepover": True,
    }
    return job_cfg.get("algorithms", default)
