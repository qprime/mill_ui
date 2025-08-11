# path: skills/cam_generator/core/pass_reporter.py
# # desc: Collect per-pass metrics and write JSON.
# api: PassReporter
# tags: cam

import json
from pathlib import Path

class PassReporter:
    def __init__(self, job_name, output_dir):
        self.job_name = job_name
        self.output_dir = Path(output_dir)
        self.reports = []

    def add_pass_report(
        self,
        pass_name,
        point_count,
        z_min,
        z_max,
        time_min,
        removed_colinear,
        removed_deduped,
        algorithms,
        xy_km=None,
        z_km=None,
    ):
        r = {
            "pass": pass_name,
            "points": int(point_count),
            "z_min": round(float(z_min), 3),
            "z_max": round(float(z_max), 3),
            "estimated_time_min": round(float(time_min), 1),
            "colinear_removed": int(removed_colinear),
            "deduped_removed": int(removed_deduped),
            "algorithms": algorithms,
        }
        if xy_km is not None:
            r["xy_km"] = round(float(xy_km), 3)
        if z_km is not None:
            r["z_km"] = round(float(z_km), 3)
        self.reports.append(r)

    def write_json(self):
        out_path = self.output_dir / f"{self .job_name }_summary.json"
        with open(out_path, "w") as f:
            json.dump(self.reports, f, indent=2)
        print(f"\n[✓] Wrote summary to {out_path }")

    def print_summary(self):
        print("\n=== Pass Summary ===")
        for r in self.reports:
            print(f"• {r ['pass']} pass:")
            print(f"   Points         : {r ['points']}")
            print(f"   Z bounds       : {r ['z_min']} to {r ['z_max']} mm")
            print(f"   Estimated time : {r ['estimated_time_min']} min")
            if 'xy_km' in r:
                print(f"   XY distance    : {r['xy_km']} km")
            if 'z_km' in r:
                print(f"   Z distance     : {r['z_km']} km")
            print(f"   Colinear trim  : {r ['colinear_removed']}")
            print(f"   Deduped trim   : {r ['deduped_removed']}")
            print(f"   Algorithms     : {', '.join (r ['algorithms'])}")
