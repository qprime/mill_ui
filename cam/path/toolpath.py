
def move_comment(text:str): return {'kind':'comment','text':text}
def move_set_feed(feed:float): return {'kind':'set_feed','feed':feed}
def move_set_rpm(rpm:float): return {'kind':'set_rpm','rpm':rpm}
def move_rapid(x=None,y=None,z=None): return {'kind':'rapid','x':x,'y':y,'z':z}
def move_cut(x=None,y=None,z=None,feed=None): return {'kind':'cut','x':x,'y':y,'z':z,'feed':feed}
def move_retract(z:float): return {'kind':'retract','z':z}

def offset_moves_z(moves: list[dict], offset: float) -> list[dict]:
    if offset <= 0.0:
        return moves
    adjusted: list[dict] = []
    for mv in moves:
        clone = dict(mv)
        if "z" in clone and clone["z"] is not None:
            z_val = float(clone["z"])
            if z_val <= 0.0:
                clone["z"] = z_val - offset
        adjusted.append(clone)
    return adjusted
