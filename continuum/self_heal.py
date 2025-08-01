"""
[pipeline]
TODO: describe module functionality.
"""

from .patcher import replace_file_if_changed ,write_file 
from .git_ops import git_restore 
from .diff_tools import has_changes 

def auto_heal_file (path :str ,new_content :str ,review_mode :bool =True )->bool :
    """
    Attempt to apply a fix to a file, with optional review.
    """

    changed =replace_file_if_changed (path ,new_content )
    if not changed :
        return False 
    if review_mode :
        print (f"[Self-Heal] File {path } updated. Please review before commit.")
    return True 

def revert_if_broken (path :str ):
    git_restore (path )
    print (f"[Self-Heal] Reverted {path } to last good commit.")

def heal_or_revert (path :str ,new_content :str ,test_func )->bool :
    if auto_heal_file (path ,new_content ):
        if test_func ():
            print (f"[Self-Heal] {path } passed tests after update.")
            return True 
        else :
            print (f"[Self-Heal] {path } failed tests. Reverting.")
            revert_if_broken (path )
            return False 
    return False 
