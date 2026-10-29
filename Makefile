.RECIPEPREFIX = >
CC = gcc
CFLAGS = -Wall -Wextra -O2 -pthread

pc: src/main.c src/buffer.c src/buffer.h
> $(CC) $(CFLAGS) -o pc src/main.c src/buffer.c

clean:
> rm -f pc

.PHONY: clean
