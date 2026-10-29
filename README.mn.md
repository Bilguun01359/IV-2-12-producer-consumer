# IV-2-12 Producer-Consumer бодлого

[English](README.md)

F.CSM302 Үйлдлийн систем, Бие даалт 1 (БД1).
Сурах бичиг: Operating System Concepts, Бүлэг 7 Synchronization Examples, Programming Project 4.
UI: Buffer animation.

## Энэ юу вэ

Producer ба consumer thread-үүдийн хуваалцдаг хязгаартай buffer (bounded buffer). Synchronization-ийг сурах бичгийн Section 7.1.1 (Figure 7.1, 7.2)-ийн дагуу POSIX semaphore болон mutex lock-оор хийсэн. Python (tkinter) цонх нь C программыг ажиллуулж, түүний thread-үүд бодитоор юу хийж байгааг анимациар харуулна.

- Producer-ууд санамсаргүй тоог circular buffer-т хийж, buffer дүүрсэн үед унтаж (block болж) хүлээнэ.
- Consumer-ууд тоог буцааж авч, buffer хоосон үед унтаж хүлээнэ.
- Цонх дээр slot бүр, in ба out байрлал, `empty` ба `full` semaphore-ийн утга, thread block болсон үед "zzz" харагдана.

## Шаардлага

- Ubuntu 24.04 (шууд эсвэл WSL2). Зөвхөн Linux: C хэсэг нь Pthreads ба нэргүй POSIX semaphore ашигладаг.
- gcc ба make
- tkinter-тэй Python 3
- git

Суулгах команд:

    sudo apt update
    sudo apt install -y build-essential python3 python3-tk git

WSL дээр цонх нээгдэхийн тулд WSLg хэрэгтэй (Windows 11, эсвэл сүүлийн `wsl --update` хийсэн Windows 10).

## Хурдан эхлэх (Quick Start)

    git clone https://github.com/Bilguun01359/IV-2-12-producer-consumer.git
    cd IV-2-12-producer-consumer
    make
    python3 src/ui.py

Start товчийг дарна. Тохиргоог өөрчилж Reset эсвэл Start дарвал өөр утгаар дахин туршиж болно.

## Цонхыг хэрхэн ашиглах

| Хэсэг | Утга |
|---|---|
| Buffer size | Slot-ийн тоо, 1-20 |
| Producers, Consumers | Тус бүрийн thread-ийн тоо, 0-20 |
| Delay (ms) | Thread хоёр үйлдлийн хооронд дунджаар унтах хугацаа, 10-10000 |
| Duration (s) | Программ хэдэн секунд ажиллаад дуусах, 1-3600 |
| Auto | Thread-үүд санамсаргүй цагт ажиллана |
| Manual | Thread-үүд зөвхөн Produce (P) эсвэл Consume (C) товч дарахад ажиллана |
| Pause / Resume | Бүх thread-ийг зогсоож, үргэлжлүүлнэ |
| Stop / Reset | Ажиллуулалтыг зогсооно / цонхыг цэвэрлэнэ |

Туршиж үзэх жишээ:

1. Producers 3, Consumers 1: buffer дүүрч, producer-ууд zzz болно.
2. Producers 1, Consumers 3: buffer ихэвчлэн хоосон байж, consumer-ууд zzz болно.
3. Manual горим, buffer size 3: Produce-ийг дөрвөн удаа дар. Дөрөв дэх producer block болно. Consume-ийг нэг удаа дарахад тэр дуусна.

## Командын мөрөөс (цонхгүйгээр)

    ./pc [-s buffer_size] [-d delay_ms] [-m] sleep_seconds producers consumers
    ./pc -s 3 -d 200 5 2 2

Энэ нь төслийн текстэд заасантай таарна: хэр удаан унтаж дуусах, producer-ийн тоо, consumer-ийн тоо. Үйлдэл бүр нэг мөр хэвлэнэ:

    [PUT] producer=1 item=59 slot=0 count=1
    [GET] consumer=2 item=59 slot=0 count=0
    [WAIT] producer=3

## Төслийн бүтэц

    src/buffer.h, src/buffer.c   buffer, insert_item(), remove_item(), semaphore ба mutex
    src/main.c                   командын мөр, producer ба consumer thread-үүд
    src/ui.py                    tkinter цонх
    Makefile                     make нь программыг build хийнэ, make clean устгана

## Сурах бичигтэй харьцуулалт

| Ном | Код |
|---|---|
| semaphore empty = n | `sem_t empty`, анх buffer-ийн хэмжээтэй тэнцүү |
| semaphore full = 0 | `sem_t full`, анх 0 |
| mutex | `pthread_mutex_t mutex` (даалгаврын шаардсанаар mutex lock) |
| wait() / signal() | `sem_wait()` / `sem_post()` |
| Figure 7.1 producer | `insert_item()` |
| Figure 7.2 consumer | `remove_item()` |

## Тэмдэглэл

- Buffer-ийн хэмжээ анхдагчаар 5 (`BUFFER_SIZE`), 20 хүртэл өөрчилж болно.
- Item нь 0-ээс 999 хүртэлх санамсаргүй тоо.
- Pause нь SIGSTOP ба SIGCONT ашигладаг тул Linux, WSL дээр ажиллана.

## AI ба эх сурвалж

Энэ төслийг зохиомжлох, бичихэд AI (Claude) тусалсан. Synchronization-ий алгоритм нь сурах бичгийн Section 7.1.1-ийг дагана.
