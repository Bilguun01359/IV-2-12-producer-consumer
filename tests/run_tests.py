import os
import re
import signal
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PC = os.path.join(ROOT, "pc")

START_RE = re.compile(r"\[START\] size=(\d+) producers=(\d+) consumers=(\d+) delay=(\d+) "
                      r"mode=(\w+) mutex=(\w+) seed=(\d+)")
PUT_RE = re.compile(r"\[PUT\] producer=(\d+) item=(\d+) slot=(\d+) count=(-?\d+)")
GET_RE = re.compile(r"\[GET\] consumer=(\d+) item=(\d+) slot=(\d+) count=(-?\d+)")
WAIT_RE = re.compile(r"\[WAIT\] (producer|consumer)=(\d+)")
END_RE = re.compile(r"\[END\] produced=(\d+) consumed=(\d+) in_buffer=(-?\d+) invariant=(\w+)")


def run(args, stdin_text=None, timeout=60):
    p = subprocess.run([PC] + args, input=stdin_text, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def parse(out):
    info = {"size": None, "puts": [], "gets": [], "waits_p": 0, "waits_c": 0, "end": None,
            "counts_ok": True, "fifo_ok": True, "slots_ok": True, "mismatches": 0}
    queue = []
    expected = 0
    last_in = None
    last_out = None
    for line in out.splitlines():
        m = START_RE.match(line)
        if m:
            info["size"] = int(m.group(1))
            continue
        m = PUT_RE.match(line)
        if m:
            item, slot, count = int(m.group(2)), int(m.group(3)), int(m.group(4))
            info["puts"].append(item)
            queue.append((item, slot))
            expected += 1
            if count != expected:
                info["mismatches"] += 1
                expected = count
            if info["size"] and not 0 <= count <= info["size"]:
                info["counts_ok"] = False
            if last_in is not None and slot != (last_in + 1) % info["size"]:
                info["slots_ok"] = False
            last_in = slot
            continue
        m = GET_RE.match(line)
        if m:
            item, slot, count = int(m.group(2)), int(m.group(3)), int(m.group(4))
            info["gets"].append(item)
            expected -= 1
            if count != expected:
                info["mismatches"] += 1
                expected = count
            if not queue or queue.pop(0) != (item, slot):
                info["fifo_ok"] = False
            if info["size"] and not 0 <= count <= info["size"]:
                info["counts_ok"] = False
            if last_out is not None and slot != (last_out + 1) % info["size"]:
                info["slots_ok"] = False
            last_out = slot
            continue
        m = WAIT_RE.match(line)
        if m:
            if m.group(1) == "producer":
                info["waits_p"] += 1
            else:
                info["waits_c"] += 1
            continue
        m = END_RE.match(line)
        if m:
            info["end"] = (int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4))
    return info


def good_run(info):
    e = info["end"]
    return (e is not None and e[3] == "OK" and e[0] == len(info["puts"]) and e[1] == len(info["gets"])
            and e[0] - e[1] == e[2] and info["fifo_ok"] and info["slots_ok"]
            and info["counts_ok"] and info["mismatches"] == 0)


def summary(info):
    e = info["end"]
    return "produced %d, consumed %d, left %d" % (e[0], e[1], e[2]) if e else "no END line"


results = []


def record(tid, name, passed, detail):
    results.append((tid, name, passed, detail))
    print("%-4s %-46s %s   %s" % (tid, name, "PASS" if passed else "FAIL", detail))


def t_basic():
    rc, out, _ = run(["-d", "100", "3", "1", "1"])
    i = parse(out)
    record("T1", "1P+1C, 3 s, buffer 5 (invariant, FIFO, slots)", rc == 0 and good_run(i), summary(i))

    rc, out, _ = run(["-s", "3", "-d", "100", "3", "3", "1"])
    i = parse(out)
    record("T2", "3P+1C, buffer 3: buffer fills, producers wait",
           rc == 0 and good_run(i) and i["waits_p"] > 0, "%s, producer waits %d" % (summary(i), i["waits_p"]))

    rc, out, _ = run(["-s", "5", "-d", "100", "3", "1", "3"])
    i = parse(out)
    record("T3", "1P+3C, buffer 5: buffer empties, consumers wait",
           rc == 0 and good_run(i) and i["waits_c"] > 0, "%s, consumer waits %d" % (summary(i), i["waits_c"]))

    rc, out, _ = run(["-s", "4", "-d", "50", "3", "4", "4"])
    i = parse(out)
    record("T4", "4P+4C, buffer 4: invariant produced-consumed=left",
           rc == 0 and good_run(i), summary(i))


def t_boundary():
    rc, out, _ = run(["-s", "1", "-d", "50", "2", "2", "2"])
    i = parse(out)
    all_slot0 = all(re.search(r"slot=0 ", l + " ") for l in out.splitlines() if l.startswith(("[PUT]", "[GET]")))
    record("B1", "buffer size 1: slot is always 0", rc == 0 and good_run(i) and all_slot0, summary(i))

    rc, out, _ = run(["-s", "5", "-d", "10", "2", "8", "8"])
    i = parse(out)
    record("B2", "delay 10 ms, 8P+8C (heavy contention)", rc == 0 and good_run(i), summary(i))

    rc, out, _ = run(["-s", "20", "-d", "20", "2", "20", "20"])
    i = parse(out)
    record("B3", "max size 20, 20P+20C", rc == 0 and good_run(i), summary(i))

    rc, out, _ = run(["-s", "3", "-d", "50", "2", "2", "0"])
    i = parse(out)
    record("B4", "0 consumers: buffer fills and stays full",
           rc == 0 and len(i["gets"]) == 0 and len(i["puts"]) == 3 and i["waits_p"] > 0 and good_run(i),
           summary(i))

    rc, out, _ = run(["-s", "3", "-d", "50", "2", "0", "2"])
    i = parse(out)
    record("B5", "0 producers: nothing to consume, consumers wait",
           rc == 0 and len(i["puts"]) == 0 and len(i["gets"]) == 0 and i["waits_c"] > 0 and good_run(i),
           summary(i))

    rc, out, _ = run(["0", "1", "1"])
    i = parse(out)
    record("B6", "run time 0 s: ends at once with an END line", rc == 0 and i["end"] is not None, summary(i))


def t_errors():
    cases = [
        ("E1", "missing arguments", ["3", "1"], "Usage"),
        ("E2", "negative run time", ["--", "-1", "1", "1"], "sleep_seconds must be"),
        ("E3", "producers is not a number", ["3", "abc", "1"], "producers must be"),
        ("E4", "buffer size 0", ["-s", "0", "3", "1", "1"], "buffer size must be"),
        ("E5", "buffer size 21 (too big)", ["-s", "21", "3", "1", "1"], "buffer size must be"),
        ("E6", "21 producers (too many)", ["3", "21", "1"], "producers must be"),
        ("E7", "delay 5 (too small)", ["-d", "5", "3", "1", "1"], "delay must be"),
        ("E8", "unknown option", ["-z", "3", "1", "1"], "Usage"),
        ("E9", "seed 0 (invalid)", ["-r", "0", "3", "1", "1"], "seed must be"),
    ]
    for tid, name, args, text in cases:
        rc, out, err = run(args)
        record(tid, "bad input: " + name, rc == 1 and text in err and out == "", "exit %d, %s" % (rc, err.splitlines()[0] if err else ""))


def t_signal():
    p = subprocess.Popen([PC, "60", "2", "2"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(1.0)
    t0 = time.time()
    p.send_signal(signal.SIGTERM)
    try:
        out, _ = p.communicate(timeout=5)
        took = time.time() - t0
        i = parse(out)
        record("S1", "SIGTERM stops a 60 s run quickly, prints END",
               p.returncode == 0 and took < 2 and i["end"] is not None and i["end"][3] == "OK",
               "stopped in %.2f s, %s" % (took, summary(i)))
    except subprocess.TimeoutExpired:
        p.kill()
        record("S1", "SIGTERM stops a 60 s run quickly, prints END", False, "did not stop")


def t_manual():
    p = subprocess.Popen([PC, "-m", "-s", "2", "0", "1", "1"], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for cmd in ("P", "P", "P", "C"):
        p.stdin.write(cmd + "\n")
        p.stdin.flush()
        time.sleep(0.3)
    p.stdin.write("Q\n")
    p.stdin.flush()
    out, _ = p.communicate(timeout=10)
    i = parse(out)
    record("M1", "manual: P P P C with buffer 2 (3rd put waits for C)",
           p.returncode == 0 and len(i["puts"]) == 3 and len(i["gets"]) == 1 and i["waits_p"] == 1 and good_run(i),
           summary(i) + ", producer waits %d" % i["waits_p"])


def t_seed():
    rc1, out1, _ = run(["-r", "42", "-d", "100", "2", "1", "1"])
    rc2, out2, _ = run(["-r", "42", "-d", "100", "2", "1", "1"])
    a, b = parse(out1)["puts"], parse(out2)["puts"]
    n = min(len(a), len(b), 8)
    record("R1", "same seed gives the same first 8 items",
           rc1 == 0 and rc2 == 0 and n >= 5 and a[:n] == b[:n], "%s" % a[:n])
    rc3, out3, _ = run(["-r", "43", "-d", "100", "2", "1", "1"])
    c = parse(out3)["puts"]
    record("R2", "different seed gives different items", rc3 == 0 and c[:5] != a[:5], "%s" % c[:5])


def t_race():
    rc, out, _ = run(["-s", "5", "-d", "10", "3", "8", "8"])
    i = parse(out)
    record("X1", "with mutex: 8P+8C, no count mismatch at all",
           rc == 0 and good_run(i) and i["mismatches"] == 0, "%s, mismatches %d" % (summary(i), i["mismatches"]))
    total_mismatch = 0
    fails = 0
    runs = 5
    for _ in range(runs):
        rc, out, _ = run(["-n", "-s", "5", "-d", "10", "2", "8", "8"])
        i = parse(out)
        total_mismatch += i["mismatches"]
        if i["end"] and i["end"][3] == "FAIL":
            fails += 1
    record("X2", "no mutex: race shows up as count mismatches (5 runs)", total_mismatch > 0,
           "mismatches %d in %d runs, invariant FAIL in %d of %d runs" % (total_mismatch, runs, fails, runs))


def main():
    if not os.path.exists(PC):
        print("Program not found. Run 'make' first.")
        return 2
    for group in (t_basic, t_boundary, t_errors, t_signal, t_manual, t_seed, t_race):
        group()
    passed = sum(1 for r in results if r[2])
    print("\n%d/%d passed" % (passed, len(results)))
    if len(sys.argv) > 2 and sys.argv[1] == "--md":
        with open(sys.argv[2], "w") as f:
            f.write("| ID | Test | Result | Details |\n|---|---|---|---|\n")
            for tid, name, ok, detail in results:
                f.write("| %s | %s | %s | %s |\n" % (tid, name, "PASS" if ok else "FAIL", detail))
            f.write("\n%d/%d passed\n" % (passed, len(results)))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
