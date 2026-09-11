#include <pthread.h>
#include <sched.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

enum Operation {
  MOVE_CHILD,
  MOVE_PARENT,
  MOVE_THIRD,
  VACATE_PARENT,
  VACATE_CHILD,
  VACATE_THIRD,
  VANISH_PARENT,
  VANISH_CHILD,
  VANISH_THIRD,
  OPERATION_COUNT
};

#define BIT(operation) (UINT64_C(1) << (operation))
#define COMPLETED_MASK (BIT(OPERATION_COUNT) - 1)

static const uint64_t prerequisites[OPERATION_COUNT] = {
    0,
    0,
    0,
    BIT(MOVE_PARENT),
    BIT(MOVE_CHILD),
    BIT(MOVE_THIRD),
    BIT(VACATE_PARENT) | BIT(MOVE_CHILD),
    BIT(VACATE_CHILD) | BIT(VACATE_THIRD),
    BIT(VACATE_THIRD) | BIT(VACATE_PARENT),
};

struct Particle {
  unsigned identity;
};

struct Execution {
  _Atomic uint64_t state;
  _Atomic uint64_t released;
  atomic_bool claimed[OPERATION_COUNT];
  _Atomic(struct Particle *) particles[3];
};

struct Arrival {
  struct Execution *execution;
  enum Operation operation;
};

static void require(bool condition, const char *message) {
  if (!condition) {
    fprintf(stderr, "%s\n", message);
    exit(EXIT_FAILURE);
  }
}

static void check_thread(int result) {
  require(result == 0, "pthread operation failed");
}

static bool permitted(uint64_t completed, enum Operation operation) {
  if (operation == MOVE_PARENT) {
    return (completed & BIT(MOVE_CHILD)) || !(completed & BIT(MOVE_THIRD)) ||
           (completed & BIT(VACATE_THIRD));
  }
  if (operation == MOVE_THIRD) {
    return (completed & BIT(MOVE_CHILD)) || !(completed & BIT(MOVE_PARENT)) ||
           (completed & BIT(VACATE_PARENT));
  }
  return true;
}

static void prepare_effect(struct Execution *execution,
                           enum Operation operation) {
  /* These immutable reads exercise the real lifetime requirements. No
     operation accesses a Particle after publishing its completion. */
  static const unsigned required[OPERATION_COUNT] = {
      3, 5, 6, 5, 2, 6, 1, 2, 4,
  };
  for (unsigned particle = 0; particle < 3; ++particle) {
    if (required[operation] & (1u << particle)) {
      struct Particle *value = atomic_load(&execution->particles[particle]);
      require(value != NULL, "operation used a Vanished particle");
      require(value->identity == particle, "particle identity changed");
    }
  }
  if (operation >= VANISH_PARENT) {
    unsigned particle = operation - VANISH_PARENT;
    struct Particle *value =
        atomic_exchange(&execution->particles[particle], NULL);
    require(value != NULL, "Vanish executed twice");
    free(value);
  }
}

static void *arrive(void *argument) {
  struct Arrival *arrival = argument;
  struct Execution *execution = arrival->execution;
  enum Operation operation = arrival->operation;
  while (!(atomic_load(&execution->released) & BIT(operation))) {
    sched_yield();
  }
  bool expected = false;
  if (!atomic_compare_exchange_strong(&execution->claimed[operation], &expected,
                                      true)) {
    return NULL;
  }
  uint64_t observed = atomic_load(&execution->state);
  while ((observed & prerequisites[operation]) != prerequisites[operation]) {
    sched_yield();
    observed = atomic_load(&execution->state);
  }
  prepare_effect(execution, operation);
  for (;;) {
    if (!permitted(observed, operation)) {
      sched_yield();
      observed = atomic_load(&execution->state);
      continue;
    }
    unsigned rank = 0;
    for (unsigned index = 0; index < OPERATION_COUNT; ++index) {
      rank += (observed & BIT(index)) != 0;
    }
    uint64_t desired = observed | BIT(operation);
    desired |= (uint64_t)(operation + 1) << (OPERATION_COUNT + 4 * rank);
    /* The same atomic transition checks permission and commits the logical
       relationship effect. A competing Move cannot use an older decision. */
    if (atomic_compare_exchange_weak(&execution->state, &observed, desired)) {
      return NULL;
    }
  }
}

static void validate_order(uint64_t state) {
  /* This state interpreter checks positions and cycles independently of the
     permission formula. All three supplying Creates precede this interval. */
  static const int owner[6] = {-1, 0, -1, -1, 2, 1};
  static const int moved[3] = {1, 0, 2};
  static const int source[3] = {1, 0, 2};
  static const int target[3] = {3, 4, 5};
  static const int selected_position[3] = {4, 3, 5};
  int positions[3] = {0, 1, 2};
  bool live[3] = {true, true, true};
  uint64_t completed = 0;
  for (unsigned rank = 0; rank < OPERATION_COUNT; ++rank) {
    unsigned encoded = (state >> (OPERATION_COUNT + 4 * rank)) & 15;
    require(encoded > 0 && encoded <= OPERATION_COUNT, "missing completion");
    unsigned operation = encoded - 1;
    require(!(completed & BIT(operation)), "operation completed twice");
    if (operation <= MOVE_THIRD) {
      int particle = moved[operation];
      require(live[particle], "Move after Vanish");
      require(positions[particle] == source[operation], "wrong Move source");
      for (unsigned other = 0; other < 3; ++other) {
        require(positions[other] != target[operation], "occupied Move target");
      }
      positions[particle] = target[operation];
    } else if (operation <= VACATE_THIRD) {
      unsigned particle = operation - VACATE_PARENT;
      require(live[particle], "Vacate after Vanish");
      require(positions[particle] == selected_position[particle],
              "wrong selected position");
      positions[particle] = -1;
    } else {
      unsigned particle = operation - VANISH_PARENT;
      require(live[particle] && positions[particle] == -1, "invalid Vanish");
      for (unsigned other = 0; other < 3; ++other) {
        require(positions[other] == -1 ||
                    owner[positions[other]] != (int)particle,
                "Vanish removed an occupied position's defining particle");
      }
      live[particle] = false;
    }
    for (unsigned particle = 0; particle < 3; ++particle) {
      unsigned visited = 0;
      int current = (int)particle;
      while (current != -1 && positions[current] != -1) {
        require(live[current],
                "occupied position belongs to a Vanished particle");
        require(!(visited & (1u << current)), "circular particle arrangement");
        visited |= 1u << current;
        current = owner[positions[current]];
        if (current != -1) {
          require(live[current], "position's defining particle has Vanished");
        }
      }
    }
    completed |= BIT(operation);
  }
  require(completed == COMPLETED_MASK, "incomplete execution");
}

static void run(const enum Operation *prefix, unsigned length) {
  struct Execution execution;
  atomic_init(&execution.state, 0);
  atomic_init(&execution.released, 0);
  require(atomic_is_lock_free(&execution.state),
          "state atomic is not lock-free");
  for (unsigned particle = 0; particle < 3; ++particle) {
    struct Particle *value = malloc(sizeof(*value));
    require(value != NULL, "allocation failed");
    value->identity = particle;
    atomic_init(&execution.particles[particle], value);
  }
  for (unsigned operation = 0; operation < OPERATION_COUNT; ++operation) {
    atomic_init(&execution.claimed[operation], false);
  }
  pthread_t workers[2 * OPERATION_COUNT];
  struct Arrival arrivals[2 * OPERATION_COUNT];
  for (unsigned index = 0; index < 2 * OPERATION_COUNT; ++index) {
    arrivals[index] = (struct Arrival){&execution, index % OPERATION_COUNT};
    check_thread(
        pthread_create(&workers[index], NULL, arrive, &arrivals[index]));
  }
  for (unsigned index = 0; index < length; ++index) {
    atomic_fetch_or(&execution.released, BIT(prefix[index]));
    while (!(atomic_load(&execution.state) & BIT(prefix[index]))) {
      sched_yield();
    }
  }
  atomic_store(&execution.released, COMPLETED_MASK);
  for (unsigned index = 0; index < 2 * OPERATION_COUNT; ++index) {
    check_thread(pthread_join(workers[index], NULL));
  }
  /* Synchronization records outlive every arrival, including duplicates. */
  validate_order(atomic_load(&execution.state));
}

int main(void) {
  const enum Operation orders[4][3] = {
      {MOVE_CHILD, MOVE_PARENT, MOVE_THIRD},
      {MOVE_CHILD, MOVE_THIRD, MOVE_PARENT},
      {MOVE_PARENT, MOVE_CHILD, MOVE_THIRD},
      {MOVE_THIRD, MOVE_CHILD, MOVE_PARENT},
  };
  for (unsigned index = 0; index < 4; ++index) {
    run(orders[index], 3);
  }
  const enum Operation parent_release[] = {
      MOVE_PARENT,
      VACATE_PARENT,
      MOVE_THIRD,
      MOVE_CHILD,
  };
  const enum Operation third_release[] = {
      MOVE_THIRD,
      VACATE_THIRD,
      MOVE_PARENT,
      MOVE_CHILD,
  };
  run(parent_release, 4);
  run(third_release, 4);
  for (unsigned repetition = 0; repetition < 200; ++repetition) {
    run(NULL, 0);
  }
  puts("206 relationship schedules completed with duplicate arrivals");
  return EXIT_SUCCESS;
}
