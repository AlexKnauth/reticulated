from imp4 import *

def f(k:{'x':Callable[[int], int]}, x)->int:
    return k.x(x)

class D:
    def x(self)->str:
        return 'a'

f(D(), 20)
