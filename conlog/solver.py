from __future__ import annotations
from conlog.datatypes import (
    Addition,
    ConditionalDecrement,
    ConditionalIncrement,
    Initial,
    Node,
    Subtraction,
    Terminal,
)
from conlog.elegant import determine_variable_bounds_multipass
from conlog.evaluator import evaluate
from dataclasses import dataclass
import networkx as nx

@dataclass(frozen=True)
class SearchState():
    node: Node
    last_node: Node | None
    values: dict[str, int]
    graph: nx.Graph


def compute_new_values_from_node(node, values, reverse=True):
    new_values = dict(values)

    if isinstance(node.op, (Addition, Subtraction, ConditionalIncrement, ConditionalDecrement)):
        if isinstance(node.op.rhs, int):
            rhs = node.op.rhs
        else:
            rhs = new_values[node.op.rhs]

        rvalue = (-1 if reverse else 1)
        if isinstance(node.op, (Subtraction, ConditionalDecrement)):
            rvalue *= -1
        if isinstance(node.op, (Addition, Subtraction)):
            rvalue *= rhs
        if isinstance(node.op, (ConditionalIncrement, ConditionalDecrement)) and rhs <= 0:
            rvalue = 0  # Do nothing if condition not satisfied

        new_values[node.op.lhs] += rvalue

    return new_values


def compute_successor_states(current_state: SearchState, bounds : dict | None = None) -> list[SearchState]:
    bounds = dict() if bounds is None else bounds

    if isinstance(current_state.node.op, Terminal) and current_state.last_node is not None:
        return []  # Terminals terminate the search.

    successor_states = []
    successor_values = compute_new_values_from_node(current_state.node, current_state.values, reverse=True)
    if any(successor_values[var] < bounds[var][0] for var in bounds) or \
         any(successor_values[var] > bounds[var][1] for var in bounds):
        return []  # Search optimization: bounds violation
    for successor_node in current_state.graph.neighbors(current_state.node):
        if successor_node == current_state.last_node:
            continue  # No backtracking allowed
        successor_states.append(SearchState(
            node=successor_node,
            last_node=current_state.node,
            values=successor_values,
            graph=current_state.graph,
        ))

    return successor_states


def solve_graph_bfs(graph: nx.Graph, limit = None):
    if limit is None:
        limit = 65536

    bounds = determine_variable_bounds_multipass(graph)

    # Get key nodes and variables
    initial_node = next(node for node in graph.nodes if isinstance(node.op, Initial))
    terminal_node = next(node for node in graph.nodes if isinstance(node.op, Terminal))
    free, fixed = initial_node.op.free, dict(initial_node.op.fixed)
    var_names = list(free) + list(fixed)

    # Run a BFS search
    queue = [[SearchState(
        node=terminal_node,
        last_node=None,
        values={n: 0 for n in var_names},
        graph=graph,
    ), None]]
    it = 0
    while len(queue) > 0 and it < limit:
        it += 1
        current_state, history = queue.pop(0)
        if current_state.node == initial_node and all(current_state.values[n] == fixed[n] for n in fixed):
            history_traverser = history
            final_path = [current_state]
            while history_traverser is not None:
                head, history_traverser = history_traverser
                final_path.append(head)

            # One last check: try evaluator on search result.
            solution = evaluate([cs.node for cs in final_path], current_state.values)

            if solution is None:
                raise Exception('BFS solver thought an invalid solution was valid')

            yield solution

        for successor_state in compute_successor_states(current_state, bounds=bounds):
            queue.append([successor_state, [current_state, history]])
