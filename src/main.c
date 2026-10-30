#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <getopt.h>
#include <time.h>
#include <pthread.h>
#include <semaphore.h>
#include "buffer.h"

static int manual = 0;
static int delay_ms = 1000;
static unsigned int base_seed = 0;
static sem_t p_token;
static sem_t c_token;
static volatile sig_atomic_t stop_requested = 0;

static void on_signal(int sig) {
    (void)sig;
    stop_requested = 1;
}

static void random_sleep(unsigned int *seed) {
    int ms = delay_ms / 2 + (int)(rand_r(seed) % (unsigned int)(delay_ms + 1));
    usleep((useconds_t)ms * 1000);
}

static void *producer(void *param) {
    int id = *(int *)param;
    unsigned int seed = base_seed ^ (unsigned int)(id * 7919);
    buffer_item item;
    buffer_set_thread('P', id);
    while (1) {
        if (manual)
            sem_wait(&p_token);
        else
            random_sleep(&seed);
        item = (buffer_item)(rand_r(&seed) % 1000);
        int r = insert_item(item);
        if (r > 0)
            break;
        if (r < 0)
            fprintf(stderr, "[ERROR] producer=%d insert_item failed\n", id);
    }
    return NULL;
}

static void *consumer(void *param) {
    int id = *(int *)param;
    unsigned int seed = base_seed ^ (unsigned int)(id * 104729);
    buffer_item item;
    buffer_set_thread('C', id);
    while (1) {
        if (manual)
            sem_wait(&c_token);
        else
            random_sleep(&seed);
        int r = remove_item(&item);
        if (r > 0)
            break;
        if (r < 0)
            fprintf(stderr, "[ERROR] consumer=%d remove_item failed\n", id);
    }
    return NULL;
}

static long parse_num(const char *text, long min, long max, const char *name) {
    char *end;
    long v = strtol(text, &end, 10);
    if (*text == '\0' || *end != '\0' || v < min || v > max) {
        fprintf(stderr, "Error: %s must be an integer from %ld to %ld (got \"%s\")\n", name, min, max, text);
        exit(1);
    }
    return v;
}

static void usage(const char *prog) {
    fprintf(stderr, "Usage: %s [options] sleep_seconds producers consumers\n", prog);
    fprintf(stderr, "  sleep_seconds  how long to run, 0-3600\n");
    fprintf(stderr, "  producers      number of producer threads, 0-20\n");
    fprintf(stderr, "  consumers      number of consumer threads, 0-20\n");
    fprintf(stderr, "Options:\n");
    fprintf(stderr, "  -s, --buffer N    buffer size, 1-%d (default %d)\n", MAX_BUFFER_SIZE, BUFFER_SIZE);
    fprintf(stderr, "  -d, --delay MS    average thread delay in ms, 10-10000 (default 1000)\n");
    fprintf(stderr, "  -r, --seed N      random seed, 1-2147483647 (default: random)\n");
    fprintf(stderr, "  -n, --no-mutex    do not use the mutex (shows a race condition)\n");
    fprintf(stderr, "  -m, --manual      threads act only on commands from stdin (P, C, Q)\n");
}

int main(int argc, char *argv[]) {
    int size = BUFFER_SIZE;
    int use_mutex = 1;
    int opt;
    static struct option longopts[] = {
        {"buffer", required_argument, NULL, 's'},
        {"delay", required_argument, NULL, 'd'},
        {"seed", required_argument, NULL, 'r'},
        {"no-mutex", no_argument, NULL, 'n'},
        {"manual", no_argument, NULL, 'm'},
        {0, 0, 0, 0}
    };

    while ((opt = getopt_long(argc, argv, "s:d:r:nm", longopts, NULL)) != -1) {
        switch (opt) {
        case 's':
            size = (int)parse_num(optarg, 1, MAX_BUFFER_SIZE, "buffer size");
            break;
        case 'd':
            delay_ms = (int)parse_num(optarg, 10, 10000, "delay");
            break;
        case 'r':
            base_seed = (unsigned int)parse_num(optarg, 1, 2147483647L, "seed");
            break;
        case 'n':
            use_mutex = 0;
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
    int sleep_s = (int)parse_num(argv[optind], 0, 3600, "sleep_seconds");
    int np = (int)parse_num(argv[optind + 1], 0, 20, "producers");
    int nc = (int)parse_num(argv[optind + 2], 0, 20, "consumers");

    if (base_seed == 0)
        base_seed = ((unsigned int)time(NULL) ^ (unsigned int)getpid()) % 2147483647u + 1;

    if (buffer_init(size, use_mutex) != 0) {
        fprintf(stderr, "Error: cannot initialize buffer\n");
        return 1;
    }
    sem_init(&p_token, 0, 0);
    sem_init(&c_token, 0, 0);

    struct sigaction sa;
    memset(&sa, 0, sizeof sa);
    sa.sa_handler = on_signal;
    sigemptyset(&sa.sa_mask);
    sigaction(SIGINT, &sa, NULL);
    sigaction(SIGTERM, &sa, NULL);

    setvbuf(stdout, NULL, _IOLBF, 0);
    printf("[START] size=%d producers=%d consumers=%d delay=%d mode=%s mutex=%s seed=%u\n",
           size, np, nc, delay_ms, manual ? "manual" : "auto", use_mutex ? "on" : "off", base_seed);
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
        while (!stop_requested && fgets(line, sizeof line, stdin)) {
            if (line[0] == 'P')
                sem_post(&p_token);
            else if (line[0] == 'C')
                sem_post(&c_token);
            else if (line[0] == 'Q')
                break;
        }
    } else {
        unsigned int left = (unsigned int)sleep_s;
        while (left > 0 && !stop_requested)
            left = sleep(left);
    }

    buffer_close();
    return 0;
}
