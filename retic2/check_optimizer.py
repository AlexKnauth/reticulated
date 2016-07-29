from . import copy_visitor, retic_ast
import ast

class Tombstone(ast.stmt): pass

class CheckRemover(copy_visitor.CopyVisitor):
    # Removes unneeded checks, like checks where the type of the check
    # is Dyn.  In the case of argument protectors (the checks inserted
    # at the entry to functions), when we remove them we might leave
    # behind a "useless" expression, one which didn't appear in the
    # original program but doesn't have any typechecking value. We
    # detect these cases by looking at Expr statements (the kind of
    # statement representing an expression alone on a line). If the
    # value of the Expr (i.e. the expression contained within it) was
    # a retic_ast.Check before the recursive call, but just an
    # ast.Name afterwards, we replace the Expr with a special
    # Tombstone value. Then, when function bodies are being
    # reconstructed to be outputted (using the reduce, dispatch_scope,
    # and dispatch_statements methods), we look for Tombstone values
    # and filter them out. Tombstones should NEVER exist in the final
    # outputted AST.

    examine_functions = True
    
    def reduce(self, ns, *args):
        lst = [self.dispatch(n, *args) for n in ns]
        return [l for l in lst if not isinstance(l, Tombstone)]

    def dispatch_scope(self, ns, *args):
        lst = [self.dispatch(s, *args) for s in ns]
        return [l for l in lst if not isinstance(l, Tombstone)]

    def dispatch_statements(self, ns, *args):
        if not hasattr(self, 'visitor'): # preorder may not have been called
            self.visitor = self
        lst = [self.dispatch(s, *args) for s in ns]
        return [l for l in lst if not isinstance(l, Tombstone)]

    def visitCheck(self, n, *args):
        val = self.dispatch(n.value)
        if isinstance(n.type, retic_ast.Dyn):
            return n.value
        else:
            return retic_ast.Check(value=val, type=n.type, lineno=n.lineno, col_offset=n.col_offset)

    def visitExpr(self, n, *args):
        val = self.dispatch(n.value)
        if isinstance(n.value, retic_ast.Check) and isinstance(val, ast.Name):
            return Tombstone()
        else:
            return ast.Expr(value=val, lineno=n.lineno)
            