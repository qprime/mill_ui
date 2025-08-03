# path: pipelines/cam_generator/core/toggles.py
# type: configuration utility
# tags: cam, configuration, utilities, algorithms
# owner: cliff
# depends_on: None
# description: Provides default algorithm enablement states and toggles for CAM job configurations.

def get_enabled_algorithms(job_cfg):
    default = {
        "ramp": True,
        "colinear": True,
        "dedupe": True,
        "adaptive_stepover": True,
    }
    return job_cfg.get("algorithms", default)
