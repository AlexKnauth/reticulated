def f(x:int)->int:
    if x == 20:
        return 0
    a = f
    b = a 
    c = b
    d = f(20)
    return 12

print(f(10))
