# NetDevOps – Phase 3: Network monitoring (Runnning on Ubuntu host)

```
EVE-NG (lab)                                  Ubuntu host
 Devices ── interface mgmt ── OOB-MNG ──> ├─ netinfra   : NTP 123 / Syslog 514 / TFTP 69  (network_mode: host)
                                               ├─ snmp-exporter :9116 ──SNMP──> devices
                                               ├─ prometheus    :9090
                                               └─ grafana       :3000
```
"IP-Host" is used for all devices

## 1. Check host before running
```bash
docker --version && docker compose version
# Cổng 69/123/514 UDP are free
sudo ss -lunp | grep -E ':(69|123|514)\b'
```

## 2. Run
```bash
cd monitoring
cp .env.example .env          # Change Grafana password
docker compose up -d --build
docker compose ps             # 4 container: netinfra, prometheus, snmp-exporter, grafana
docker compose logs netinfra  # See "chronyd / rsyslogd / in.tftpd run"
```
Test right away on host:
```bash
sudo ss -lunp | grep -E ':(69|123|514)\b'                 
logger -n 127.0.0.1 -P 514 -d "test syslog"               
sudo apt install ntpdate && ntpdate -q 127.0.0.1        
```

## 3. Configuring <IP_HOST> on Cisco devices
```
service timestamps log datetime msec
clock timezone ICT 7 0
!
ntp server <IP_HOST> prefer
!
logging host <IP_HOST>
logging trap informational
logging on
!
ip access-list standard SNMP-ALLOW
 permit host <IP_HOST>
snmp-server community netlab-ro RO SNMP-ALLOW
snmp-server location VCB-LAB
```
Examine:
```
show ntp associations                               
configure terminal / end                            
copy running-config tftp://<IP_HOST>/HN-GW.cfg      
```

## 4. Examine and Monitoring
```bash
snmpwalk -v2c -c netlab-ro <IP_DEVICES> 1.3.6.1.2.1.1.3        # apt install snmp
curl -s "http://localhost:9116/snmp?target=<IP_DEVICES>&module=cisco_lab&auth=lab_v2" | head -30
# Prometheus: http://localhost:9090/targets -> job snmp phải UP
```
Grafana: http://localhost:3000 (admin / password in `.env`), datasource Prometheus is ready. PromQL:
- Băng thông vào (bps): `rate(ifHCInOctets{device="HN-GW"}[2m]) * 8`
- CPU 5 phút: `cpmCPUTotal5minRev`
- Cổng down: `ifOperStatus{ifDescr!~"Null.*"} != 1`

