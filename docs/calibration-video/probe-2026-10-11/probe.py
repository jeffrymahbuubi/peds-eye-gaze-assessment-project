"""P1-P3 calibration probe against the running Gazepoint Control (127.0.0.1:4242).

One reader thread reads the socket in a single loop and timestamps every
line with perf_counter_ns; the main thread only sends. Two calibrations:
  run A: original/device-default DELAY+TIMEOUT, window hidden, points TL,BR,TR,BL,C
  run B: DELAY 1.8 / TIMEOUT 0.3, same points
Originals of CALIBRATE_SHOW / DELAY / TIMEOUT are restored at the end.
"""
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time

HOST, PORT = "127.0.0.1", 4242
HERE = os.path.dirname(os.path.abspath(__file__))
LOG = open(os.path.join(HERE, "raw_log.txt"), "w", encoding="utf-8")
T0 = time.perf_counter_ns()
lines = []  # (t_ms, direction, text)
lock = threading.Lock()
stop = threading.Event()

POINTS = [("TL", 0.10, 0.10), ("BR", 0.90, 0.90), ("TR", 0.90, 0.10),
          ("BL", 0.10, 0.90), ("C", 0.50, 0.50)]


def now_ms():
    return (time.perf_counter_ns() - T0) / 1e6


def log(direction, text):
    t = now_ms()
    with lock:
        lines.append((t, direction, text))
        LOG.write(f"{t:12.3f} {direction} {text}\n")
        LOG.flush()
    return t


def parse(line):
    m = re.match(r"<(\w+)\s+(.*?)/?>\s*$", line)
    if not m:
        return None, {}
    return m.group(1), dict(re.findall(r'(\w+)="([^"]*)"', m.group(2)))


def reader(sock):
    buf = b""
    while not stop.is_set():
        try:
            data = sock.recv(65536)
        except socket.timeout:
            continue
        except OSError as e:
            log("!!", f"recv error {e!r}")
            return
        if not data:
            log("!!", "socket closed by Control")
            return
        buf += data
        while b"\r\n" in buf:
            ln, buf = buf.split(b"\r\n", 1)
            if ln.strip():
                log("<<", ln.decode("ascii", "replace"))


def send(sock, msg):
    t = log(">>", msg)
    sock.sendall((msg + "\r\n").encode("ascii"))
    return t


def wait_for(pred, since_idx, timeout_s):
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        with lock:
            for t, d, txt in lines[since_idx:]:
                if d == "<<" and pred(txt):
                    return t, txt
        time.sleep(0.01)
    return None, None


def get(sock, ident, timeout_s=3.0):
    idx = len(lines)
    send(sock, f'<GET ID="{ident}" />')
    t, txt = wait_for(lambda s: f'ID="{ident}"' in s and s.startswith("<ACK"), idx, timeout_s)
    return parse(txt)[1] if txt else None


def screenshot(path):
    ps = (
        "Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
        "$b=[System.Windows.Forms.SystemInformation]::VirtualScreen;"
        "$bmp=New-Object System.Drawing.Bitmap $b.Width,$b.Height;"
        "$g=[System.Drawing.Graphics]::FromImage($bmp);"
        "$g.CopyFromScreen($b.Left,$b.Top,0,0,$bmp.Size);"
        f"$bmp.Save('{path}');"
    )
    return subprocess.Popen(["powershell", "-NoProfile", "-Command", ps])


def run_calibration(sock, tag, delay, timeout, shot_at_s=None):
    log("--", f"=== calibration {tag}: DELAY={delay} TIMEOUT={timeout} ===")
    if delay is not None:
        send(sock, f'<SET ID="CALIBRATE_DELAY" VALUE="{delay}" />')
    if timeout is not None:
        send(sock, f'<SET ID="CALIBRATE_TIMEOUT" VALUE="{timeout}" />')
    send(sock, '<SET ID="CALIBRATE_SHOW" STATE="0" />')
    send(sock, '<SET ID="CALIBRATE_CLEAR" />')
    for name, x, y in POINTS:
        send(sock, f'<SET ID="CALIBRATE_ADDPOINT" X="{x}" Y="{y}" />')
    time.sleep(0.3)
    d = get(sock, "CALIBRATE_DELAY")
    t = get(sock, "CALIBRATE_TIMEOUT")
    log("--", f"{tag} effective DELAY={d} TIMEOUT={t}")
    idx = len(lines)
    t_start = send(sock, '<SET ID="CALIBRATE_START" STATE="1" />')
    shot = None
    if shot_at_s is not None:
        time.sleep(shot_at_s)
        shot = screenshot(os.path.join(HERE, f"screen_{tag}_mid.png"))
        log("--", f"screenshot {tag} taken")
    per_pt = (float(d.get("VALUE", 2)) if d else 2) + (float(t.get("VALUE", 2)) if t else 2)
    tr, txt = wait_for(lambda s: 'ID="CALIB_RESULT"' in s, idx, 5 * per_pt + 20)
    if shot:
        shot.wait(20)
    if tr is None:
        log("!!", f"{tag}: no CALIB_RESULT within timeout; sending CALIBRATE_START STATE=0")
        send(sock, '<SET ID="CALIBRATE_START" STATE="0" />')
    time.sleep(1.0)
    summ = get(sock, "CALIBRATE_RESULT_SUMMARY")
    log("--", f"{tag} summary after: {summ}")
    with lock:
        seg = [(tt, txt2) for tt, dd, txt2 in lines[idx:] if dd == "<<"]
    return {"tag": tag, "t_start": t_start, "delay": d, "timeout": t,
            "records": seg, "summary": summ, "got_result": tr is not None}


def analyse(run):
    out = {"tag": run["tag"], "delay": run["delay"], "timeout": run["timeout"],
           "got_result": run["got_result"], "summary": run["summary"]}
    starts, results, calres = [], [], None
    for t, txt in run["records"]:
        kind, a = parse(txt)
        if kind != "CAL":
            continue
        if a.get("ID") == "CALIB_START_PT":
            starts.append((t, a))
        elif a.get("ID") == "CALIB_RESULT_PT":
            results.append((t, a))
        elif a.get("ID") == "CALIB_RESULT":
            calres = (t, a)
    out["start_pts"] = [{"t": round(t - run["t_start"], 1), **a} for t, a in starts]
    out["result_pts"] = [{"t": round(t - run["t_start"], 1), **a} for t, a in results]
    out["calib_result"] = ({"t": round(calres[0] - run["t_start"], 1), **calres[1]}
                           if calres else None)
    pairs = []
    for t, a in starts:
        r = next(((tr, ar) for tr, ar in results if ar.get("PT") == a.get("PT") and tr >= t), None)
        if r:
            pairs.append({"PT": a.get("PT"), "start_to_result_ms": round(r[0] - t, 1)})
    out["per_point"] = pairs
    if starts:
        out["start_to_first_START_PT_ms"] = round(starts[0][0] - run["t_start"], 1)
    if results and calres:
        out["last_RESULT_PT_to_CALIB_RESULT_ms"] = round(calres[0] - results[-1][0], 1)
    # gaps between consecutive RESULT_PT and next START_PT
    gaps = []
    for (tr, ar) in results:
        nxt = next((ts for ts, a in starts if ts > tr), None)
        if nxt is not None:
            gaps.append(round(nxt - tr, 1))
    out["result_to_next_start_ms"] = gaps
    return out


def main():
    sock = socket.create_connection((HOST, PORT), timeout=5)
    sock.settimeout(0.2)
    th = threading.Thread(target=reader, args=(sock,), daemon=True)
    th.start()
    time.sleep(0.5)  # drain whatever Control sends on connect
    orig = {k: get(sock, k) for k in
            ("CALIBRATE_SHOW", "CALIBRATE_DELAY", "CALIBRATE_TIMEOUT", "CALIBRATE_RESULT_SUMMARY")}
    log("--", f"originals: {orig}")
    if orig["CALIBRATE_SHOW"] is None:
        log("!!", "Control did not answer GET; aborting")
        stop.set()
        return
    runs = []
    try:
        runs.append(run_calibration(sock, "A_default", None, None, shot_at_s=2.0))
        runs.append(run_calibration(sock, "B_fast", 1.8, 0.3, shot_at_s=2.5))
    finally:
        # restore
        send(sock, '<SET ID="CALIBRATE_START" STATE="0" />')
        if orig.get("CALIBRATE_DELAY"):
            send(sock, f'<SET ID="CALIBRATE_DELAY" VALUE="{orig["CALIBRATE_DELAY"]["VALUE"]}" />')
        if orig.get("CALIBRATE_TIMEOUT"):
            send(sock, f'<SET ID="CALIBRATE_TIMEOUT" VALUE="{orig["CALIBRATE_TIMEOUT"]["VALUE"]}" />')
        if orig.get("CALIBRATE_SHOW"):
            send(sock, f'<SET ID="CALIBRATE_SHOW" STATE="{orig["CALIBRATE_SHOW"]["STATE"]}" />')
        time.sleep(0.5)
        after = {k: get(sock, k) for k in ("CALIBRATE_SHOW", "CALIBRATE_DELAY", "CALIBRATE_TIMEOUT")}
        log("--", f"after restore: {after}")
        stop.set()
        th.join(2)
        sock.close()
    res = {"originals": orig, "after_restore": after, "runs": [analyse(r) for r in runs]}
    with open(os.path.join(HERE, "analysis.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
