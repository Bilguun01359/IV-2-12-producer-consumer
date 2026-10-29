#include <stdio.h>
#include <errno.h>
#include <pthread.h>
#include <semaphore.h>
#include "buffer.h"

static buffer_item buffer[MAX_BUFFER_SIZE];
static int size = 0;
static int in = 0;
static int out = 0;
static int count = 0;
static sem_t empty;
static sem_t full;
static pthread_mutex_t mutex;
static _Thread_local char my_role = '?';
static _Thread_local int my_id = 0;

int buffer_init(int n) {
    if (n < 1 || n > MAX_BUFFER_SIZE)
        return -1;
    size = n;
    in = 0;
    out = 0;
    count = 0;
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

static int take(sem_t *s) {
    if (sem_trywait(s) == 0)
        return 0;
    if (errno != EAGAIN)
        return -1;
    if (my_role == 'P')
        printf("[WAIT] producer=%d\n", my_id);
    else
        printf("[WAIT] consumer=%d\n", my_id);
    fflush(stdout);
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
    pthread_mutex_lock(&mutex);
    int slot = in;
    buffer[slot] = item;
    in = (in + 1) % size;
    count++;
    printf("[PUT] producer=%d item=%d slot=%d count=%d\n", my_id, item, slot, count);
    fflush(stdout);
    pthread_mutex_unlock(&mutex);
    sem_post(&full);
    return 0;
}

int remove_item(buffer_item *item) {
    if (size == 0)
        return -1;
    if (take(&full) != 0)
        return -1;
    pthread_mutex_lock(&mutex);
    int slot = out;
    *item = buffer[slot];
    out = (out + 1) % size;
    count--;
    printf("[GET] consumer=%d item=%d slot=%d count=%d\n", my_id, *item, slot, count);
    fflush(stdout);
    pthread_mutex_unlock(&mutex);
    sem_post(&empty);
    return 0;
}
