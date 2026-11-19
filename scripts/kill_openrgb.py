import ctypes, subprocess, time, socket
from ctypes import wintypes
k32 = ctypes.WinDLL('kernel32', use_last_error=True)
PROCESS_TERMINATE = 0x0001
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
pids = set()
r = subprocess.run(['netstat','-ano','-p','TCP'],capture_output=True,text=True,encoding='gbk',errors='replace')
for line in r.stdout.splitlines():
    if ":6742" in line and "LISTENING" in line:
        pids.add(int(line.split()[-1]))
print("listener pids:", pids)
for pid in pids:
    h = k32.OpenProcess(PROCESS_TERMINATE | PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if h:
        ok = k32.TerminateProcess(h, 1); k32.CloseHandle(h)
        print("terminate", pid, ok)
    else:
        print("cannot open", pid, ctypes.get_last_error())
time.sleep(2)
s=socket.socket(); s.settimeout(1)
try:
    s.connect(("127.0.0.1",6742)); print("PORT STILL OPEN")
except Exception:
    print("port closed OK")
