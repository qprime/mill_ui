def get_enabled_algorithms(job_cfg):
    # fallback defaults if not defined
    default = {
        "ramp": True,
        "colinear": True,
        "dedupe": True,
        "adaptive_stepover": True
    }
    return job_cfg.get("algorithms", default)
