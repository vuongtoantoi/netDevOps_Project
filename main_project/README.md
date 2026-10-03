# config_builder.py
config_builder.py
------------------
Doc file YAML (routers: FPT_Telecom/HCM_GW/HN_GW va switches: HCM-SW/HN-DMZ/
FPT-SW/OFFICE-ACC1/OFFICE-ACC2/HN-OFFICE/HN-DATACENTER), chuan hoa du lieu, va
sinh ra danh sach cau lenh Cisco IOS (config mode) cho tung thiet bi.

Module nay KHONG dung pexpect / khong ket noi thiet bi that - chi xu ly du
lieu + sinh lenh, de co the test doc lap (dry-run) truoc khi day len switch/
router that qua deploy_pexpect.py.

Cach dung nhanh:
    python3 config_builder.py devices.yaml --dry-run

# deploy_pexpect.py
deploy_pexpect.py
------------------
Day cau hinh (sinh boi config_builder.py) len tung thiet bi Cisco IOS qua
SSH, dung pexpect - KHONG dung netmiko/paramiko.

Vi sao netmiko/paramiko hay "khong dung duoc" voi lab GNS3/EVE-NG/Packet
Tracer:
Netmiko chay tren Paramiko. Cac ban Paramiko/OpenSSH gan day mac dinh TAT
nhieu thuat toan SSH "cu" (vd key-exchange diffie-hellman-group1-sha1,
host-key ssh-rsa, mot so cipher CBC...) vi ly do bao mat. Cac IOS image hay
dung trong lab (c3725/c3745/c7200/mot so IOSv doi cu) lai CHI ho tro dung
nhung thuat toan cu nay -> Paramiko/Netmiko bao loi dang "Unable to
negotiate kex algorithm", "Error reading SSH protocol banner", hoac tuong tu
nhu sai mat khau du that ra khong phai. OpenSSH client (lenh `ssh` co san
tren Linux/Mac, hoac Git-Bash/WSL tren Windows) van con cho phep BAT LAI cac
thuat toan cu do qua option `-o`, nen pexpect + spawn lenh `ssh` he thong
thuong "chay duoc" ngay ca khi Paramiko/Netmiko bo tay.

Neu ssh van khong duoc (vi du IOS qua cu, chi ho tro telnet), doi cach spawn
sang: pexpect.spawn(f"telnet {host} {port}") va bo cac buoc "yes/known host"
o duoi.

Cach dung:
    pip install pexpect pyyaml --break-system-packages

    # 1) Luon kiem tra lenh sinh ra truoc (khong dung toi thiet bi that):
    python3 deploy_pexpect.py devices.yaml --dry-run

    # 2) Day that len TAT CA thiet bi trong file:
    python3 deploy_pexpect.py devices.yaml

    # 3) Chi day 1-2 thiet bi cu the (test truoc khi day ca lab):
    python3 deploy_pexpect.py devices.yaml --only HCM-SW HN-DMZ

    # 4) Gop nhieu file (neu ban tach lai thanh 2 file switches/routers):
    python3 deploy_pexpect.py devices_switches.yaml devices_routers.yaml

# nornir_tasks.py
nornir_tasks.py
----------------
Custom Nornir task: day cau hinh qua pexpect - KHONG dung nornir_netmiko hay
nornir_napalm, vi 2 plugin do chay tren Netmiko/Paramiko va nhieu kha nang
dinh dung van de crypto SSH cu giong nhu o tuan 4.

Task tu tra cuu du lieu cau hinh cua host (trong device_lookup, lay tu chinh
devices_corrected.yaml) roi goi lai dung cac ham da viet + test o tuan 4:
config_builder.build_commands_for_device() va deploy_pexpect.connect/
push_commands/save_and_backup - khong viet lai logic ket noi.

# nornir_push.py
nornir_push.py
---------------
Tuan 5: chay task push_config_pexpect DONG THOI (song song, nhieu thread)
len TAT CA thiet bi khai bao trong inventory/ - thay cho vong lap tuan tu
device-by-device trong deploy_pexpect.py (tuan 4).

Chuan bi (1 lan):
    python3 generate_nornir_inventory.py devices_corrected.yaml -o inventory/

Chay:
    python3 nornir_push.py devices_corrected.yaml --dry-run
    python3 nornir_push.py devices_corrected.yaml --group switches
    python3 nornir_push.py devices_corrected.yaml            # tat ca, song song


# NOTE: Phần gitignore, .env.example, .env
Như bạn thấy trong folder này có phần gitignore và .env để  có thể giấu mật khẩu khỏi thuật toán của Github, tuy nhiên trong source code của tôi vẫn giwux nguyên mật khẩu vì tôi muốn bạn hiểu rõ phần code của tôi có những gì, và nó phục vụ gì. Thay vì phải thêm một phần code để script python đọc mật khẩu từ .env mà bạn phải tìm nó trong khi thắc mắc tại sao devices lại không có mật khẩu, tôi vẫn muốn giữ lại code như lúc đầu tôi làm!