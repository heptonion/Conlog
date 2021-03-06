import argparse
from conlog.elegant   import interpret
from conlog.evaluator import evaluate
from conlog.frontends import convert_to_grid, GridError, FrontendError, make_grid_program, TokenStream, TextProgram
from conlog.plot      import plot_graph
from conlog.solver    import solve_graph_bfs
from conlog.solver_c  import solve_graph_bfs_c

AUTO_SEMICOLON  = True

#~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~
# Read from file

parser = argparse.ArgumentParser()
parser.add_argument('inp',              metavar='FILE',     nargs='?',              default=None,  help='conlog file to parse and execute')
parser.add_argument('-s', '--strategy', metavar='STRATEGY', choices=('c','g','p'),  default='g',   help='strategy to use')
parser.add_argument('-l', '--limit',    metavar='N',        type=int,               default=None,  help='search limit')
parser.add_argument('-i', '--interactive',                  action='store_true',    default=False, help='load graph then start interactive session')
parser.add_argument('-a', '--all',      dest='find_all',    action='store_true',    default=False, help='find all solutions instead of just the first (ignored in interactive mode)')
parser.add_argument('-p', '--plot',                         action='store_true',    default=False, help='load graph then plot and exit')
args = parser.parse_args()

strategy = args.strategy
limit = 1000000 if args.limit is None else args.limit

if (filename := args.inp) is not None:

    is_grid_file = any(filename.endswith(ext) for ext in ('.cla', '.clg'))
    is_text_file = any(filename.endswith(ext) for ext in ('.clt', '.cl'))
    if not (is_grid_file or is_text_file):
        print('\x1B[93mwarning\x1B[39m: not a conlog file: %s' % filename)

    with open(filename, 'r') as f:
        filetext = f.read()

    if is_text_file:
        stream = TokenStream(filetext, None)
        program = TextProgram()
        while True:
            seq = stream.readline()
            if isinstance(seq, FrontendError):
                log_lines = stream.log.split('\n')
                seq.show(log_lines)
                exit(1) 
            if seq is None:
                break
            if len(seq) == 0:
                continue
            result = program.add_statement(seq, allow_reinit=True)
            if isinstance(result, FrontendError):
                log_lines = stream.log.split('\n')
                result.show(log_lines)
                exit(1)
    else:
        grid = convert_to_grid(filetext)
        if isinstance(grid, GridError):
            grid.show()
            exit(1)
        program = make_grid_program(grid)
        if isinstance(program, GridError):
            program.show(grid)
            exit(1)

    if args.plot:
        plot_graph(program.graph())
        exit(0)

    if args.interactive:
        if not is_text_file:
            conversion = TextProgram()
            conversion.variables = program.variables
            conversion.nodes     = program.nodes
            conversion.edges     = program.edges
            program = conversion

    else:
        graph = program.graph()
        try:
            if args.strategy == 'c':
                interpreter = solve_graph_bfs_c(graph, limit=limit)
            if args.strategy == 'g':
                interpreter = solve_graph_bfs(graph, limit=limit)
            if args.strategy == 'p':
                interpreter = interpret(graph, limit=limit)
            try:
                solution = next(interpreter)
            except StopIteration:
                print("\x1B[91munsatisfiable\x1B[39m")
                exit(0)
        except KeyboardInterrupt:
            print('\rinterrupted')
            exit(1)

        alternate = False
        while True:
            first = True
            for (name, value) in solution.assignment.items():
                if program.variables[name] in ('free', None):
                    if alternate and not first:
                        print('   ', end='')
                    print(f"\x1B[95m{name}\x1B[39m = \x1B[95m{value}\x1B[39m")
                    first = False
            last_emitted = None
            for out in solution.stdout:
                if isinstance(out, str):
                    if last_emitted is None or last_emitted == 'character':
                        print(out, end='')
                    else:
                        print(' ' + out, end='')
                    last_emitted = 'character'
                else:
                    if last_emitted is None:
                        print(str(out), end='')
                    else:
                        print(' ' + str(out), end='')
                    last_emitted = 'numeric'
            if len(solution.stdout) > 0:
                print()

            if not args.find_all:
                exit(0)

            alternate = True
            try:
                solution = next(interpreter)
            except StopIteration:
                break
            except KeyboardInterrupt:
                print('\rinterrupted')
                break
            print("\x1B[2mor\x1B[22m", end=' ')

        exit(0)

else:
    program = TextProgram()

#~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~
# Interactive prompt

def prompt():
    print("\x1B[2mconlog:\x1B[22m", end=' ')
    try:
        line = input()
    except KeyboardInterrupt:
        print()
        exit(0)
    except EOFError:
        print('^D')
        exit(0)
    if line in ['exit', 'quit', ':q']:
        exit(0)
    if AUTO_SEMICOLON:
        stripped = line.rstrip()
        if len(stripped) > 0 and stripped[-1] != ';':
            line += ';'
    return line + '\n'

stream = TokenStream("", prompt)

while True:
    seq = stream.readline()
    if isinstance(seq, FrontendError):
        log_lines = stream.log.split('\n')
        seq.show(log_lines)
        continue
    if seq is None:
        break
    if len(seq) == 0:
        continue

    if len(seq) < 3 and seq[0].kind == 'name' and seq[0].value == 'strategy':
        if len(seq) == 1:
            print(f"strategy is \x1B[93m{strategy}\x1B[39m")
        else:
            if seq[1].kind != 'name' or seq[1].value not in ('c', 'g', 'p'):
                log_lines = stream.log.split('\n')
                FrontendError("unknown strategy", seq[1]).show(log_lines)
            else:
                strategy = seq[1].value
        continue

    if len(seq) < 3 and seq[0].kind == 'name' and seq[0].value == 'limit':
        if len(seq) == 1:
            print(f"limit is \x1B[93m{limit}\x1B[39m")
        elif seq[1].kind == 'name' and seq[1].value in ('inf', 'infinity'):
            limit = float('inf')
        elif seq[1].kind != 'numeric':
            log_lines = stream.log.split('\n')
            FrontendError("limit must be numeric", seq[1]).show(log_lines)
        else:
            limit = seq[1].value
        continue

    if len(seq) < 3 and seq[0].value in ('solve', 'go'):
        find_all = (len(seq) == 2 and seq[1].value == 'all')

        has_initial = 'initial' in program.nodes
        has_final   = 'final'   in program.nodes
        if not (has_initial and has_final):
            if not has_initial:
                print("\x1B[91merror\x1B[39m: missing initial node")
            if not has_final:
                print("\x1B[91merror\x1B[39m: missing final node")
            continue
        uninit = program.uninitialized()
        if len(uninit) > 0:
            uninit_names = ', '.join(f"\x1B[95m{name}\x1B[39m" for name in uninit)
            print(uninit_names, "uninitialized and assumed free")

        graph = program.graph()
        try:
            if strategy == 'c':
                interpreter = solve_graph_bfs_c(graph, limit=limit)
            if strategy == 'g':
                interpreter = solve_graph_bfs(graph, limit=limit)
            if strategy == 'p':
                interpreter = interpret(graph, limit=limit)
            try:
                solution = next(interpreter)
            except StopIteration:
                print("\x1B[91munsatisfiable\x1B[39m")
                continue
        except KeyboardInterrupt:
            print('\rinterrupted')
            continue

        print("\x1B[92msatisfiable\x1B[39m")
        alternate = False
        while True:
            first = True
            for (name, value) in solution.assignment.items():
                if program.variables[name] in ('free', None):
                    if alternate and not first:
                        print('   ', end='')
                    print(f"\x1B[95m{name}\x1B[39m = \x1B[95m{value}\x1B[39m")
                    first = False
            last_emitted = None
            for out in solution.stdout:
                if isinstance(out, str):
                    if last_emitted is None or last_emitted == 'character':
                        print(out, end='')
                    else:
                        print(' ' + out, end='')
                    last_emitted = 'character'
                else:
                    if last_emitted is None:
                        print(str(out), end='')
                    else:
                        print(' ' + str(out), end='')
                    last_emitted = 'numeric'
            if len(solution.stdout) > 0:
                print()

            # Uncomment to print the path
            # nodes = [f"\x1B[94m{node.name}\x1B[39m" for node in solution.path]
            # if len(nodes) > 15:
            #     nodes = nodes[:7] + ["..."] + nodes[-7:]
            # print(' -- '.join(nodes))

            if not find_all:
                break

            alternate = True
            try:
                solution = next(interpreter)
            except StopIteration:
                break 
            except KeyboardInterrupt:
                print('\rinterrupted')
                break
            print("\x1B[2mor\x1B[22m", end=' ')

        continue

    is_command = (len(seq) == 1 and seq[0].kind == 'name')

    if is_command and seq[0].value == 'help':
        print("strategy            print the current strategy")
        print("strategy c|g|p      set the strategy to c, g, or p")
        print("limit               print the current search limit")
        print("limit <num>         set the search limit to <num>")
        print("go|search|solve     solve the current graph")
        print("go|... all          find all solutions")
        print("reset|clear         reset the current graph")
        print("<name>              print the definition of <name>")
        print("vars                print the definitions of all variables")
        print("nodes               print the definitions of all nodes")
        print("show|plot           render the current graph")
        print("exit|quit           exit the interpreter")
        print("CTRL-C              halt the ongoing search")

    if is_command and seq[0].value in ('show', 'plot'):
        plot_graph(program.graph())
        continue

    if is_command and seq[0].value in ('clear', 'reset'):
        program = TextProgram()
        continue

    if is_command:
        program.show(seq[0].value)
        continue

    result = program.add_statement(seq, allow_reinit=True)
    if isinstance(result, FrontendError):
        log_lines = stream.log.split('\n')
        result.show(log_lines)
        continue
