# Interface-child operations without the interface's parent

The normal Define fixture
`operation_graph_relationship_integration/interface_child_work_can_precede_the_actions_parent_create`
passes source validation. A caller creates particle P, then creates a gateway
particle G and moves P into its action's interface. The action creates a child
at `input::/child` and passes P onward through another interface position.

The child position is defined by P, not G. Under identified-endpoint execution,
the child Create requires P but neither G's existence nor the incoming Move.
The interface Moves still require G. The fixture records those dependencies;
its graph assertion is an expected failure of the current compiler.

## C correctness experiment

`interface_child_runtime.c` gives the child operation a direct pointer to P.
It never receives a pointer to G. Moving P changes the source, interface, and
returned-position pointer values without replacing P's defined child position.

Each of 200 repetitions tests three schedules:

1. Complete the child Create before allocating G.
2. Complete all interface Moves and free G before permitting the child Create.
   Vacate P's final ordinary position as well, retaining P until its child use
   finishes.
3. Impose neither cross-branch order; let the child Create race the interface
   branch. Join before reclaiming P.

All 600 schedules completed with GCC 16.2.1 at `-O2`. Clang 22.1.8 runs also
completed with AddressSanitizer plus UndefinedBehaviorSanitizer, and separately
with ThreadSanitizer. GCC's installed sanitizer libraries were unavailable;
Clang supplied the sanitizer builds. LeakSanitizer required execution outside
the ptrace sandbox; it completed there without disabling leak checking.

```sh
clang -std=c11 -O2 -g -Wall -Wextra -Werror -pthread -fsanitize=address,undefined operation_graph_optimization/interface_child_runtime.c -o /tmp/define-interface-child-runtime-sanitized
/tmp/define-interface-child-runtime-sanitized
clang -std=c11 -O1 -g -Wall -Wextra -Werror -pthread -fsanitize=thread operation_graph_optimization/interface_child_runtime.c -o /tmp/define-interface-child-runtime-thread-sanitized
/tmp/define-interface-child-runtime-thread-sanitized
```

This checks concrete identity delivery, independent storage accesses, and
reclamation. It is a hand-written implementation of the selected operation
effects, not output of the Define compiler. The synchronization forcing the
first two schedules is test coordination, not an additional dependency rule.
It does not validate general relationship arbitration or measure atomic costs.

An implementation that makes every callee operation wait for allocation of the
action's parent would lose these orders. The operation can instead receive its
identified required objects directly. Interface occupancy and the identity of
the particle supplied through it must remain separate information.
