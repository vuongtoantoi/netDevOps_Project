import argparse
import os

import pexpect

import config_builder as cb

SSH_LEGACY_OPTS = (
    "-o StrictHostKeyChecking=no "
    "-o UserKnownHostsFile=/dev/null "
    "-o KexAlgorithms=+diffie-hellman-group1-sha1,diffie-hellman-group14-sha1 "
    "-o HostKeyAlgorithms=+ssh-rsa "
    "-o PubkeyAcceptedAlgorithms=+ssh-rsa "
    "-o Ciphers=+aes128-cbc,3des-cbc"
)

LOGIN_TIMEOUT = 20
CMD_TIMEOUT = 15
PROMPT = r"[>#]\s*$"       
PRIV_PROMPT = r"#\s*$"     


def connect(device, log_dir):
    """Mo ket noi SSH bang pexpect, dang nhap, vao enable, tat phan trang."""
    name = device["name"]
    host = device["host"]
    port = device.get("port", 22)
    username = device["username"]
    password = device["password"]

    os.makedirs(log_dir, exist_ok=True)
    cmd = f"ssh {SSH_LEGACY_OPTS} -p {port} {username}@{host}"
    child = pexpect.spawn(cmd, timeout=LOGIN_TIMEOUT, encoding="utf-8")
    child.logfile = open(os.path.join(log_dir, f"{name}.log"), "w")

    i = child.expect(
        [
            r"(?i)are you sure you want to continue connecting",
            r"(?i)password:",
            r"(?i)connection refused",
            r"(?i)no route to host",
            pexpect.TIMEOUT,
            pexpect.EOF,
        ]
    )
    if i == 0:
        child.sendline("yes")
        i = child.expect([r"(?i)password:", pexpect.TIMEOUT, pexpect.EOF])
        if i != 0:
            raise RuntimeError("khong thay prompt password sau khi accept host key")
    elif i in (2, 3):
        raise RuntimeError(f"khong ket noi duoc toi {host}:{port} (tu choi/khong co route)")
    elif i in (4, 5):
        raise RuntimeError("timeout/EOF truoc khi thay prompt password")

    child.sendline(password)
    i = child.expect([PROMPT, r"(?i)password:", pexpect.TIMEOUT, pexpect.EOF])
    if i == 1:
        raise RuntimeError("sai username/password khi dang nhap SSH")
    if i in (2, 3):
        raise RuntimeError("timeout/EOF sau khi gui password dang nhap")

    
    if child.after.strip().endswith(">"):
        child.sendline("enable")
        i = child.expect([r"(?i)password:", PRIV_PROMPT, pexpect.TIMEOUT, pexpect.EOF])
        if i == 0:
            child.sendline(device.get("enable_password", password))
            i = child.expect([PRIV_PROMPT, pexpect.TIMEOUT, pexpect.EOF])
            if i != 0:
                raise RuntimeError("sai enable password hoac timeout khi vao enable mode")
        elif i != 1:
            raise RuntimeError("timeout/EOF khi vao enable mode")

    child.sendline("terminal length 0")   
    child.expect(PRIV_PROMPT)
    return child


def push_commands(child, commands):
    """Vao configure terminal, gui tung dong lenh, roi 'end'."""
    child.sendline("configure terminal")
    child.expect(r"\(config\)#\s*$")

    rejected = []
    for line in commands:
        child.sendline(line)
        idx = child.expect(
            [PRIV_PROMPT, r"(?i)% ?invalid", r"(?i)% ?incomplete", pexpect.TIMEOUT],
            timeout=CMD_TIMEOUT,
        )
        if idx in (1, 2):
            rejected.append(line)
        elif idx == 3:
            rejected.append(f"{line}  (TIMEOUT - khong thay phan hoi)")

    child.sendline("end")
    child.expect(PRIV_PROMPT)
    return rejected


def save_and_backup(child, device):
    """write memory, roi copy running-config qua TFTP neu YAML co bat backup_config."""
    child.sendline("write memory")
    child.expect([r"(?i)\[ok\]", PRIV_PROMPT], timeout=30)

    for line in cb.build_backup_commands(device):
        child.sendline(line)
        for _ in range(4):  
            idx = child.expect(
                [
                    r"(?i)destination filename",
                    r"(?i)address or name of remote host",
                    PRIV_PROMPT,
                    pexpect.TIMEOUT,
                ],
                timeout=30,
            )
            if idx in (0, 1):
                child.sendline("")  
                continue
            break


def deploy_one(device, log_dir, dry_run=False):
    name = device["name"]
    print(f"\n=== {name} ({device.get('host')}) ===")
    try:
        commands = cb.build_commands_for_device(device)
    except cb.DeviceConfigError as e:
        print(f"  !! BO QUA - loi du lieu YAML: {e}")
        return False

    if dry_run:
        print(f"  (dry-run) se gui {len(commands)} dong lenh, backup: "
              f"{cb.build_backup_commands(device) or '(khong bat)'}")
        return True

    try:
        child = connect(device, log_dir)
        rejected = push_commands(child, commands)
        save_and_backup(child, device)
        child.sendline("exit")
        child.close()
        if rejected:
            print(f"  !! DAY XONG NHUNG CO {len(rejected)} LENH BI TU CHOI:")
            for r in rejected:
                print(f"       - {r}")
            print(f"     (xem chi tiet trong {log_dir}/{name}.log)")
            return False
        print(f"  OK - da day {len(commands)} dong lenh. Log: {log_dir}/{name}.log")
        return True
    except Exception as e:  
        print(f"  !! LOI KHI DAY CAU HINH: {type(e).__name__}: {e}")
        print(f"     (xem chi tiet trong {log_dir}/{name}.log)")
        return False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", help="1 hoac nhieu file YAML thiet bi (vd devices.yaml)")
    ap.add_argument("--only", nargs="*", help="chi xu ly cac thiet bi co ten nay (vd --only HCM-SW HN-DMZ)")
    ap.add_argument("--dry-run", action="store_true", help="chi in ra lenh se gui, KHONG ket noi thiet bi that")
    ap.add_argument("--log-dir", default="logs", help="thu muc luu log toan bo phien pexpect (mac dinh: logs/)")
    args = ap.parse_args()

    devices = cb.load_all_devices(args.files)
    if args.only:
        devices = [d for d in devices if d["name"] in args.only]
    if not devices:
        print("Khong tim thay thiet bi nao khop dieu kien.")
        return

    ok, fail = [], []
    for d in devices:
        success = deploy_one(d, args.log_dir, dry_run=args.dry_run)
        (ok if success else fail).append(d["name"])

    print(f"\n\nTONG KET: {len(ok)} OK {ok}\n           {len(fail)} LOI {fail}")


if __name__ == "__main__":
    main()
