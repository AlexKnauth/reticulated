## The main module for transient check insertion. This relies on
## .retic_type nodes having been inserted by typecheck.py.


from . import copy_visitor, typing, typeparser, retic_ast, ast_trans, flags, exc, scope
import ast, copy

def assign_type(x, v):
    x.retic_type = v.retic_type
    return x

def generateArgumentProtectors(n: ast.arguments, lineno: int, col_offset:int)->typing.List[ast.Expr]:
    ## Given a set of arguments from a FunctionDef, generate the
    ## checks that need to be inserted at function entry in order to
    ## detect incorrect argument values.
    prots = []
    for arg in n.args:
        prots.append(ast.Expr(value=retic_ast.ProtCheck(value=assign_type(ast.Name(id=arg.arg,
                                                                               ctx=ast.Load(), lineno=lineno, col_offset=col_offset),
                                                                      arg),
                                                    type=arg.retic_type, lineno=lineno, col_offset=col_offset),
                              lineno=lineno, col_offset=col_offset))
    for arg in n.kwonlyargs:
        prots.append(ast.Expr(value=retic_ast.ProtCheck(value=assign_type(ast.Name(id=arg.arg,
                                                                               ctx=ast.Load(), lineno=lineno, col_offset=col_offset),
                                                                      arg),
                                                    type=arg.retic_type, lineno=lineno, col_offset=col_offset),
                              lineno=lineno, col_offset=col_offset))
    if n.vararg:
        prots.append(ast.Expr(value=retic_ast.ProtCheck(value=assign_type(ast.Name(id=n.vararg.arg,
                                                                               ctx=ast.Load(), lineno=lineno, col_offset=col_offset),
                                                                      n.vararg),
                                                    type=n.vararg.retic_type, lineno=lineno,
                                                    col_offset=col_offset), lineno=lineno, col_offset=col_offset))
    if n.kwarg:
        prots.append(ast.Expr(value=retic_ast.ProtCheck(value=assign_type(ast.Name(id=n.kwarg.arg,
                                                                               ctx=ast.Load(), lineno=lineno, col_offset=col_offset),
                                                                      n.kwarg),
                                                    type=n.kwarg.retic_type, lineno=lineno,
                                                    col_offset=col_offset), lineno=lineno, col_offset=col_offset))
    return prots



class CheckInserter(copy_visitor.CopyVisitor):
    ## The main visitor. Outputs an AST with checks inserted. Here
    ## we're blindly inserting checks wherever they might possibly be
    ## needed, and will rely on other passes to remove extraneous ones
    ## (like where a value is being checked against Dyn)

    ## Usage: CheckInserter().preorder(ast)
    
    def visitModule(self, n):
        return ast.Module(body=self.dispatch(n.body, set()))
    
    def visitFunctionDef(self, n, *args):
        fargs = self.dispatch(n.args, *args)
        decorator_list = [self.dispatch(dec, *args) for dec in n.decorator_list]
        body = self.dispatch_scope(n.body, *args)
        arg_protectors = generateArgumentProtectors(n.args, n.lineno, n.col_offset)
        return ast_trans.FunctionDef(name=n.name, args=fargs,
                                     body=arg_protectors+body, decorator_list=decorator_list,
                                     returns=n.returns, 
                                     lineno=n.lineno, col_offset=n.col_offset)

    def visitCall(self, n, *args):
        call =  ast_trans.Call(func=self.dispatch(n.func, *args),
                               args=self.reduce(n.args, *args),
                               keywords=[ast.keyword(arg=k.arg, value=self.dispatch(k.value, *args))\
                                         for k in n.keywords],
                               starargs=self.dispatch(n.starargs, *args) if getattr(n, 'starargs', None) else None,
                               kwargs=self.dispatch(n.kwargs, *args) if getattr(n, 'kwargs', None) else None,
                               lineno=n.lineno, col_offset=n.col_offset)
        call.retic_type = n.retic_type
        return retic_ast.Check(value=call, type=n.retic_type, lineno=n.lineno, col_offset=n.col_offset)
        
    def visitAttribute(self, n, *args):
        attr = ast.Attribute(value=self.dispatch(n.value, *args),
                             attr=n.attr, ctx=n.ctx,
                             lineno=n.lineno, col_offset=n.col_offset)
        if isinstance(n.ctx, ast.Load):
            attr.retic_type = n.retic_type
            return retic_ast.Check(value=attr, type=n.retic_type, lineno=n.lineno, col_offset=n.col_offset)
        else: return attr

    def visitSubscript(self, n, *args):
        value = self.dispatch(n.value, *args)
        slice = self.dispatch(n.slice, *args)
        sub = ast.Subscript(value=value, slice=slice, ctx=n.ctx, lineno=n.lineno, col_offset=n.col_offset)
        if isinstance(n.ctx, ast.Load):
            sub.retic_type = n.retic_type
            return retic_ast.Check(value=sub,
                                   type=n.retic_type, lineno=n.lineno, col_offset=n.col_offset)
        else: return sub

        
    # Need to insert a check for each variable target
    #
    # So, if our statement is 
    #  x = y = z
    # We need to ensure that z has the types of x and y.
    # However, for non-variables, we don't need to worry:
    #  x[0] = y.a = z
    # No checks needed here, because checks will be used at dereferences.
    # For destructuring assignment we get weirder. Say we have
    #  x, y = z 
    # with x:int, y:str, z:dyn.
    # We can also have starred assignment.
    #  x, *y, z = w
    # with x:int, y:List[str], z:int, w:dyn
    # To handle these things, we generate a list of checks and
    # put them in an ExpandSeq node, which sequences
    # statements.
    def destruct_to_checks(self, lhs: ast.expr):
        
        if isinstance(lhs, ast.Name):
            return [ast.Expr(value=retic_ast.ProtCheck(value=assign_type(ast.Name(id=lhs.id, 
                                                                              ctx=ast.Load(), lineno=lhs.lineno, col_offset=lhs.col_offset),
                                                                     lhs), 
                                                   type=lhs.retic_type, lineno=lhs.lineno, col_offset=lhs.col_offset),
                             lineno=lhs.lineno, col_offset=lhs.col_offset)]
        elif isinstance(lhs, ast.Tuple) or isinstance(lhs, ast.List):
            return sum((self.destruct_to_checks(targ) for targ in lhs.elts), [])
        elif isinstance(lhs, ast.Starred):
            return self.destruct_to_checks(lhs.value)
        elif isinstance(lhs, ast.Attribute) or isinstance(lhs, ast.Subscript):
            return []
        else: 
            raise exc.InternalReticulatedError(lhs)

    def visitFor(self, n, *args):
        # We need to guard the internal body of for loops to make sure that the iteration target has the expected type.

        prots = self.destruct_to_checks(n.target)
        return ast.For(target=self.dispatch(n.target, *args),
                       iter=self.dispatch(n.iter, *args),
                       body=prots + self.dispatch_statements(n.body, *args),
                       orelse=self.dispatch_statements(n.orelse, *args),
                       lineno=n.lineno, col_offset=n.col_offset)

    def visitAssign(self, n, *args):
        value = self.dispatch(n.value, *args)
        prots = []
        
        for target in n.targets:
            # Don't recur on the targets since we can never have a LHS check
            

            
            # If the target is a single assignment, let's just put the check on the RHS.
            # If it's something more complicated, leave the check till after the assignment
            if isinstance(target, ast.Name) or isinstance(target, ast.Attribute) or isinstance(target, ast.Subscript):
                value = retic_ast.Check(value=value, type=target.retic_type, lineno=value.lineno, col_offset=value.col_offset)
            else:
                prots += self.destruct_to_checks(target)
                
        return retic_ast.ExpandSeq(body=[ast.Assign(targets=n.targets, value=value, lineno=n.lineno, col_offset=n.col_offset)] + prots,
                                   lineno=value.lineno, col_offset=value.col_offset)


    def visitAugAssign(self, n, *args):
        value = self.dispatch(n.value, *args)
        if not isinstance(n.target, ast.Name):
            cp = copy.copy(n.target)
            cp.ctx = ast.Load()
            fake = ast.Assign(targets=[n.target], value=ast.BinOp(left=cp, op=n.op, right=value, lineno=value.lineno, col_offset=value.col_offset),
                              lineno=n.lineno, col_offset=n.col_offset)
            return self.visitAssign(fake, *args)
        else:
            value = retic_ast.Check(value=value, type=n.target.retic_type, lineno=value.lineno, col_offset=value.col_offset)
            return ast.AugAssign(target=n.target, op=n.op, value=value, lineno=n.lineno, col_offset=n.col_offset)

    # ExceptionHandlers should have a retic_type node for the type of
    # the bound variable, if it exists. We need to guard the inside of
    # the exceptionhandler from bad bindings: like if the binder x has
    # type MyException, and the .type field (representing the kind of
    # exceptions caught) has Retic type Dyn, but is at runtime a
    # NotMyException
    def visitExceptHandler(self, n, *args):
        type = self.dispatch(n.type, *args)
        body = self.dispatch(n.body, *args)
        
        if n.name:
            prot = ast.Expr(value=retic_ast.Check(value=assign_type(ast.Name(id=n.name, ctx=ast.Load(),
                                                                             lineno=n.lineno, col_offset=n.col_offset),
                                                                    n),
                                                  type=n.retic_type, lineno=n.lineno, col_offset=n.col_offset), lineno=n.lineno, col_offset=n.col_offset)
            body = [prot] + body
            
        return ast.ExceptHandler(name=n.name, type=type, body=body)

        
    def visitwithitem(self, n, *args):
        cexpr = self.dispatch(n.context_expr, *args)
        optvars = self.dispatch(n.optional_vars, *args)

        if optvars:
            if isinstance(optvars, ast.Name):
                cexpr = retic_ast.Check(value=cexpr,
                                        type=optvars.retic_type,
                                        lineno=cexpr.lineno, col_offset=cexpr.col_offset)
            elif isinstance(target, ast.Starred):
                raise exc.UnimplementedException('Assignment checks against Starred')
            elif isinstance(target, ast.List):
                raise exc.UnimplementedException('Assignment checks against List')
            elif isinstance(target, ast.Tuple):
                raise exc.UnimplementedException('Assignment checks against Tuple')
        


#        prot = self.handlewithitem(optvars)

        ret = ast.withitem(context_expr=cexpr, optional_vars=optvars)
#        ret.retic_protector = None
        return ret

    # We might need to go back to the old approach of generating  protectors if we're withing to a tuple
    def visitWith(self, n, *args):
        body = self.dispatch(n.body, *args)
        if flags.PY_VERSION == 3 and flags.PY3_VERSION >= 3:
            items = [self.dispatch(item, *args) for item in n.items]
 #           prots = [itm.retic_protector for itm in items if itm.retic_protector]
            return ast.With(items=items, body=body)#prots + body)
        else:
            cexpr = self.dispatch(n.context_expr, *args)
            optvars = self.dispatch(n.optional_vars, *args)
            
            if optvars:
                if isinstance(optvars, ast.Name):
                    cexpr = retic_ast.Check(value=cexpr,
                                            type=optvars.retic_type,
                                            lineno=cexpr.lineno, col_offset=cexpr.col_offset)
                elif isinstance(target, ast.Starred):
                    raise exc.UnimplementedException('Assignment checks against Starred')
                elif isinstance(target, ast.List):
                    raise exc.UnimplementedException('Assignment checks against List')
                elif isinstance(target, ast.Tuple):
                    raise exc.UnimplementedException('Assignment checks against Tuple')
#            prot = self.handlewithitem(optvars)
#            if prot:
#                body = [prot] + body
                
            return ast.With(context_expr=cexpr, optional_vars=optvars, body=body)
            
        
    # Iterate over the comprehensions and produce both the new
    # comprehensions and a new binding for varchecks -- the variables
    # assigned to by the generators
    def handleComprehensions(self, comps, varchecks, *args):
        generators = []
        for comp in comps:
            iter = self.dispatch(comp.iter, varchecks, *args)
            target = self.dispatch(comp.target, varchecks, *args)
            
            vars = scope.WriteTargetFinder().preorder(target)
            varchecks = set.union(vars, varchecks)
            
            ifs = self.dispatch(comp.ifs, varchecks, *args)
            generators.append(ast.comprehension(target=target, iter=iter, ifs=ifs))
        return generators, varchecks

    def visitListComp(self, n, varchecks, *args):
        # In comprehensions, we can't generate protectors to guard
        # arguments since the body is just an expression. Instead we
        # add variables to varchecks to indicate in visitName that the
        # variable should be checked directly. This can lead to
        # duplicated checks but I suspect that's relatively rare.
        
        generators, varchecks = self.handleComprehensions(n.generators, varchecks, *args)
            
        elt = self.dispatch(n.elt, varchecks, *args)
        return ast.ListComp(elt=elt, generators=generators)

    def visitSetComp(self, n, varchecks, *args):
        
        generators, varchecks = self.handleComprehensions(n.generators, varchecks, *args)
            
        elt = self.dispatch(n.elt, varchecks, *args)
        return ast.SetComp(elt=elt, generators=generators)

    def visitDictComp(self, n, varchecks, *args):
        
        generators, varchecks = self.handleComprehensions(n.generators, varchecks, *args)
            
        key = self.dispatch(n.key, varchecks, *args)
        value = self.dispatch(n.value, varchecks, *args)
        return ast.DictComp(key=key, value=value, generators=generators)

    def visitGeneratorExp(self, n, varchecks, *args):
        
        generators, varchecks = self.handleComprehensions(n.generators, varchecks, *args)
            
        elt = self.dispatch(n.elt, varchecks, *args)
        return ast.GeneratorExp(elt=elt, generators=generators)
        
    def visitcomprehension(self, n, *args):
        raise exc.InternalReticulatedError('Should not visit comprehension generators directly')

    def visitName(self, n, varchecks, *args):
        if isinstance(n.ctx, ast.Load) and n.id in varchecks:
            return retic_ast.Check(value=n, type=n.retic_type, lineno=n.lineno, col_offset=n.col_offset)
        else:
            return n
