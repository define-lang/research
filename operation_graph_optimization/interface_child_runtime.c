#include <pthread.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>

struct Particle {
  struct Particle *child;
};

struct Gateway {
  struct Particle *input;
  struct Particle *result;
};

struct ChildCreate {
  struct Particle *particle;
  pthread_mutex_t mutex;
  pthread_cond_t changed;
  bool permitted;
  bool completed;
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

static void *worker_create_child(void *argument) {
  struct ChildCreate *operation = argument;
  check_thread(pthread_mutex_lock(&operation->mutex));
  while (!operation->permitted) {
    check_thread(pthread_cond_wait(&operation->changed, &operation->mutex));
  }
  check_thread(pthread_mutex_unlock(&operation->mutex));

  /* The identified child position belongs to this particle, so the operation
     neither receives nor dereferences the future action's Gateway. */
  operation->particle->child = calloc(1, sizeof(struct Particle));
  require(operation->particle->child != NULL, "child allocation failed");

  check_thread(pthread_mutex_lock(&operation->mutex));
  operation->completed = true;
  check_thread(pthread_cond_signal(&operation->changed));
  check_thread(pthread_mutex_unlock(&operation->mutex));
  return NULL;
}

static void run_schedule(unsigned schedule) {
  struct Particle *source = calloc(1, sizeof(struct Particle));
  require(source != NULL, "particle allocation failed");
  struct ChildCreate operation = {
      .particle = source,
      .permitted = schedule != 1,
      .completed = false,
  };
  check_thread(pthread_mutex_init(&operation.mutex, NULL));
  check_thread(pthread_cond_init(&operation.changed, NULL));
  pthread_t worker;
  check_thread(pthread_create(&worker, NULL, worker_create_child, &operation));

  if (schedule == 0) {
    /* This schedule proves that creation of the action's parent is not an
       allocation prerequisite for its operation on the supplied particle. */
    check_thread(pthread_mutex_lock(&operation.mutex));
    while (!operation.completed) {
      check_thread(pthread_cond_wait(&operation.changed, &operation.mutex));
    }
    check_thread(pthread_mutex_unlock(&operation.mutex));
  }

  struct Gateway *gateway = calloc(1, sizeof(struct Gateway));
  require(gateway != NULL, "gateway allocation failed");
  gateway->input = source;
  source = NULL;
  gateway->result = gateway->input;
  gateway->input = NULL;
  struct Particle *returned = gateway->result;
  gateway->result = NULL;
  require(returned == operation.particle, "Move changed particle identity");
  free(gateway);

  /* Vacancy need not wait for the pending child Create. Its defining
     particle remains alive through the independent lifetime requirement. */
  returned = NULL;
  require(source == NULL && returned == NULL,
          "vacated position remains occupied");
  if (schedule == 1) {
    /* The child operation is deliberately released after the Gateway has
       vanished; retaining only its identified particle must suffice. */
    check_thread(pthread_mutex_lock(&operation.mutex));
    operation.permitted = true;
    check_thread(pthread_cond_signal(&operation.changed));
    check_thread(pthread_mutex_unlock(&operation.mutex));
  }

  check_thread(pthread_join(worker, NULL));
  struct Particle *child = operation.particle->child;
  require(child != NULL, "child Create was lost");
  operation.particle->child = NULL;
  free(child);
  free(operation.particle);
  check_thread(pthread_cond_destroy(&operation.changed));
  check_thread(pthread_mutex_destroy(&operation.mutex));
}

int main(void) {
  for (unsigned repetition = 0; repetition < 200; ++repetition) {
    run_schedule(0);
    run_schedule(1);
    /* This run imposes neither cross-branch order; only the final lifetime
       Join protects reclamation of the particle supplying /child. */
    run_schedule(2);
  }
  puts("600 interface-child schedules completed");
  return EXIT_SUCCESS;
}
