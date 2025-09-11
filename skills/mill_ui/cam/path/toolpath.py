
def move_comment(text:str): return {'kind':'comment','text':text}
def move_set_feed(feed:float): return {'kind':'set_feed','feed':feed}
def move_set_rpm(rpm:float): return {'kind':'set_rpm','rpm':rpm}
def move_rapid(x=None,y=None,z=None): return {'kind':'rapid','x':x,'y':y,'z':z}
def move_cut(x=None,y=None,z=None,feed=None): return {'kind':'cut','x':x,'y':y,'z':z,'feed':feed}
def move_retract(z:float): return {'kind':'retract','z':z}
