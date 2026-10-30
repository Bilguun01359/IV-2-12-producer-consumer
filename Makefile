.RECIPEPREFIX = >
CC = gcc
CFLAGS = -Wall -Wextra -O2 -pthread

pc: src/main.c src/buffer.c src/buffer.h
> $(CC) $(CFLAGS) -o pc src/main.c src/buffer.c

test: pc
> python3 tests/run_tests.py

clean:
> rm -f pc

.PHONY: test clean
