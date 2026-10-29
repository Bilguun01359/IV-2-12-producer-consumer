# IV-2-12 The Producer-Consumer Problem

[Монгол хэл / Mongolian](README.mn.md)

F.CSM302 Operating Systems, Assignment 1 (BD1).
Textbook: Operating System Concepts, Chapter 7 Synchronization Examples, Programming Project 4.
UI: Buffer animation.

## What it is

A bounded buffer shared by producer and consumer threads, synchronized with POSIX semaphores and a mutex lock exactly as in Section 7.1.1 (Figures 7.1 and 7.2). A Python (tkinter) window runs the C program and animates what its threads really do.

- Producers put random numbers into a circular buffer and sleep (block) when it is full.
- Consumers take numbers out and sleep (block) when it is empty.
- The window shows every slot, the in and out positions, the values of the empty and full semaphores, and a "zzz" when a thread is blocked.

## Requirements

- Ubuntu 24.04 (native or WSL2). Linux only: the C part uses Pthreads and unnamed POSIX semaphores.
- gcc and make
- Python 3 with tkinter
- git

    sudo apt update
    sudo apt install -y build-essential python3 python3-tk git

On WSL the window needs WSLg (Windows 11, or Windows 10 with a recent `wsl --update`).

## Quick Start

    git clone https://github.com/Bilguun01359/IV-2-12-producer-consumer.git
    cd IV-2-12-producer-consumer
    make
    python3 src/ui.py

Press Start. Change the settings and press Reset or Start again to try other values.

## Using the window

| Control | Meaning |
|---|---|
| Buffer size | Number of slots, 1-20 |
| Producers, Consumers | Number of threads of each kind, 0-20 |
| Delay (ms) | Average sleep of a thread between two actions, 10-10000 |
| Duration (s) | How long the program runs before it ends, 1-3600 |
| Auto | Threads act at random times |
| Manual | Threads act only when you press Produce (P) or Consume (C) |
| Pause / Resume | Stops and continues all threads |
| Stop / Reset | Ends the run / clears the window |

Try these:

1. Producers 3, Consumers 1: the buffer fills up and the producers show zzz.
2. Producers 1, Consumers 3: the buffer is mostly empty and the consumers show zzz.
3. Manual mode, buffer size 3: press Produce four times. The fourth producer blocks. Press Consume once and it finishes.

## Command line (without the window)

    ./pc [-s buffer_size] [-d delay_ms] [-m] sleep_seconds producers consumers
    ./pc -s 3 -d 200 5 2 2

This matches the project text: how long to sleep before terminating, the number of producers, the number of consumers. Each action prints one line:

    [PUT] producer=1 item=59 slot=0 count=1
    [GET] consumer=2 item=59 slot=0 count=0
    [WAIT] producer=3

## Project structure

    src/buffer.h, src/buffer.c   buffer, insert_item(), remove_item(), semaphores and mutex
    src/main.c                   command line, producer and consumer threads
    src/ui.py                    tkinter window
    Makefile                     make builds the program, make clean removes it

## How it maps to the textbook

| Book | Code |
|---|---|
| semaphore empty = n | `sem_t empty`, initialized to the buffer size |
| semaphore full = 0 | `sem_t full`, initialized to 0 |
| mutex | `pthread_mutex_t mutex` (a mutex lock, as the project asks) |
| wait() / signal() | `sem_wait()` / `sem_post()` |
| Figure 7.1 producer | `insert_item()` |
| Figure 7.2 consumer | `remove_item()` |

## Notes

- The buffer size is 5 by default (`BUFFER_SIZE`) and can be changed up to 20.
- Items are random numbers from 0 to 999.
- Pause uses SIGSTOP and SIGCONT, so it works on Linux and WSL.

## AI and sources

AI assistance (Claude) was used while designing and writing this project. The synchronization algorithm follows Section 7.1.1 of the textbook.
