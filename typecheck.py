import ast
from vis import Visitor
from typefinder import Typefinder
from typing import *
from relations import *
from exceptions import StaticTypeError
import typing, ast, utils

PRINT_WARNINGS = True
DEBUG_VISITOR = False
OPTIMIZED_INSERTION = False
STATIC_ERRORS = False

MAY_FALL_OFF = 1
WILL_RETURN = 0

def meet_mfo(m1, m2):
    if m1 == MAY_FALL_OFF or m2 == MAY_FALL_OFF:
        return MAY_FALL_OFF
    else:
        return WILL_RETURN

def warn(msg):
    if PRINT_WARNINGS:
        print('WARNING:', msg)

def cast(val, src, trg, msg, cast_function='retic_cas_cast'):
    src = normalize(src)
    trg = normalize(trg)

    lineno = str(val.lineno) if hasattr(val, 'lineno') else 'number missing'
    if not tycompat(src, trg):
        return error("%s: cannot cast from %s to %s (line %s)" % (msg, src, trg, lineno))
    elif src == trg:
        return val
    elif not OPTIMIZED_INSERTION:
        warn('Inserting cast at line %s: %s => %s' % (lineno, src, trg))
        return ast.Call(func=ast.Name(id=cast_function, ctx=ast.Load()),
                        args=[val, src.to_ast(), trg.to_ast(), ast.Str(s=msg)],
                        keywords=[], starargs=None, kwargs=None)
    else:
        # Specialized version that omits unnecessary casts depending what mode we're in,
        # e.g. cast-as-assert would omit naive upcasts
        pass

# Casting with unknown source type, as in cast-as-assertion 
# function return values at call site
def check(val, trg, msg, check_function='retic_cas_check', lineno=None):
    trg = normalize(trg)
    if lineno == None:
        lineno = str(val.lineno) if hasattr(val, 'lineno') else 'number missing'

    if not OPTIMIZED_INSERTION:
        warn('Inserting check at line %s: %s' % (lineno, trg))
        return ast.Call(func=ast.Name(id=check_function, ctx=ast.Load()),
                        args=[val, trg.to_ast(), ast.Str(s=msg)],
                        keywords=[], starargs=None, kwargs=None)
    else:
        # Specialized version that omits unnecessary casts depending what mode we're in,
        # e.g. this should be a no-op for everything but cast-as-assertion
        pass

def error(msg, error_function='retic_error'):
    if STATIC_ERRORS:
        raise StaticTypeError(msg)
    else:
        warn('Static error found')
        return ast.Call(func=ast.Name(id=error_function, ctx=ast.Load()),
                        args=[ast.Str(s=msg+' (statically detected)')], keywords=[], starargs=None,
                        kwargs=None)

def error_stmt(msg, lineno, mfo=MAY_FALL_OFF, error_function='retic_error'):
    if STATIC_ERRORS:
        raise StaticTypeError(msg)
    else:
        return ast.Expr(value=error(msg, error_function), lineno=lineno), mfo

class Typechecker(Visitor):
    typefinder = Typefinder()
    
    def dispatch_debug(self, tree, *args):
        ret = super().dispatch(tree, *args)
        print('results of %s:' % tree.__class__.__name__)
        if isinstance(ret, tuple):
            if isinstance(ret[0], ast.AST):
                print(ast.dump(ret[0]))
            if isinstance(ret[1], PyType):
                print(ret[1])
        if isinstance(ret, ast.AST):
            print(ast.dump(ret))
        return ret

    if DEBUG_VISITOR:
        dispatch = dispatch_debug

    def typecheck(self, n):
        n = self.preorder(n, {})
        n = ast.fix_missing_locations(n)
        return n

    def dispatch_scope(self, n, env, ret, initial_locals={}):
        env = env.copy()
        env.update(self.typefinder.dispatch_scope(n, env, initial_locals))
        body = []
        fo = MAY_FALL_OFF
        for s in n:
            (stmt, fo) = self.dispatch(s, env, ret)
            body.append(stmt)
        return (body, fo)

    def dispatch_statements(self, n, env, ret):
        body = []
        fo = MAY_FALL_OFF
        for s in n:
            (stmt, fo) = self.dispatch(s, env, ret)
            body.append(stmt)
        return (body, fo)
        
    def visitModule(self, n, env):
        (body, fo) = self.dispatch_scope(n.body, env, Void)
        return ast.Module(body=body)

## STATEMENTS ##
    # Import stuff
    def visitImport(self, n, env, ret):
        return (n, MAY_FALL_OFF)

    def visitImportFrom(self, n, env, ret):
        return (n, MAY_FALL_OFF)

    # Function stuff
    def visitFunctionDef(self, n, env, ret): #TODO: check defaults, handle varargs and kwargs
        args, argnames = self.dispatch(n.args, env)
        nty = env[n.name]
        
        env = env.copy()
        argtys = list(zip(argnames, nty.froms))
        initial_locals = dict(argtys + [(n.name, nty)])
        (body, fo) = self.dispatch_scope(n.body, env, nty.to, initial_locals)
        
        argchecks = [ast.Expr(value=check(ast.Name(id=arg, ctx=ast.Load()), ty, 'Argument of incorrect type', lineno=n.lineno),
                              lineno=n.lineno) for
                     (arg, ty) in argtys]

        if nty.to != Dyn and nty.to != Void and fo == MAY_FALL_OFF:
            return error_stmt('Return value of incorrect type', n.lineno)

        return (ast.FunctionDef(name=n.name, args=args,
                                 body=argchecks+body, decorator_list=n.decorator_list,
                                 returns=n.returns, lineno=n.lineno), MAY_FALL_OFF)
    
    def visitarguments(self, n, env):

        return n, [self.dispatch(arg) for arg in n.args]
    
    def visitarg(self, n):
        return n.arg

    def visitReturn(self, n, env, ret):
        if n.value:
            (value, ty) = self.dispatch(n.value, env)
            mfo = MAY_FALL_OFF if tyinstance(ty, Void) else WILL_RETURN
            value = cast(value, ty, ret, "Return value of incorrect type")
        else:
            mfo = MAY_FALL_OFF
            value = None
            if not tycompat(Void, ret):
                return error_stmt('Return value expected', n.lineno, mfo)
        return (ast.Return(value=value, lineno=n.lineno), mfo)

    # Assignment stuff
    def visitAssign(self, n, env, ret): #handle multiple targets
        (val, vty) = self.dispatch(n.value, env)
        ttys = []
        targets =[]
        for target in n.targets:
            (target, tty) = self.dispatch(target, env)
            ttys.append(tty)
            targets.append(target)
        try:
            meet = tymeet(ttys)
        except Bot:
            return error_stmt('Assignee of incorrect type', n.lineno)

        val = cast(val, vty, meet, "Assignee of incorrect type")
        return (ast.Assign(targets=targets, value=val, lineno=n.lineno), MAY_FALL_OFF)

    def visitAugAssign(self, n, env, ret):
        (target, tty) = self.dispatch(n.target, env)
        (value, _) = self.dispatch(n.value, env)
        optarget = utils.copy_assignee(target, ast.Load())

        assignment = ast.Assign(targets=[target], 
                                value=ast.BinOp(left=optarget,
                                                op=n.op,
                                                right=value),
                                lineno=n.lineno)
        
        return self.dispatch(assignment, env, ret)

    def visitDelete(self, n, env, ret):
        targets = []
        for t in n.targets:
            (value, ty) = self.dispatch(t, env)
            targets.append(value)
        return (ast.Delete(targets=targets, lineno=n.lineno), MAY_FALL_OFF)

    # Control flow stuff
    def visitIf(self, n, env, ret):
        (test, tty) = self.dispatch(n.test, env)
        (body, bfo) = self.dispatch_statements(n.body, env, ret)
        (orelse, efo) = self.dispatch_statements(n.orelse, env, ret) if n.orelse else (None, MAY_FALL_OFF)
        mfo = meet_mfo(bfo, efo)
        return (ast.If(test=test, body=body, orelse=orelse, lineno=n.lineno), mfo)

    def visitFor(self, n, env, ret):
        (target, tty) = self.dispatch(n.target, env)
        (iter, ity) = self.dispatch(n.iter, env)
        (body, bfo) = self.dispatch_statements(n.body, env, ret)
        (orelse, efo) = self.dispatch_statements(n.orelse, env, ret) if n.orelse else (None, MAY_FALL_OFF)
        mfo = meet_mfo(bfo, efo)
        return (ast.For(target=target, iter=cast(iter, ity, List(tty), 'iterator list of incorrect type'),
                        body=body, orelse=orelse, lineno=n.lineno), mfo)
        
    def visitWhile(self, n, env, ret):
        (test, tty) = self.dispatch(n.test, env)
        (body, bfo) = self.dispatch_statements(n.body, env, ret)
        (orelse, efo) = self.dispatch_statements(n.orelse, env, ret) if n.orelse else (None, MAY_FALL_OFF)
        mfo = meet_mfo(bfo, efo)
        return (ast.For(target=target, iter=iter, body=body, orelse=orelse, lineno=n.lineno), mfo)

    def visitWith(self, n, env, ret): #Seems like this is one of the few cases where we can impose structural types
        (context_expr, _) = self.dispatch(n.context_expr, env)
        (optional_vars, _) = self.dispatch(n.optional_vars, env) if n.optional_vars else (None, Dyn)
        (body, mfo) = self.dispatch_statements(n.body, env, ret)
        return (ast.With(context_expr=context_expr, optional_vars=optional_vars, body=body, lineno=n.lineno), mfo)
    
    # Class stuff
    def visitClassDef(self, n, env, ret):
        return (n, MAY_FALL_OFF)

    # Exception stuff
    # Python 3.2
    def visitTryExcept(self, n, env, ret):
        (body, mfo) = self.dispatch_statements(n.body, env, ret)
        handlers = []
        for handler in n.handlers:
            (handler, hfo) = self.dispatch(handler, env, ret)
            mfo = meet_mfo(mfo, hfo)
            handlers.append(handler)
        (orelse, efo) = self.dispatch(n.orelse, env, ret) if n.orelse else ([], mfo)
        mfo = meet_mfo(mfo, efo)
        return (ast.TryExcept(body=body, handlers=handlers, orelse=orelse, lineno=n.lineno), mfo)

    # Python 3.2
    def visitTryFinally(self, n, env, ret):
        (body, bfo) = self.dispatch_statements(n.body, env, ret)
        (finalbody, ffo) = self.dispatch_statements(n.finalbody, env, ret)
        if ffo == WILL_RETURN:
            return (TryFinally(body=body, finalbody=finalbody, lineno=n.lineno), ffo)
        else:
            return (TryFinally(body=body, finalbody=finalbody, lineno=n.lineno), bfo)
    
    # Python 3.3
    def visitTry(self, n, env, ret):
        (body, mfo) = self.dispatch_statements(n.body, env, ret)
        handlers = []
        for handler in n.handlers:
            (handler, hfo) = self.dispatch(handler, env, ret)
            mfo = meet_mfo(mfo, hfo)
            handlers.append(handler)
        (orelse, efo) = self.dispatch(n.orelse, env, ret) if n.orelse else ([], mfo)
        mfo = meet_mfo(mfo, efo)
        (finalbody, ffo) = self.dispatch_statements(n.finalbody, env, ret)
        if ffo == WILL_RETURN:
            return (Try(body=body, handlers=handlers, orelse=orelse, finalbody=finalbody, lineno=n.lineno), ffo)
        else:
            return (Try(body=body, handlers=handlers, orelse=orelse, finalbody=finalbody, lineno=n.lineno), mfo)

    def visitExceptHandler(self, n, env, ret):
        (type, _) = self.dispatch(n.type, env) if n.type else (None, Dyn)
        (body, mfo) = self.dispatch_statements(n.body, env, ret)
        return (ast.ExceptHandler(type=type, name=n.name, lineno=n.lineno), mfo)

    def visitRaise(self, n, env, ret):
        (exc, _) = self.dispatch(n.exc, env) if n.exc else (None, Dyn) # Can require to be a subtype of Exception
        (cause, _) = self.dispatch(n.cause, env) if n.cause else (None, Dyn) # Same
        return (ast.Raise(exc=exc, cause=cause, lineno=n.lineno), WILL_RETURN)

    def visitAssert(self, n, env, ret):
        (test, _) = self.dispatch(n.test, env)
        (msg, _) = self.dispatch(n.msg, env) if n.msg else (None, Dyn)
        return (ast.Assert(test=test, msg=msg, lineno=n.lineno), MAY_FALL_OFF)

    # Declaration stuff
    def visitGlobal(self, n, env, ret):
        return (n, MAY_FALL_OFF)

    def visitNonlocal(self, n, env, ret):
        return (n, MAY_FALL_OFF)

    # Miscellaneous
    def visitExpr(self, n, env, ret):
        (value, ty) = self.dispatch(n.value, env)
        return (ast.Expr(value=value, lineno=n.lineno), MAY_FALL_OFF)

    def visitPass(self, n, env, ret):
        return (n, MAY_FALL_OFF)

    def visitBreak(self, n, env, ret):
        return (n, MAY_FALL_OFF)

    def visitContinue(self, n, env, ret):
        return (n, MAY_FALL_OFF)

### EXPRESSIONS ###
    # Op stuff
    def visitBoolOp(self, n, env):
        values = []
        tys = []
        for value in n.values:
            (value, ty) = self.dispatch(value, env)
            values.append(value)
            tys.append(ty)
        ty = tyjoin(tys)
        return (ast.BoolOp(op=n.op, values=values), ty)

    def visitBinOp(self, n, env):
        (left, lty) = self.dispatch(n.left, env)
        (right, rty) = self.dispatch(n.right, env)
        node = ast.BinOp(left=left, op=n.op, right=right)
        stringy = tyinstance(lty, String) or tyinstance(rty, String)
        if isinstance(n.op, ast.Div):
            ty = primjoin([lty, rty], Float, Complex)
        elif isinstance(n.op, ast.Add):
            if stringy:
                if tyinstance(lty, String) and tyinstance(rty, String):
                    ty = String
                else:
                    ty = Dyn
            else: ty = primjoin([lty, rty])
        elif any([isinstance(n.op, op) for op in [ast.Sub, ast.Pow]]):
            ty = primjoin([lty, rty])
        elif isinstance(n.op, ast.Mult):
            if stringy:
                if any([tyinstance(ty, String) for ty in [lty, rty]]) and \
                        any([tyinstance(ty, Int) for ty in [lty, rty]]):
                    ty = String
                else: ty = Dyn
            else: ty = primjoin([lty, rty])
        elif any([isinstance(n.op, op) for op in [ast.FloorDiv, ast.Mod]]):
            ty = ty_join([lty, rty], Int, Float)
        elif any([isinstance(n.op, op) for op in [ast.BitOr, ast.BitAnd, ast.BitXor]]):
            ty = ty_join([lty, rty], Bool, Int)
        elif any([isinstance(n.op, op) for op in [ast.LShift, ast.RShift]]):
            ty = ty_join([lty, rty], Int, Int)

        return (node, ty)

    def visitUnaryOp(self, n, env):
        (operand, ty) = self.dispatch(n.operand, env)
        node = ast.UnaryOp(op=n.op, operand=operand)
        if isinstance(n.op, ast.Invert):
            ty = primjoin([ty], Int, Int)
        elif any([isinstance(n.op, op) for op in [ast.UAdd, ast.USub]]):
            ty = primjoin([ty])
        elif isinstance(op, ast.Not):
            ty = Bool
        return (node, ty)

    def visitCompare(self, n, env):
        (left, _) = self.dispatch(n.left, env)
        comparators = [comp for (comp, _) in [self.dispatch(ocomp, env) for ocomp in n.comparators]]
        return (ast.Compare(left=left, ops=n.ops, comparators=comparators), Bool)

    # Collections stuff    
    def visitList(self, n, env):
        if isinstance(n.ctx, ast.Store):
            return self.visitTuple(n, env)
        eltdata = [self.dispatch(x, env) for x in n.elts]
        elttys = [ty for (elt, ty) in eltdata]
        ty = tyjoin(elttys)
        elts = [elt for (elt, ty) in eltdata]
        return (ast.List(elts=elts, ctx=n.ctx), List(ty))

    def visitTuple(self, n, env):
        eltdata = [self.dispatch(x, env) for x in n.elts]
        tys = [ty for (elt, ty) in eltdata]
        elts = [elt for (elt, ty) in eltdata]
        return (ast.Tuple(elts=elts, ctx=n.ctx), Tuple(*tys))

    def visitDict(self, n, env):
        keydata = [self.dispatch(key, env) for key in n.keys]
        valdata = [self.dispatch(val, env) for val in n.values]
        keys, ktys = zip(*keydata)
        values, vtys = zip(*valdata)
        return (ast.Dict(keys=keys, values=values), Dict(tyjoin(ktys), tyjoin(vtys)))

    def visitSet(self, n, env):
        elts = [elt for (elt, _) in [self.dispatch(elt2, env) for elt2 in n.elts]]
        return (ast.Set(elts=elts), Dyn)

    def visitListComp(self, n, env):
        generators = self.dispatch(n.generators, env)
        elt, ety = self.dispatch(n.elt, env)
        return ast.ListComp(elt=elt, generators=generators), List(ety)

    def visitSetComp(self, n, env):
        generators = self.dispatch(n.generators, env)
        elt, ety = self.dispatch(n.elt, env)
        return ast.SetComp(elt=elt, generators=generators), Dyn

    def visitDictComp(self, n, env):
        generators = self.dispatch(n.generators, env)
        key, kty = self.dispatch(n.key, env)
        value, vty = self.dispatch(n.value, env)
        return ast.DictComp(key=key, value=value, generators=generators), Dict(kty, vty)

    def visitGeneratorExp(self, n, env):
        generators = self.dispatch(n.generators, env)
        elt, ety = self.dispatch(n.elt, env)
        return ast.GeneratorExp(elt=elt, generators=generators), Dyn

    def visitcomprehension(self, n, env):
        (iter, ity) = self.dispatch(n.iter, env)
        ifs = [if_ for (if_, _) in [self.dispatch(if2, env) for if2 in n.ifs]]
        (target, tty) = self.dispatch(n.target, env)
        return ast.comprehension(target=target, iter=cast(iter, ity, List(tty), 'Iterator list of incorrect type'), ifs=ifs)

    # Control flow stuff
    def visitYield(self, n, env):
        value, _ = self.dispatch(n.value, env) if n.value else (None, Void)
        return ast.Yield(value=value), Dyn

    def visitYieldFrom(self, n, env):
        value, _ = self.dispatch(n.value, env)
        return ast.YieldFrom(value=value), Dyn

    def visitIfExp(self, n, env):
        value, _ = self.dispatch(n.value, env)
        body, bty = self.dispatch(n.body, env)
        orelse, ety = self.dispatch(n.orelse, env)
        return ast.IfExp(value=value, body=body, orelse=orelse), tyjoin([bty,ety])

    # Function stuff
    def visitCall(self, n, env):
        def cast_args(argdata, fun, funty):
            if any([tyinstance(funty, x) for x in UNCALLABLES]):
                return error(''), Dyn
            elif tyinstance(funty, Dyn):
                return ([v for (v, s) in argdata],
                        cast(fun, Dyn, Function([s for (v, s) in argdata], Dyn), 
                             "Function of incorrect type"),
                        Dyn)
            elif tyinstance(funty, Function):
                if len(argdata) <= len(funty.froms):
                    args = [cast(v, s, t, "Argument of incorrect type") for ((v, s), t) in 
                            zip(argdata, funty.froms)]
#                    if len(argdata) < len(funty.froms):
#                        froms = funty.froms[len(argdata):]
#                        if froms[0].name == None:
#                            raise StaticTypeError()
#                    else: froms = []
#                    kws
#                    for kwarg in kwdata:
#                        kw = kwarg.arg
#                        tty = None
#                        for i in range(froms):
#                            param = froms[i]
#                            if param.name == kw:
#                                tty = param.type
#                                del froms[i]
#                                break
#                        if not tty and funty.kwfroms:
#                            froms = kwfroms.copy()
#                            if kw in froms:
#                                tty = froms[kw]
#                                del froms[kw]
#                        if not tty and funty.kw:
#                            tty = funty.kw
#                        if not tty:
#                            raise StaticTypeError
                            
#                    froms = funty.froms[
                    return (args, fun, funty.to)
                else: return error(''), Dyn
            elif tyinstance(funty, Object):
                if '__call__' in ty.members:
                    funty = funty.members['__call__']
                    return cast_args(args, atys, funty)
                else: return ([cast(v, s, Dyn, "Argument of incorrect type") for (v, s) in
                               argdata], fun, Dyn)
            else: return ([cast(v, s, Dyn, "Argument of incorrect type") for (v, s) in
                           argdata], fun, Dyn)

        (func, ty) = self.dispatch(n.func, env)
        argdata = [self.dispatch(x, env) for x in n.args]
        (args, func, ret) = cast_args(argdata, func, ty)
        call = ast.Call(func=func, args=args, keywords=n.keywords,
                        starargs=n.starargs, kwargs=n.kwargs)
        call = check(call, ret, "Return value of incorrect type")
        return (call, ret)

    def visitLambda(self, n, env):
        args, argnames = self.dispatch(n.args, env)
        params = [Dyn] * len(argnames)
        env = env.copy()
        env.update(dict(list(zip(argnames, params))))
        body, rty = self.dispatch(n.body, env)
        return ast.Lambda(args=args, body=body), Function(params, rty)

    # Variable stuff
    def visitName(self, n, env):
        try:
            ty = env[n.id]
            if isinstance(n.ctx, ast.Delete) and not tyinstance(ty, Dyn):
                return error('Attempting to delete statically typed id'), ty
        except KeyError:
            ty = Dyn
        return (n, ty)

    def visitAttribute(self, n, env):
        value, vty = self.dispatch(n.value, env)
        if tyinstance(vty, Object):
            try:
                ty = vty.members[n.attr]
                if isinstance(n.ctx, ast.Del):
                    return error('Attempting to delete statically typed attribute'), ty
            except KeyError:
                ty = Dyn
        elif tyinstance(vty, Dyn):
            ty = Dyn
        ans = ast.Attribute(value=value, attr=n.attr, ctx=n.ctx)
        if not isinstance(n.ctx, ast.Store):
            ans = check(ans, ty, 'Value of incorrect type in subscriptable')
        return ans, ty

    def visitSubscript(self, n, env):
        value, vty = self.dispatch(n.value, env)
        slice, ty = self.dispatch(n.value, env, vty)
        ans = ast.Slice(value=value, slice=slice, ctx=n.ctx)
        if not isinstance(n.ctx, ast.Store):
            ans = check(ans, ty, 'Value of incorrect type in subscriptable')
        return ans, ty

    def visitIndex(self, n, env, extty):
        value, vty = self.dispatch(n.value, env)
        if tyinstance(extty, List):
            value = cast(value, vty, Int, 'Indexing with non-integer type')
            ty = extty.type
        elif tyinstance(extty, String) or tyinstance(extty, Tuple):
            value = cast(value, vty, Int, 'Indexing with non-integer type')
            ty = Dyn
        elif tyinstance(extty, Dict):
            value = cast(value, vty, extty.keys, 'Indexing dict with non-key value')
            ty = extty.values
        elif tyinstance(extty, Object):
            # Expand
            ty = Dyn
        elif tyinstance(extty, Dyn):
            ty = Dyn
        else: 
            return error('Attmpting to index non-indexable value'), Dyn
        # More cases...?
        return ast.Index(value=value), ty

    def visitSlice(self, n, env, extty):
        lower, lty = self.dispatch(n.lower, env) if n.lower else (None, Void)
        upper, uty = self.dispatch(n.upper, env) if n.upper else (None, Void)
        step, sty = self.dispatch(n.step, env) if n.step else (None, Void)
        if tyinstance(extty, List):
            lower = cast(lower, vty, Int, 'Indexing with non-integer type') if lty != Void else lower
            upper = cast(upper, vty, Int, 'Indexing with non-integer type') if uty != Void else upper
            step = cast(step, vty, Int, 'Indexing with non-integer type') if sty != Void else step
            ty = extty
        elif tyinstance(extty, Object):
            # Expand
            ty = Dyn
        elif tyinstance(extty, Dyn):
            ty = Dyn
        else: 
            return error('Attmpting to slice non-sliceable value'), Dyn
        return ast.Slice(lower=lower, upper=upper, step=step), ty

    def visitExtSlice(self, n, env, extty):
        dims = [dim for (dim, _) in [self.dispatch(dim2, n, env, extty) for dim2 in n.dims]]
        return ast.ExtSlice(dims=dims), Dyn

    def visitStarred(self, n, env):
        value, _ = self.dispatch(n.value, env)
        return ast.Starred(value=value, ctx=n.ctx), Dyn

    # Literal stuff
    def visitNum(self, n, env):
        ty = Dyn
        v = n.n
        if type(v) == int:
            ty = Int
        elif type(v) == float:
            ty = Float
        elif type(v) == complex:
            ty = Complex
        return (n, ty)

    def visitStr(self, n, env):
        return (n, String)

    def visitBytes(self, n, env):
        return (n, Dyn)

    def visitEllipsis(self, n, env):
        return (n, Dyn)


# Probably gargbage
def make_static_instances(root):
    for n in ast.walk(root):
        if isinstance(n, ast.FunctionDef):
            for arg in n.args.args:
                if isinstance(arg.annotation, ast.Call) and \
                        isinstance(arg.annotation.func, ast.Name):
                    if arg.annotation.func.id == Instance.__name__:
                        arg.annotation.func.id = InstanceStatic.__name__
                        arg.annotation.args[0] = ast.Str(s=arg.annotation.args[0].id)
                    elif arg.annotation.func.id == Class.__name__:
                        arg.annotation.func.id = ClassStatic.__name__
                        arg.annotation.args[0] = ast.Str(s=arg.annotation.args[0].id)
                elif isinstance(arg.annotation, ast.Name) and \
                        not arg.annotation.id in [cls.__name__ for cls in PyType.__subclasses__()] and \
                        not arg.annotation.id in [cls.builtin.__name__ for cls in PyType.__subclasses__() if \
                                                      hasattr(cls, 'builtin') and cls.builtin]:
                    arg.annotation = ast.Call(func=ast.Name(id=InstanceStatic.__name__, ctx=arg.annotation.ctx),
                                              args=[ast.Str(s=arg.annotation.id)])
    return n

def make_dynamic_instances(root):
    for n in ast.walk(root):
        if isinstance(n, ast.FunctionDef):
            for arg in n.args.args:
                if isinstance(arg.annotation, ast.Call) and \
                        isinstance(arg.annotation.func, ast.Name):
                    if arg.annotation.func.id == InstanceStatic.__name__:
                        arg.annotation.func.id = Instance.__name__
                        arg.annotation.args[0] = ast.Name(id=arg.annotation.args[0].id, ctx=ast.Load())
                    elif arg.annotation.func.id == ClassStatic.__name__:
                        arg.annotation.func.id = Class.__name__
                        arg.annotation.args[0] = ast.Name(id=arg.annotation.args[0].id, ctx=ast.Load())
    return n
