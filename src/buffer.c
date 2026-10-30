#include <stdio.h>
#include <errno.h>
#include <pthread.h>
#include <semaphore.h>
#include "buffer.h"

static buffer_item buffer[MAX_BUFFER_SIZE];
static int size = 0;
static int use_mutex = 1;
static volatile int in = 0;
static volatile int out = 0;
static volatile int count = 0;
static long produced = 0;
static long consumed = 0;
static volatile int finished = 0;
static sem_t empty;
static sem_t full;
static pthread_mutex_t mutex;
static _Thread_local char my_role = '?';
static _Thread_local int my_id = 0;

int buffer_init(int n, int mutex_on) {
    if (n < 1 || n > MAX_BUFFER_SIZE)
        return -1;
    size = n;
    use_mutex = mutex_on;
    in = 0;
    out = 0;
    count = 0;
    produced = 0;
    consumed = 0;
    finished = 0;
    if (sem_init(&empty, 0, n) != 0)
        return -1;
    if (sem_init(&full, 0, 0) != 0)
        return -1;
    if (pthread_mutex_init(&mutex, NULL) != 0)
        return -1;
    return 0;
}

void buffer_destroy(void) {
    sem_destroy(&empty);
    sem_destroy(&full);
    pthread_mutex_destroy(&mutex);
}

void buffer_set_thread(char role, int id) {
    my_role = role;
    my_id = id;
}

static void enter_section(void) {
    if (use_mutex)
        pthread_mutex_lock(&mutex);
}

static void leave_section(void) {
    if (use_mutex)
        pthread_mutex_unlock(&mutex);
}

static int take(sem_t *s) {
    if (sem_trywait(s) == 0)
        return 0;
    if (errno != EAGAIN)
        return -1;
    enter_section();
    if (!finished) {
        if (my_role == 'P')
            printf("[WAIT] producer=%d\n", my_id);
        else
            printf("[WAIT] consumer=%d\n", my_id);
        fflush(stdout);
    }
    leave_section();
    while (sem_wait(s) == -1) {
        if (errno != EINTR)
            return -1;
    }
    return 0;
}

int insert_item(buffer_item item) {
    if (size == 0)
        return -1;
    if (take(&empty) != 0)
        return -1;
    enter_section();
    if (finished) {
        leave_section();
        return 1;
    }
    int slot = in;
    buffer[slot] = item;
    in = (slot + 1) % size;
    count = count + 1;
    __atomic_fetch_add(&produced, 1, __ATOMIC_RELAXED);
    printf("[PUT] producer=%d item=%d slot=%d count=%d\n", my_id, item, slot, count);
    fflush(stdout);
    leave_section();
    sem_post(&full);
    return 0;
}

int remove_item(buffer_item *item) {
    if (size == 0)
        return -1;
    if (take(&full) != 0)
        return -1;
    enter_section();
    if (finished) {
        leave_section();
        return 1;
    }
    int slot = out;
    *item = buffer[slot];
    out = (slot + 1) % size;
    count = count - 1;
    __atomic_fetch_add(&consumed, 1, __ATOMIC_RELAXED);
    printf("[GET] consumer=%d item=%d slot=%d count=%d\n", my_id, *item, slot, count);
    fflush(stdout);
    leave_section();
    sem_post(&empty);
    return 0;
}

int buffer_close(void) {
    enter_section();
    finished = 1;
    long p = __atomic_load_n(&produced, __ATOMIC_RELAXED);
    long c = __atomic_load_n(&consumed, __ATOMIC_RELAXED);
    int n = count;
    int ok = (p - c == n) && n >= 0 && n <= size;
    printf("[END] produced=%ld consumed=%ld in_buffer=%d invariant=%s\n", p, c, n, ok ? "OK" : "FAIL");
    fflush(stdout);
    leave_section();
    return ok;
}
