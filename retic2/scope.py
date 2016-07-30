from . import visitors, retic_ast, typing, typeparser, exc, consistency
import ast

## This module figures out the environment for a given scope. 

tydict = typing.Alias(typing.Dict[str, retic_ast.Type])

class InconsistentAssignment(Exception): pass

class InitialScopeFinder(visitors.DictGatheringVisitor):
    examine_functions = False

    def combine_stmt(self, s1: tydict, s2: tydict)->tydict:
        for k in s1:
            if k in s2 and s1[k] != s2[k]:
                raise InconsistentAssignment(k, s1[k], s2[k])
        s1.update(s2)
        return s1
    
    def visitFunctionDef(self, n: ast.FunctionDef)->tydict:
        argtys = []
        for arg in n.args.args:
            if arg.annotation:
                argty = typeparser.typeparse(arg.annotation)
            else:
                argty = retic_ast.Dyn()
            argtys.append(argty)
        retty = typeparser.typeparse(n.returns)
        return {n.name: retic_ast.Function(retic_ast.PosAT(argtys), retty)}
        
class InferenceTargetFinder(visitors.SetGatheringVisitor):
    examine_functions = False
    
    def visitcomprehension(self, n, *args):
        return set()

    def visitName(self, n: ast.Name)->typing.Set[ast.expr]:
        if isinstance(n.ctx, ast.Store):
            return { n.id }
        else: return set()

class AssignmentFinder(visitors.SetGatheringVisitor):
    examine_functions = False
    
    def visitAssign(self, n: ast.Assign):
        return { (targ, n.value, 'ASSIGN') for targ in n.targets if not isinstance(targ, ast.Subscript) and not isinstance(targ, ast.Attribute) }

    def visitAugAssign(self, n: ast.AugAssign):
        if not isinstance(n.target, ast.Subscript) and not isinstance(n.target, ast.Attribute):
            return { (n.target, n.value, 'ASSIGN') }
        else: return set()

    def visitFor(self, n: ast.For): 
        if not isinstance(n.target, ast.Subscript) and not isinstance(n.target, ast.Attribute):
            return set.union({ (n.target, n.iter, 'FOR') }, self.dispatch(n.body), self.dispatch(n.orelse))
        else: return set.union(self.dispatch(n.body), self.dispatch(n.orelse))
        
