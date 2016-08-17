from . import retic_ast, typeparser

# Specifies the Reitculated type for builtin values
def module_env():
    env = {
        # Reticulated definitions (more will be added below when types are brought in from the typeparser
        '__typeof': retic_ast.Function(retic_ast.PosAT([retic_ast.Dyn()]), retic_ast.Str()),
        # Locals
        '__builtins__': retic_ast.Dyn(),
        '__package__': retic_ast.Dyn(),
        '__spec__': retic_ast.Dyn(),
        '__loader__': retic_ast.Dyn(),
        '__doc__': retic_ast.Dyn(),
        '__name__': retic_ast.Str(),
        # Builtins
        'BufferError': retic_ast.Dyn(),
        'divmod': retic_ast.Dyn(),
        'slice': retic_ast.Dyn(),
        'NotImplemented': retic_ast.Dyn(),
        'eval': retic_ast.Dyn(),
        'UnboundLocalError': retic_ast.Dyn(),
        'str': retic_ast.Dyn(),
        'type': retic_ast.Dyn(),
        '__loader__': retic_ast.Dyn(),
        'reversed': retic_ast.Dyn(),
        'filter': retic_ast.Dyn(),
        'True': retic_ast.Bool(),
        'KeyboardInterrupt': retic_ast.Dyn(),
        'OSError': retic_ast.Dyn(),
        'UnicodeWarning': retic_ast.Dyn(),
        'globals': retic_ast.Dyn(),
        'TabError': retic_ast.Dyn(),
        'ConnectionResetError': retic_ast.Dyn(),
        'TypeError': retic_ast.Dyn(),
        'list': retic_ast.Dyn(),
        'bool': retic_ast.Dyn(),
        'dict': retic_ast.Dyn(),
        'PendingDeprecationWarning': retic_ast.Dyn(),
        'IsADirectoryError': retic_ast.Dyn(),
        '__debug__': retic_ast.Bool(),
        'dir': retic_ast.Dyn(),
        'issubclass': retic_ast.Dyn(),
        'UnicodeTranslateError': retic_ast.Dyn(),
        'float': retic_ast.Dyn(),
        '__name__': retic_ast.Str(),
        '_': retic_ast.Dyn(),
        'hex': retic_ast.Dyn(),
        'ImportWarning': retic_ast.Dyn(),
        'next': retic_ast.Dyn(),
        'property': retic_ast.Dyn(),
        'BytesWarning': retic_ast.Dyn(),
        'EnvironmentError': retic_ast.Dyn(),
        'bytes': retic_ast.Dyn(),
        'delattr': retic_ast.Dyn(),
        'ArithmeticError': retic_ast.Dyn(),
        'hasattr': retic_ast.Dyn(),
        'UnicodeDecodeError': retic_ast.Dyn(),
        'id': retic_ast.Dyn(),
        'bytearray': retic_ast.Dyn(),
        'all': retic_ast.Dyn(),
        'Ellipsis': retic_ast.Dyn(),
        'super': retic_ast.Dyn(),
        'SyntaxError': retic_ast.Dyn(),
        'KeyError': retic_ast.Dyn(),
        'map': retic_ast.Dyn(),
        'print': retic_ast.Dyn(),
        'FloatingPointError': retic_ast.Dyn(),
        'open': retic_ast.Dyn(),
        'SyntaxWarning': retic_ast.Dyn(),
        'staticmethod': retic_ast.Dyn(),
        'any': retic_ast.Dyn(),
        'help': retic_ast.Dyn(),
        'memoryview': retic_ast.Dyn(),
        'ord': retic_ast.Dyn(),
        'NotImplementedError': retic_ast.Dyn(),
        'vars': retic_ast.Dyn(),
        'zip': retic_ast.Dyn(),
        'exec': retic_ast.Dyn(),
        'tuple': retic_ast.Dyn(),
        'GeneratorExit': retic_ast.Dyn(),
        'max': retic_ast.Dyn(),
        'LookupError': retic_ast.Dyn(),
        'None': retic_ast.Dyn(),
        'SystemExit': retic_ast.Dyn(),
        'input': retic_ast.Dyn(),
        'MemoryError': retic_ast.Dyn(),
        'license': retic_ast.Dyn(),
        'repr': retic_ast.Dyn(),
        'FileExistsError': retic_ast.Dyn(),
        'exit': retic_ast.Dyn(),
        'format': retic_ast.Dyn(),
        'bin': retic_ast.Dyn(),
        'FileNotFoundError': retic_ast.Dyn(),
        'TimeoutError': retic_ast.Dyn(),
        'sorted': retic_ast.Dyn(),
        'object': retic_ast.Dyn(),
        '__package__': retic_ast.Str(),
        'getattr': retic_ast.Dyn(),
        '__spec__': retic_ast.Dyn(),
        'UserWarning': retic_ast.Dyn(),
        'InterruptedError': retic_ast.Dyn(),
        'IndexError': retic_ast.Dyn(),
        'compile': retic_ast.Dyn(),
        'FutureWarning': retic_ast.Dyn(),
        'AssertionError': retic_ast.Dyn(),
        'DeprecationWarning': retic_ast.Dyn(),
        'oct': retic_ast.Dyn(),
        'callable': retic_ast.Dyn(),
        'SystemError': retic_ast.Dyn(),
        'ValueError': retic_ast.Dyn(),
        'NameError': retic_ast.Dyn(),
        'chr': retic_ast.Dyn(),
        'pow': retic_ast.Dyn(),
        'hash': retic_ast.Dyn(),
        'OverflowError': retic_ast.Dyn(),
        'Warning': retic_ast.Dyn(),
        'setattr': retic_ast.Dyn(),
        'ChildProcessError': retic_ast.Dyn(),
        'StopIteration': retic_ast.Dyn(),
        'quit': retic_ast.Dyn(),
        'ImportError': retic_ast.Dyn(),
        'UnicodeEncodeError': retic_ast.Dyn(),
        'False': retic_ast.Bool(),
        'EOFError': retic_ast.Dyn(),
        'RuntimeWarning': retic_ast.Dyn(),
        'ConnectionAbortedError': retic_ast.Dyn(),
        'iter': retic_ast.Dyn(),
        'AttributeError': retic_ast.Dyn(),
        'min': retic_ast.Dyn(),
        '__doc__': retic_ast.Str(),
        'ResourceWarning': retic_ast.Dyn(),
        '__build_class__': retic_ast.Dyn(),
        'IOError': retic_ast.Dyn(),
        'ConnectionError': retic_ast.Dyn(),
        'set': retic_ast.Dyn(),
        'range': retic_ast.Dyn(),
        'NotADirectoryError': retic_ast.Dyn(),
        'ascii': retic_ast.Dyn(),
        'isinstance': retic_ast.Dyn(),
        'copyright': retic_ast.Dyn(),
        '__import__': retic_ast.Dyn(),
        'credits': retic_ast.Dyn(),
        'ProcessLookupError': retic_ast.Dyn(),
        'sum': retic_ast.Dyn(),
        'BlockingIOError': retic_ast.Dyn(),
        'enumerate': retic_ast.Dyn(),
        'len': retic_ast.Dyn(),
        'BrokenPipeError': retic_ast.Dyn(),
        'ReferenceError': retic_ast.Dyn(),
        'Exception': retic_ast.Dyn(),
        'locals': retic_ast.Dyn(),
        'complex': retic_ast.Dyn(),
        'BaseException': retic_ast.Dyn(),
        'PermissionError': retic_ast.Dyn(),
        'ZeroDivisionError': retic_ast.Dyn(),
        'UnicodeError': retic_ast.Dyn(),
        'frozenset': retic_ast.Dyn(),
        'int': retic_ast.Dyn(),
        'IndentationError': retic_ast.Dyn(),
        'classmethod': retic_ast.Dyn(),
        'RuntimeError': retic_ast.Dyn(),
        'abs': retic_ast.Dyn(),
        'ConnectionRefusedError': retic_ast.Dyn(),
        'round': retic_ast.Dyn(),
        'Union': retic_ast.Dyn()
    }

    for name in typeparser.type_names:
        if name not in env:
            env[name] = retic_ast.Dyn()
    return env
