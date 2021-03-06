#!/usr/bin/env python3
from . import static, exc, repl
import sys, argparse, os, os.path, ast

""" The Reticulated Python entry module. Run this on the command line!"""


def launch_repl(semantics):
    repl.repl(semantics=semantics)

def main():
    parser = argparse.ArgumentParser(description='Typecheck and run a ' + 
                                     'Python program with type casts')
    parser.add_argument('-p', '--print', dest='output_ast', action='store_true', 
                        default=False, help='instead of executing the program, print out the modified program (comments and formatting will be lost)')
    parser.add_argument('-n', '--no-opt', dest='optimize', action='store_false', 
                        default=True, help='do not optimize transient checks')
    parser.add_argument('--lattice-test', dest='lattice_test_dir', action='store', 
                        type=str, default=None, help='perform full performance analysis, storing intermediate programs in directory DIR')
    typings = parser.add_mutually_exclusive_group()
    typings.add_argument('--transient', dest='semantics', action='store_const', const='TRANS',
                         help='use the casts-as-checks runtime semantics (the default)')
    typings.add_argument('--static-only', '--linting', '--noop', dest='semantics', action='store_const', const='NOOP',
                         help='do not perform runtime checks (static linting only)')
    typings.set_defaults(semantics='TRANS')
    parser.add_argument('program', help='a Python program to be executed (.py extension required)', default=None, nargs='?')
    parser.add_argument('args', help='arguments to the program in question (in quotes)', default='', nargs='?')

    args = parser.parse_args(sys.argv[1:])
    prog_args = args.args.split()
    if args.program is None:
        launch_repl(args.semantics)
    else:
        try:
            with open(args.program, 'r', encoding='utf-8') as program:
                sys.path.insert(1, os.path.sep.join(os.path.abspath(args.program).split(os.path.sep)[:-1]))

                st, srcdata = static.parse_module(program)
                
                if args.lattice_test_dir is None:
                    st = static.typecheck_module(st, srcdata)

                    if args.semantics == 'TRANS':
                        st = static.transient_compile_module(st, args.optimize)
                    elif args.semantics != 'NOOP':
                        raise UnimplementedException()

                    if args.output_ast:
                        static.emit_module(st)
                    else:
                        static.exec_module(st, srcdata)

                    
                    # from . import debugging
                    # debugging.AttachedInfoFinder().preorder(st1)
                    # st1 = static.typecheck_module(st1, srcdata)

                    # if args.semantics == 'TRANS':
                    #     st1 = static.transient_compile_module(st1, args.optimize)
                    # elif args.semantics != 'NOOP':
                    #     raise UnimplementedException()

                    # if args.output_ast:
                    #     static.emit_module(st1)
                    # else:
                    #     static.exec_module(st1, srcdata)
                else:
                    from .trust import dynamizer
                    dynamizer.lattice_test_module(st, srcdata, args.optimize, args.lattice_test_dir)
        except IOError as e:
            print(e)

if __name__ == '__main__':
    main()
