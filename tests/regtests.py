#!/usr/bin/env python3

import os, sys, io
import subprocess

pyfiles = {}
trfiles = {}
mofiles = {}

trpassed = 0
mopassed = 0
trtests = 0
motests = 0

PYVERSION = 'python3'
CALL = (PYVERSION + ' ../retic.py').split()

print('Starting regression tests.')

def test(file, sem, expected):
    print ('Reticulating', file)
    try: 
        oresult = subprocess.check_output(CALL + [pyfiles[file]] + [sem], 
                                          stderr=subprocess.STDOUT).decode('utf-8').strip()
        result = '\n'.join(line for line in oresult.split('\n') if not line.strip().startswith('#'))
        printed = '\n'.join(line for line in oresult.split('\n') if line.strip().startswith('#'))
        print(printed)
        exc = False
    except Exception as e:
        exc = e.output.decode('utf-8').strip()
        printed = '\n'.join(line for line in exc.split('\n') if line.strip().startswith('#'))
        print(printed)
        human_exc = '...\n' + exc[exc.rfind('File "'):]
        try:
            err_zone = exc[exc.rfind('File "'):]
            actual_line = err_zone[err_zone.find('line '):].split()[1].strip(',')
        except IndexError:
            print('=============\nTest failure for file "{}": a non-Reticulated error message was raised.\nError message:\n\n{}\n=============\n'.format(file, human_exc))
            return 0
            

    if exc:
        if expected.startswith('RUNTIME'):
            exp_line = expected[len('RUNTIME'):].strip()
            if exp_line == actual_line:
                print('Correct runtime error')
                return 1
            else:
                print('=============\nTest failure for file "{}": expected a runtime error on line {}; received runtime error on line {}.\nError message:\n\n{}\n=============\n'.format(file, exp_line, actual_line, human_exc))
                return 0
        elif expected.startswith('STATIC'):
            exp_line = expected[len('STATIC'):].strip()
            print('=============\nTest failure for file "{}": expected a static type error on line {}; received runtime error on line {}.\nError message:\n\n{}\n=============\n'.format(file, exp_line, actual_line, human_exc))
            return 0
        else:
            print('=============\nTest failure for file "{}": expected program to terminate normally; received runtime error on line {}.\nError message:\n\n{}\n=============\n'.format(file, actual_line, human_exc))
            return 0
    elif result.find('Static type error') >= 0 or result.find('Malformed type annotation') >= 0:
        err_zone = result[result.rfind('File "'):]
        actual_line = err_zone[err_zone.find('line '):].split()[1].strip(',')
        if expected.startswith('RUNTIME'):
            exp_line = expected[len('RUNTIME'):].strip()
            print('=============\nTest failure for file "{}": expected a runtime error on line {}; received static type error on line {}.\nError message:\n\n{}\n=============\n'.format(file, exp_line, actual_line, result))
            return 0
        elif expected.startswith('STATIC'):
            exp_line = expected[len('STATIC'):].strip()
            if exp_line == actual_line:
                print('Correct static error')
                return 1
            else:
                print('=============\nTest failure for file "{}": expected a static type error on line {}; received static type error on line {}.\nError message:\n\n{}\n============='.format(file, exp_line, actual_line, result))
                return 0
        else:
            print('=============\nTest failure for file "{}": expected program to terminate normally; received static type error on line {}.\nError message:\n\n{}\n============='.format(file, actual_line, result))
            return 0
    else:
        if expected.startswith('RUNTIME'):
            exp_line = expected[len('RUNTIME'):].strip()
            print('=============\nTest failure for file "{}": expected a runtime error on line {} but program terminated normally.\nResult of execution:\n\n{}\n=============\n'.format(file, exp_line, result if result else '[empty]'))
            return 0
        elif expected.startswith('STATIC'):
            exp_line = expected[len('STATIC'):].strip()
            print('=============\nTest failure for file "{}": expected a static type error on line {} but program terminated normally.\nResult of execution:\n\n{}\n=============\n'.format(file, exp_line, result if result else '[empty]'))
            return 0
        else:
            if expected == result:
                print('Correct termination')
                return 1
            else:
                print('=============\nTest failure for file "{}": actual output does not match expected output.\nExpected output:\n\n{}\n-----------\nActual output:\n\n{}\n=============\n'.format(file, expected if expected else '[empty]', result if result else '[empty]'))
                return 0
            
pyfiles = {f[:-3]: f for f in os.listdir('.') if os.path.isfile(f) and f.endswith('.py')}
notrfiles = [f for f in os.listdir('.') if os.path.isfile(f) and f.endswith('.py') and not os.path.isfile(f[:-3] + '.trx') and not os.path.isfile(f[:-3] + '.lib')]
trfiles = {f[:-4]: f for f in os.listdir('.') if os.path.isfile(f) and f.endswith('.trx')}
mofiles = {f[:-4]: f for f in os.listdir('.') if os.path.isfile(f) and f.endswith('.mox')}

for file in sorted(pyfiles):
    if file in trfiles:
        with open(trfiles[file], 'r') as f_obj:
            trpassed += test(file, '--transient', f_obj.read().strip())
            trtests += 1
    if file in mofiles:
        with open(mofiles[file], 'r') as f_obj:
            mopassed += test(file, '--monotonic', f_obj.read().strip())
            motests += 1


print('\n{}/{} tests passed with transient'.format(trpassed, trtests))
print('\nNo transient output files for the following cases:', notrfiles)
with open('notes', 'r') as notes:
    print('\nCurrent notes:', *['\n{}: '.format(i) + note for i, note in enumerate(notes.read().strip().split('\n'))])
print('\n')
