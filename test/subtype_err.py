class A:
    def f(self, k:int)->int:
        return k


class B:
    pass

class C(B):
    def g(self, k:int)->int:
        return k + 500

def cf(x:A, a:int)->int:
    return x.f(a)

cf(A(), 40)
cf(C(), 40)
