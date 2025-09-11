
GEOM_MM_PLACES=3
FEED_MM_MIN_PLACES=1
def round_mm(v:float)->float: return round(float(v),GEOM_MM_PLACES)
def round_feed(v:float)->float: return round(float(v),FEED_MM_MIN_PLACES)
def clamp(v:float, lo:float, hi:float)->float: return max(lo, min(hi, v))
