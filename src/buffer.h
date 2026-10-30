#ifndef BUFFER_H
#define BUFFER_H

typedef int buffer_item;

#define BUFFER_SIZE 5
#define MAX_BUFFER_SIZE 20

int buffer_init(int size, int use_mutex);
void buffer_destroy(void);
void buffer_set_thread(char role, int id);
int insert_item(buffer_item item);
int remove_item(buffer_item *item);
int buffer_stats(long *produced, long *consumed, int *in_buffer);

#endif
