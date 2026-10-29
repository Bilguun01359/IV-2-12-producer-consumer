#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <pthread.h>
#include <semaphore.h>
#include "buffer.h"

static int manual = 0;
static int delay_ms = 1000;
static sem_t p_token;
static sem_t c_token;

static void random_sleep(unsigned int *seed) {
    int ms = delay_ms / 2 + (int)(rand_r(seed) % (unsigned int)(delay_ms + 1));
    usleep((useconds_t)ms * 1000);
}

static void *producer(void *param) {
    int id = *(int *)param;
    unsigned int seed = (unsigned int)time(NULL) ^ (unsigned int)(id * 7919);
    buffer_item item;
    buffer_set_thread('P', id);
    while (1) {
        if (manual)
            sem_wait(&p_token);
        else
            random_sleep(&seed);
        item = (buffer_item)(rand_r(&seed) % 1000);
        if (insert_item(item))
            fprintf(stderr, "[ERROR] producer=%d insert_item failed\n", id);
    }
    return NULL;
}

static void *consumer(void *param) {
    int id = *(int *)param;
    unsigned int seed = (unsigned int)time(NULL) ^ (unsigned int)(id * 104729);
    buffer_item item;
    buffer_set_thread('C', id);
    while (1) {
        if (manual)
            sem_wait(&c_token);
        else
            random_sleep(&seed);
        if (remove_item(&item))
            fprintf(stderr, "[ERROR] consumer=%d remove_item failed\n", id);
    }
    return NULL;
}

static int parse_int(const char *text, int min, int max, const char *name) {
    char *end;
    long v = strtol(text, &end, 10);
    if (*text == '\0' || *end != '\0' || v < min || v > max) {
        fprintf(stderr, "Error: %s must be an integer from %d to %d (got \"%s\")\n", name, min, max, text);
        exit(1);
    }
    return (int)v;
}

static void usage(const char *prog) {
    fprintf(stderr, "Usage: %s [-s buffer_size] [-d delay_ms] [-m] sleep_seconds producers consumers\n", prog);
    fprintf(stderr, "  -s  buffer size, 1-%d (default %d)\n", MAX_BUFFER_SIZE, BUFFER_SIZE);
    fprintf(stderr, "  -d  average thread delay in ms, 10-10000 (default 1000)\n");
    fprintf(stderr, "  -m  manual mode: threads act only on commands from stdin (P, C, Q)\n");
}

int main(int argc, char *argv[]) {
    int size = BUFFER_SIZE;
    int opt;

    while ((opt = getopt(argc, argv, "s:d:m")) != -1) {
        switch (opt) {
        case 's':
            size = parse_int(optarg, 1, MAX_BUFFER_SIZE, "buffer size");
            break;
        case 'd':
            delay_ms = parse_int(optarg, 10, 10000, "delay");
            break;
        case 'm':
            manual = 1;
            break;
        default:
            usage(argv[0]);
            return 1;
        }
    }
    if (argc - optind != 3) {
        usage(argv[0]);
        return 1;
    }
    int sleep_s = parse_int(argv[optind], 0, 3600, "sleep_seconds");
    int np = parse_int(argv[optind + 1], 0, 20, "producers");
    int nc = parse_int(argv[optind + 2], 0, 20, "consumers");

    if (buffer_init(size) != 0) {
        fprintf(stderr, "Error: cannot initialize buffer\n");
        return 1;
    }
    sem_init(&p_token, 0, 0);
    sem_init(&c_token, 0, 0);

    setvbuf(stdout, NULL, _IOLBF, 0);
    printf("[START] size=%d producers=%d consumers=%d delay=%d mode=%s\n",
           size, np, nc, delay_ms, manual ? "manual" : "auto");
    fflush(stdout);

    pthread_t ptid[20];
    pthread_t ctid[20];
    int pid[20];
    int cid[20];

    for (int i = 0; i < np; i++) {
        pid[i] = i + 1;
        pthread_create(&ptid[i], NULL, producer, &pid[i]);
    }
    for (int i = 0; i < nc; i++) {
        cid[i] = i + 1;
        pthread_create(&ctid[i], NULL, consumer, &cid[i]);
    }

    if (manual) {
        char line[64];
        while (fgets(line, sizeof line, stdin)) {
            if (line[0] == 'P')
                sem_post(&p_token);
            else if (line[0] == 'C')
                sem_post(&c_token);
            else if (line[0] == 'Q')
                break;
        }
    } else {
        sleep(sleep_s);
    }

    printf("[END]\n");
    fflush(stdout);
    return 0;
}
