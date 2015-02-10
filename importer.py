from visitors import DictGatheringVisitor
import typecheck, os, os.path, ast, sys, imp, typing, utils, exc
from os.path import join as _path_join, isdir as _path_isdir, isfile as _path_isfile
from rtypes import *
from typing import Var, StarImport
from gatherers import WrongContextVisitor
import flags

if flags.PY_VERSION == 3:
    from exec3 import _exec
    from importlib.abc import Finder, SourceLoader
else: 
    from exec2 import _exec
    class Finder:
        pass
    class SourceLoader:
        def is_package(self, fullname):
            """Concrete implementation of InspectLoader.is_package by checking if
            the path returned by get_filename has a filename of '__init__.py'."""
            filename = self.get_filename(fullname).rpartition(os.path.sep)[2]
            return filename.rsplit('.', 1)[0] == '__init__'

import_cache = {}
not_found = set()

def _case_ok(directory, check):
    return check in os.listdir(directory if directory else os.getcwd())

def make_importer(typing_context):
    class ReticImporter(Finder, SourceLoader):
        def __init__(self, path):
            if not path.startswith(os.getcwd()):
                raise ImportError
            self.path = path

        def find_module(self, fullname, return_path=False):
            if fullname in flags.IGNORED_MODULES:
                return None
            tail_module = fullname.rpartition('.')[2]
            base_path = _path_join(self.path, tail_module)
            if _path_isdir(base_path) and _case_ok(self.path, tail_module):
                init_filename = '__init__.py'
                full_path = _path_join(base_path, init_filename)
                if (_path_isfile(full_path) and
                    _case_ok(base_path, init_filename)):
                    print('FOUND1', fullname)
                    return full_path if return_path else self
            mod_filename = tail_module + '.py'
            full_path = _path_join(self.path, mod_filename)
            if _path_isfile(full_path) and _case_ok(self.path, mod_filename):
                return full_path if return_path else self
            return None

        def get_filename(self, fullname):
            ret = self.find_module(fullname, return_path=True)
            if ret is not None:
                return ret
            else: raise ImportError

        def get_data(*args):
            raise ImportError

        def module_repr(*args):
            raise ImportError

        def get_code(self, fullname):
            if fullname in import_cache and False:
                code, _ = import_cache[fullname]
                if code != None:
                    typing.debug('%s found in import cache' % fullname, flags.IMP)
                    return code
            source_path = self.get_filename(fullname)
            with open(source_path) as srcfile:
                try:
                    typing.debug('Cache miss, compiling %s' % source_path, flags.IMP)
                    py_ast = ast.parse(srcfile.read())
                    checker = typecheck.Typechecker()
                    try:
                        typed_ast, _ = checker.typecheck(py_ast, source_path, 0)
                    except exc.StaticTypeError as e:
                        utils.handle_static_type_error(e)
                    return compile(typed_ast, source_path, 'exec')
                finally: 
                    pass
                    # Timing stuff can go here if need be

        def load_module(self, fullname):
            code = self.get_code(fullname)
            ispkg = self.is_package(fullname)
            mod = sys.modules.setdefault(fullname, imp.new_module(fullname))
            srcfile = self.get_filename(fullname)
            mod.__dict__.update(typing_context)
            mod.__file__ = srcfile
            mod.__loader__ = self
            if ispkg:
                mod.__path__ = [srcfile.rsplit(os.path.sep, 1)[0]]
                mod.__package__ = fullname
            else:
                mod.__path__ = [srcfile.rsplit(os.path.sep, 1)[0]]
                mod.__package__ = fullname.rpartition('.')[0]
            mod.__name__ = fullname
            _exec(code, mod.__dict__)
            return mod

        def exec_module(self, module):
            srcfile = module.__file__
            package = module.__package__
            fullname = module.__name__
            code = self.get_code(module.__name__)
            module.__dict__.update(typing_context)
            module.__file__ = srcfile
            module.__loader__ = self
            module.__package__ = package
            module.__name__ = fullname
            _exec(code, module.__dict__)
            return module
    return ReticImporter


class ImportFinder(DictGatheringVisitor):
    examine_functions = False

    def typecheck_import(self, module_name, depth):
        if not flags.TYPECHECK_IMPORTS:
            return None
        if module_name in flags.IGNORED_MODULES:
            return None
        if module_name in not_found or module_name in sys.builtin_module_names:
            typing.warn('Imported module %s is a builtin module and cannot be typechecked' % module_name, 1)
            return None
        if module_name in sys.modules:
            typing.warn('Imported module %s is already loaded by Reticulated and cannot be typechecked'\
                            % module_name, 1)
            return None
        for path in [p for p in sys.path if p.startswith(os.getcwd())]:
            qualname = os.path.join(path, *module_name.split('.')) + '.py'
            if module_name in import_cache:
                _, env = import_cache[module_name]
                return env
            try:
                with open(qualname) as module:
                    typing.debug('Typechecking import ' + qualname, flags.IMP)
                    import_cache[module_name] = None, None
                    assert depth <= flags.IMPORT_DEPTH
                    if depth == flags.IMPORT_DEPTH:
                        typing.warn('Import depth exceeded when typechecking module %s' % qualname, 1)
                        typing.debug('Finished importing ' + qualname, flags.IMP)
                        return None
                    py_ast = ast.parse(module.read())
                checker = typecheck.Typechecker()
                typed_ast, env = checker.typecheck(py_ast, qualname, depth + 1)
                if flags.VERIFY_CONTEXTS:
                    from gatherers import WrongContextVisitor
                    wcv = WrongContextVisitor()
                    wcv.filename = qualname
                    typing.debug('Context checker started for imported module %s' % module_name, flags.PROC)
                    wcv.preorder(typed_ast)
                    typing.debug('Context checker finished for imported module %s' % module_name, flags.PROC)
                import_cache[module_name] = compile(typed_ast, module_name, 'exec'), env
                typing.debug('Finished importing ' + qualname, flags.IMP)
                return env
            except IOError:
                continue
        not_found.add(module_name)
        return None
    
    def visitImport(self, n, depth):
        env = {}
        for alias in n.names:
            module = alias.name
            name = alias.asname if alias.asname else alias.name
            impenv = self.typecheck_import(module, depth)
            if impenv is None:
                env[Var(name)] = Dyn
            else: 
                env[Var(name)] = Object('', {k.var: impenv[k] for k in impenv if isinstance(k, Var)})
        return env

    def visitImportFrom(self, n, depth):
        if n.level is not None and n.level != 0:
            impenv = None
        else: impenv = self.typecheck_import(n.module, depth)
        wasemp = False
        if impenv is None:
            impenv = {}
            wasemp = True
        env = {}
        for alias in n.names:
            member = alias.name
            if member == '*':
                if wasemp:
                    typing.warn('Unable to import type definitions from %s due to *-import' % n.module, 0)
                impenv[StarImport(n.module)] = impenv
                return impenv
            name = alias.asname if alias.asname else alias.name
            if Var(member) in impenv:
                env[Var(name)] = impenv[Var(member)]
            else: env[Var(name)] = Dyn
            if TypeVariable(member) in impenv:
                env[TypeVariable(name)] = impenv[TypeVariable(member)]
        return env

