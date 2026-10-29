import os
import queue
import re
import signal
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk

HERE = os.path.dirname(os.path.abspath(__file__))
BINARY = os.path.join(os.path.dirname(HERE), "pc.exe" if os.name == "nt" else "pc")

BG = "#f5f6f8"
SLOT_EMPTY = "#dfe3e8"
SLOT_FULL = "#4caf72"
LINE = "#5b6573"
PUT_COLOR = "#e8912d"
GET_COLOR = "#2f7fd0"
WAIT_COLOR = "#c0392b"
TEXT = "#222831"

LIMITS = {
    "size": (1, 20),
    "producers": (0, 20),
    "consumers": (0, 20),
    "delay": (10, 10000),
    "duration": (1, 3600),
}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Producer-Consumer: buffer animation")
        self.configure(bg=BG)
        self.minsize(960, 700)

        self.proc = None
        self.paused = False
        self.lines = queue.Queue()
        self.flash = {}
        self.reset_state(5, 1, 1)

        self.v_size = tk.StringVar(value="5")
        self.v_prod = tk.StringVar(value="1")
        self.v_cons = tk.StringVar(value="1")
        self.v_delay = tk.StringVar(value="800")
        self.v_dur = tk.StringVar(value="60")
        self.v_mode = tk.StringVar(value="auto")
        self.v_msg = tk.StringVar(value="Set the parameters and press Start.")

        self.build_controls()
        self.build_canvas()
        self.build_status()
        self.build_log()
        self.build_legend()
        self.update_buttons()
        self.redraw()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(30, self.poll)

    def reset_state(self, size, np_, nc):
        self.size = size
        self.np = np_
        self.nc = nc
        self.slots = [None] * size
        self.next_in = 0
        self.next_out = 0
        self.count = 0
        self.produced = 0
        self.consumed = 0
        self.wait_p = set()
        self.wait_c = set()
        self.waits_total = 0
        self.flash = {}

    def build_controls(self):
        box = ttk.LabelFrame(self, text="Settings")
        box.pack(fill="x", padx=10, pady=(10, 4))
        fields = [
            ("Buffer size (1-20)", self.v_size),
            ("Producers (0-20)", self.v_prod),
            ("Consumers (0-20)", self.v_cons),
            ("Delay, ms (10-10000)", self.v_delay),
            ("Duration, s (1-3600)", self.v_dur),
        ]
        self.entries = []
        for i, (label, var) in enumerate(fields):
            ttk.Label(box, text=label).grid(row=0, column=i, padx=8, pady=(6, 0), sticky="w")
            e = ttk.Entry(box, textvariable=var, width=12)
            e.grid(row=1, column=i, padx=8, pady=(0, 8), sticky="w")
            self.entries.append(e)

        mode = ttk.Frame(box)
        mode.grid(row=0, column=5, rowspan=2, padx=12)
        self.rb_auto = ttk.Radiobutton(mode, text="Auto (random)", variable=self.v_mode, value="auto")
        self.rb_manual = ttk.Radiobutton(mode, text="Manual (step)", variable=self.v_mode, value="manual")
        self.rb_auto.pack(anchor="w")
        self.rb_manual.pack(anchor="w")

        row2 = ttk.Frame(self)
        row2.pack(fill="x", padx=10, pady=4)
        self.b_start = ttk.Button(row2, text="Start", command=self.start)
        self.b_pause = ttk.Button(row2, text="Pause", command=self.toggle_pause)
        self.b_stop = ttk.Button(row2, text="Stop", command=self.stop)
        self.b_reset = ttk.Button(row2, text="Reset", command=self.reset)
        self.b_prod = ttk.Button(row2, text="Produce (P)", command=lambda: self.send("P"))
        self.b_cons = ttk.Button(row2, text="Consume (C)", command=lambda: self.send("C"))
        for b in (self.b_start, self.b_pause, self.b_stop, self.b_reset):
            b.pack(side="left", padx=3)
        ttk.Separator(row2, orient="vertical").pack(side="left", fill="y", padx=10)
        self.b_prod.pack(side="left", padx=3)
        self.b_cons.pack(side="left", padx=3)

        self.lbl_msg = tk.Label(self, textvariable=self.v_msg, bg=BG, fg=TEXT, anchor="w")
        self.lbl_msg.pack(fill="x", padx=12, pady=(2, 0))

    def build_canvas(self):
        self.canvas = tk.Canvas(self, width=940, height=290, bg="white", highlightthickness=1,
                                highlightbackground="#c9ced6")
        self.canvas.pack(padx=10, pady=6)

    def build_status(self):
        self.v_status = tk.StringVar()
        tk.Label(self, textvariable=self.v_status, bg=BG, fg=TEXT, anchor="w",
                 font=("TkFixedFont", 10)).pack(fill="x", padx=12)

    def build_log(self):
        frame = ttk.LabelFrame(self, text="Event log (from the C program)")
        frame.pack(fill="both", expand=True, padx=10, pady=4)
        self.log = tk.Text(frame, height=9, state="disabled", font=("TkFixedFont", 10), wrap="none")
        sb = ttk.Scrollbar(frame, command=self.log.yview)
        self.log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log.pack(fill="both", expand=True)
        self.log.tag_configure("put", foreground="#b86a10")
        self.log.tag_configure("get", foreground=GET_COLOR)
        self.log.tag_configure("wait", foreground=WAIT_COLOR)
        self.log.tag_configure("info", foreground=LINE)
        self.log.tag_configure("error", foreground=WAIT_COLOR, font=("TkFixedFont", 10, "bold"))

    def build_legend(self):
        bar = tk.Canvas(self, height=34, bg=BG, highlightthickness=0)
        bar.pack(fill="x", padx=10, pady=(0, 8))
        x = 10
        items = [
            ("circle", SLOT_EMPTY, None, "empty"),
            ("circle", SLOT_FULL, None, "full (number = item)"),
            ("circle", SLOT_FULL, PUT_COLOR, "just written"),
            ("circle", SLOT_EMPTY, GET_COLOR, "just read"),
            ("text", "zzz", None, "blocked (waiting)"),
            ("text", "▼", None, "in = next write"),
            ("text", "▲", None, "out = next read"),
        ]
        for kind, a, b, label in items:
            if kind == "circle":
                bar.create_oval(x, 9, x + 16, 25, fill=a, outline=b or LINE, width=3 if b else 1)
                x += 22
            else:
                bar.create_text(x + 8, 17, text=a, fill=WAIT_COLOR if a == "zzz" else TEXT,
                                font=("TkDefaultFont", 10, "bold"))
                x += 28
            t = bar.create_text(x, 17, text=label, anchor="w", fill=TEXT)
            x = bar.bbox(t)[2] + 14

    def layout(self):
        n = self.size
        per_row = min(n, 10)
        rows = 1 if n <= 10 else 2
        left, right = 230, 710
        spacing = (right - left) / per_row
        radius = max(14, min(26, spacing / 2 - 5))
        ys = [150] if rows == 1 else [105, 195]
        pos = []
        for i in range(n):
            r, c = divmod(i, per_row)
            pos.append((left + spacing * (c + 0.5), ys[r]))
        return pos, radius

    def redraw(self):
        c = self.canvas
        c.delete("static")
        pos, radius = self.layout()
        now = time.time()

        c.create_text(470, 18, text="Bounded buffer (circular queue)", fill=LINE,
                      font=("TkDefaultFont", 11, "bold"), tags="static")

        self.draw_actor(c, 25, 90, 175, 210, "Producer" if self.np == 1 else "Producers",
                        self.np, self.wait_p, PUT_COLOR)
        self.draw_actor(c, 765, 90, 915, 210, "Consumer" if self.nc == 1 else "Consumers",
                        self.nc, self.wait_c, GET_COLOR)

        c.create_line(175, 150, 215, 150, arrow="last", fill=LINE, width=2, tags="static")
        c.create_line(725, 150, 765, 150, arrow="last", fill=LINE, width=2, tags="static")

        for i, (x, y) in enumerate(pos):
            item = self.slots[i]
            fl = self.flash.get(i)
            outline, width = LINE, 1
            if fl and fl[1] > now:
                outline = PUT_COLOR if fl[0] == "put" else GET_COLOR
                width = 4
            c.create_oval(x - radius, y - radius, x + radius, y + radius,
                          fill=SLOT_FULL if item is not None else SLOT_EMPTY,
                          outline=outline, width=width, tags="static")
            if item is not None:
                c.create_text(x, y, text=str(item), fill="white",
                              font=("TkDefaultFont", 10, "bold"), tags="static")
            c.create_text(x, y + radius + 11, text=str(i), fill=LINE, tags="static")
            if i == self.next_in:
                c.create_text(x, y - radius - 12, text="▼ in", fill=PUT_COLOR,
                              font=("TkDefaultFont", 9, "bold"), tags="static")
            if i == self.next_out:
                c.create_text(x, y + radius + 28, text="▲ out", fill=GET_COLOR,
                              font=("TkDefaultFont", 9, "bold"), tags="static")

        empty = self.size - self.count
        c.create_text(470, 262, fill=TEXT, font=("TkFixedFont", 11), tags="static",
                      text="empty = size - count = %d        full = count = %d" %
                      (empty, self.count))
        self.v_status.set("produced: %d   consumed: %d   in buffer: %d/%d   times blocked: %d" %
                          (self.produced, self.consumed, self.count, self.size, self.waits_total))

    def draw_actor(self, c, x0, y0, x1, y1, title, n, waiting, color):
        blocked = len(waiting)
        outline = WAIT_COLOR if blocked else color
        c.create_rectangle(x0, y0, x1, y1, fill="#fafafa", outline=outline,
                           width=3 if blocked else 2, tags="static")
        c.create_text((x0 + x1) / 2, y0 + 20, text="%s (%d)" % (title, n),
                      font=("TkDefaultFont", 11, "bold"), fill=TEXT, tags="static")
        if n == 0:
            c.create_text((x0 + x1) / 2, (y0 + y1) / 2 + 10, text="none", fill=LINE, tags="static")
        elif blocked:
            c.create_text((x0 + x1) / 2, (y0 + y1) / 2 + 2, text="zzz", fill=WAIT_COLOR,
                          font=("TkDefaultFont", 22, "bold"), tags="static")
            c.create_text((x0 + x1) / 2, y1 - 22, text="%d of %d blocked" % (blocked, n),
                          fill=WAIT_COLOR, tags="static")
        elif self.proc is None:
            c.create_text((x0 + x1) / 2, (y0 + y1) / 2 + 10, text="idle", fill=LINE,
                          font=("TkDefaultFont", 12), tags="static")
        else:
            c.create_text((x0 + x1) / 2, (y0 + y1) / 2 + 10, text="running", fill="#2e7d4f",
                          font=("TkDefaultFont", 12), tags="static")

    def flash_active(self):
        now = time.time()
        return any(v[1] > now for v in self.flash.values())

    def fly(self, x0, y0, x1, y1, text, color, steps=14):
        r = 15
        oval = self.canvas.create_oval(x0 - r, y0 - r, x0 + r, y0 + r, fill=color, outline="", tags="token")
        label = self.canvas.create_text(x0, y0, text=text, fill="white",
                                        font=("TkDefaultFont", 9, "bold"), tags="token")

        def step(i):
            if i > steps:
                self.canvas.delete(oval)
                self.canvas.delete(label)
                return
            t = i / steps
            x = x0 + (x1 - x0) * t
            y = y0 + (y1 - y0) * t
            self.canvas.coords(oval, x - r, y - r, x + r, y + r)
            self.canvas.coords(label, x, y)
            self.after(16, step, i + 1)

        step(0)

    def log_line(self, text, tag):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n", tag)
        if int(self.log.index("end-1c").split(".")[0]) > 2000:
            self.log.delete("1.0", "500.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def set_msg(self, text, error=False):
        self.v_msg.set(text)
        self.lbl_msg.configure(fg=WAIT_COLOR if error else TEXT)

    def read_params(self):
        values = {}
        names = [("size", self.v_size, "Buffer size"), ("producers", self.v_prod, "Producers"),
                 ("consumers", self.v_cons, "Consumers"), ("delay", self.v_delay, "Delay"),
                 ("duration", self.v_dur, "Duration")]
        for key, var, label in names:
            lo, hi = LIMITS[key]
            text = var.get().strip()
            if not re.fullmatch(r"\d+", text) or not lo <= int(text) <= hi:
                self.set_msg("%s must be a whole number from %d to %d." % (label, lo, hi), True)
                return None
            values[key] = int(text)
        return values

    def start(self):
        if self.proc is not None:
            return
        if not os.path.exists(BINARY):
            self.set_msg("Program not found. Run 'make' in the project folder first.", True)
            return
        p = self.read_params()
        if p is None:
            return
        manual = self.v_mode.get() == "manual"
        cmd = [BINARY, "-s", str(p["size"]), "-d", str(p["delay"])]
        if manual:
            cmd.append("-m")
        cmd += [str(p["duration"]), str(p["producers"]), str(p["consumers"])]
        self.clear_log()
        self.reset_state(p["size"], p["producers"], p["consumers"])
        self.canvas.delete("token")
        self.redraw()
        try:
            self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, text=True, bufsize=1)
        except OSError as e:
            self.proc = None
            self.set_msg("Cannot start the program: %s" % e, True)
            return
        self.paused = False
        self.lines = queue.Queue()
        threading.Thread(target=self.reader, args=(self.proc, self.lines), daemon=True).start()
        self.set_msg("Running (manual: use the Produce and Consume buttons)." if manual
                     else "Running. Producers and consumers act at random times.")
        self.update_buttons()

    def reader(self, proc, q):
        for line in proc.stdout:
            q.put(line.rstrip("\n"))
        q.put(None)

    def send(self, cmd):
        if self.proc is None or self.v_mode.get() != "manual" or self.paused:
            return
        try:
            self.proc.stdin.write(cmd + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError):
            pass

    def toggle_pause(self):
        if self.proc is None or not hasattr(signal, "SIGSTOP"):
            return
        try:
            if self.paused:
                os.kill(self.proc.pid, signal.SIGCONT)
                self.paused = False
                self.set_msg("Resumed.")
            else:
                os.kill(self.proc.pid, signal.SIGSTOP)
                self.paused = True
                self.set_msg("Paused: all threads are stopped. Press Resume to continue.")
        except OSError:
            pass
        self.update_buttons()

    def kill_proc(self):
        if self.proc is None:
            return
        proc = self.proc
        self.proc = None
        try:
            if self.paused and hasattr(signal, "SIGCONT"):
                os.kill(proc.pid, signal.SIGCONT)
            proc.terminate()
            proc.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            try:
                proc.kill()
            except OSError:
                pass
        self.paused = False

    def stop(self):
        if self.proc is None:
            return
        self.kill_proc()
        self.wait_p.clear()
        self.wait_c.clear()
        self.set_msg("Stopped.")
        self.update_buttons()
        self.redraw()

    def reset(self):
        self.kill_proc()
        p = self.read_params()
        self.clear_log()
        if p is None:
            self.reset_state(5, 1, 1)
        else:
            self.reset_state(p["size"], p["producers"], p["consumers"])
            self.set_msg("Reset. Press Start to run again.")
        self.canvas.delete("token")
        self.update_buttons()
        self.redraw()

    def clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def update_buttons(self):
        running = self.proc is not None
        manual = self.v_mode.get() == "manual"
        self.b_start.configure(state="disabled" if running else "normal")
        self.b_stop.configure(state="normal" if running else "disabled")
        can_pause = running and hasattr(signal, "SIGSTOP")
        self.b_pause.configure(state="normal" if can_pause else "disabled",
                               text="Resume" if self.paused else "Pause")
        self.b_prod.configure(state="normal" if running and manual else "disabled")
        self.b_cons.configure(state="normal" if running and manual else "disabled")
        st = "disabled" if running else "normal"
        for e in self.entries:
            e.configure(state=st)
        self.rb_auto.configure(state=st)
        self.rb_manual.configure(state=st)

    def poll(self):
        changed = False
        try:
            while True:
                line = self.lines.get_nowait()
                if line is None:
                    if self.proc is not None:
                        try:
                            self.proc.wait(timeout=1)
                        except subprocess.TimeoutExpired:
                            pass
                        self.proc = None
                        self.wait_p.clear()
                        self.wait_c.clear()
                        self.update_buttons()
                        changed = True
                    continue
                self.handle(line)
                changed = True
        except queue.Empty:
            pass
        if changed or self.flash:
            now = time.time()
            self.flash = {k: v for k, v in self.flash.items() if v[1] > now - 0.05}
            self.redraw()
        self.after(30, self.poll)

    def handle(self, line):
        m = re.match(r"\[START\] size=(\d+) producers=(\d+) consumers=(\d+) delay=(\d+) mode=(\w+)", line)
        if m:
            self.reset_state(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            self.log_line("Started: buffer size %s, %s producer(s), %s consumer(s), mode %s" %
                          (m.group(1), m.group(2), m.group(3), m.group(5)), "info")
            return
        m = re.match(r"\[PUT\] producer=(\d+) item=(\d+) slot=(\d+) count=(\d+)", line)
        if m:
            pid, item, slot, count = (int(g) for g in m.groups())
            self.wait_p.discard(pid)
            if 0 <= slot < self.size:
                self.slots[slot] = item
                self.next_in = (slot + 1) % self.size
                self.flash[slot] = ("put", time.time() + 0.6)
                pos, _ = self.layout()
                self.fly(175, 150, pos[slot][0], pos[slot][1], str(item), PUT_COLOR)
            self.count = count
            self.produced += 1
            self.log_line("Producer %d put %d into slot %d   (items in buffer: %d)" %
                          (pid, item, slot, count), "put")
            return
        m = re.match(r"\[GET\] consumer=(\d+) item=(\d+) slot=(\d+) count=(\d+)", line)
        if m:
            cid, item, slot, count = (int(g) for g in m.groups())
            self.wait_c.discard(cid)
            if 0 <= slot < self.size:
                pos, _ = self.layout()
                self.fly(pos[slot][0], pos[slot][1], 765, 150, str(item), GET_COLOR)
                self.slots[slot] = None
                self.next_out = (slot + 1) % self.size
                self.flash[slot] = ("get", time.time() + 0.6)
            self.count = count
            self.consumed += 1
            self.log_line("Consumer %d took %d from slot %d   (items in buffer: %d)" %
                          (cid, item, slot, count), "get")
            return
        m = re.match(r"\[WAIT\] (producer|consumer)=(\d+)", line)
        if m:
            who, n = m.group(1), int(m.group(2))
            self.waits_total += 1
            if who == "producer":
                self.wait_p.add(n)
                self.log_line("Producer %d: buffer is full, waiting (sleeping)" % n, "wait")
            else:
                self.wait_c.add(n)
                self.log_line("Consumer %d: buffer is empty, waiting (sleeping)" % n, "wait")
            return
        if line.startswith("[END]"):
            self.log_line("Finished.", "info")
            self.set_msg("Finished. Press Start to run again or change the settings.")
            return
        if line.startswith("[ERROR]") or line.startswith("Error") or line.startswith("Usage"):
            self.log_line(line, "error")
            self.set_msg(line, True)
            return
        self.log_line(line, "info")

    def on_close(self):
        self.kill_proc()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
