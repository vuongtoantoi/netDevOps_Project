import re
import sys

SYSLOG_LEVEL_ALIASES = {
    "info": "informational",  
}

class DeviceConfigError(ValueError):
    def __init__(self, device_name, message):
        super().__init__(f"[{device_name}] {message}")
        self.device_name = device_name

def normalize_vlans(device):
    name = device.get("name", "?")
    raw = device.get("vlans")
    if raw is None:
        return {}

    if isinstance(raw, dict):
        if any(isinstance(k, int) and k < 0 for k in raw):
            raise DeviceConfigError(
                name,
                "khoa 'vlans' bi am (vd -10, -110,...) - dau hieu thieu dau cach "
                "sau dau '-' trong YAML (phai la '- 10: Ten' chu khong phai "
                "'-10: Ten'). Sua YAML truoc khi chay tiep.",
            )
       
        return {int(k): v for k, v in raw.items()}

    if isinstance(raw, list):
        out = {}
        for item in raw:
            if not isinstance(item, dict) or len(item) != 1:
                raise DeviceConfigError(name, f"phan tu 'vlans' khong hop le: {item!r}")
            (vid, vname), = item.items()
            out[int(vid)] = vname
        return out

    raise DeviceConfigError(name, f"kieu du lieu 'vlans' khong nhan dien duoc: {type(raw)}")


def normalize_interfaces(device):
    name = device.get("name", "?")
    raw = device.get("interfaces")
    if raw is None:
        return {}

    if isinstance(raw, dict):
        out = {}
        for iface, props in raw.items():
            if isinstance(props, list):
                raise DeviceConfigError(
                    name,
                    f"khoa '{iface}' trong 'interfaces' la 1 list, khong phai thuoc "
                    f"tinh interface - rat co the la 1 khoi khac (vd 'tunnel:') bi "
                    f"thut le nham vao trong 'interfaces'. Dua '{iface}:' ra thanh "
                    f"1 khoa rieng, ngang cap voi 'interfaces:'.",
                )
            if not isinstance(props, dict):
                raise DeviceConfigError(name, f"interface '{iface}' co gia tri khong hop le: {props!r}")
            out[iface] = props
        return out

    if isinstance(raw, list):
        out = {}
        for item in raw:
            if not isinstance(item, dict) or len(item) < 1:
                raise DeviceConfigError(name, f"phan tu 'interfaces' khong hop le: {item!r}")
            if len(item) == 1:
                (iface, props), = item.items()
                if props is None:
                    raise DeviceConfigError(
                        name,
                        f"interface '{iface}' co gia tri None - thuong la do thut le "
                        f"sai (cac thuoc tinh con phai thut SAU vao trong so voi "
                        f"'{iface}:', khong duoc de ngang hang).",
                    )
                if not isinstance(props, dict):
                    raise DeviceConfigError(name, f"interface '{iface}' co gia tri khong hop le: {props!r}")
                out[iface] = props
                continue
            none_keys = [k for k, v in item.items() if v is None]
            if none_keys:
                iface = none_keys[0]
                props = {k: v for k, v in item.items() if k != iface}
                raise DeviceConfigError(
                    name,
                    f"interface '{iface}': cac thuoc tinh {list(props.keys())} dang "
                    f"thut le NGANG BANG voi '{iface}:' thay vi SAU HON, nen bi hieu "
                    f"la cac key cung cap (roi) chu khong phai thuoc tinh con. Sua: "
                    f"thut sau them 2 space cho {list(props.keys())} vao trong so voi "
                    f"dong '- {iface}:'.",
                )
            raise DeviceConfigError(name, f"phan tu 'interfaces' co nhieu key la (khong ro y dinh): {item!r}")
        return out

    raise DeviceConfigError(name, f"'interfaces' phai la list hoac dict, dang gap {type(raw)}")

def as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]

def get_tftp_server(tftp_cfg):
    """File routers dung 'server' (so it), file switches dung 'servers'."""
    if not tftp_cfg:
        return None
    return tftp_cfg.get("server") or tftp_cfg.get("servers")


def parse_interface_range(range_key):
    m = re.match(r"^([A-Za-z]+\d+/)(\d+)-(\d+)$", range_key)
    if not m:
        raise ValueError(f"Khong parse duoc interface-range: {range_key!r}")
    prefix, start, end = m.groups()
    return f"{prefix}{start}", end


def is_svi_name(iface_name):
    return re.match(r"^[Vv]lan\d+$", iface_name) is not None

def _match_clause(addr, wildcard):
    if addr is None or str(addr).lower() == "any":
        return "any"
    if wildcard:
        return f"{addr} {wildcard}"
    return f"host {addr}"


def build_acl_lines(acl):
    name = acl["name"]
    acl_type = acl.get("type", "standard")
    lines = []
    if acl_type == "standard":
        lines.append(f"ip access-list standard {name}")
        for e in acl.get("entries", []):
            src = _match_clause(e.get("source"), e.get("wildcard"))
            lines.append(f" {e.get('sequence', '')} {e['action']} {src}".rstrip())
    else:
        lines.append(f"ip access-list extended {name}")
        for e in acl.get("entries", []):
            proto = e.get("protocol", "ip")
            src = _match_clause(e.get("source"), e.get("wildcard"))
            dst = _match_clause(e.get("destination"), e.get("destination_wildcard"))
            port = f" eq {e['destination_port']}" if e.get("destination_port") else ""
            lines.append(
                f" {e.get('sequence', '')} {e['action']} {proto} {src} {dst}{port}".rstrip()
            )
    lines.append("exit")
    return lines

def build_snmp_lines(snmp_cfg):
    """Sinh lenh 'snmp-server ...' tu khoi YAML dang:
    snmp:
      snmp:
      enabled: true
      community: "netlab-ro"
      permission: RO # hoặc RW
      location: "VCB_HANOI"
      contact: "admin@vcb.com.vn"
    """
    if not snmp_cfg or not snmp_cfg.get("enabled"):
        return []
    lines = []
    community = snmp_cfg.get("community")
    if community:
        permission = snmp_cfg.get("permission", "RO")
        lines.append(f"snmp-server community {community} {permission}")
    if snmp_cfg.get("location"):
        lines.append(f"snmp-server location {snmp_cfg['location']}")
    if snmp_cfg.get("contact"):
        lines.append(f"snmp-server contact {snmp_cfg['contact']}")
    return lines

def build_interface_acl_bindings(bindings):
    lines = []
    for b in bindings or []:
        lines.append(f"interface {b['interface']}")
        lines.append(f" ip access-group {b['acl']} {b['direction']}")
        lines.append("exit")
    return lines

def build_switch_commands(device):
    name = device["name"]
    lines = [f"hostname {name}"]

    vlans = normalize_vlans(device)
    for vid, vname in sorted(vlans.items()):
        lines += [f"vlan {vid}", f" name {vname}", "exit"]

    if device.get("spanning-tree_root_primary") and vlans:
        for vid in sorted(vlans):
            lines.append(f"spanning-tree vlan {vid} root primary")

    for range_key, props in _flatten_ranges(device.get("interfaces-range")):
        base, end = parse_interface_range(range_key)
        lines.append(f"interface range {base} - {end}")
        mode = props.get("channel-group-mode", "active")
        lines.append(f" channel-group {props['channel-group']} mode {mode}")
        lines.append("exit")

    ifaces = normalize_interfaces(device)
    for iface, props in ifaces.items():
        lines.append(f"interface {iface}")
        if props.get("description"):
            lines.append(f" description {props['description']}")
        if props.get("switchport_mode") == "access":
            lines.append(" switchport mode access")
            if props.get("switchport_access_vlan"):
                lines.append(f" switchport access vlan {props['switchport_access_vlan']}")
            if props.get("spanning-tree portfast"):
                lines.append(" spanning-tree portfast")
            if str(props.get("spanning-tree bpduguard", "")).lower() == "enable":
                lines.append(" spanning-tree bpduguard enable")
        elif props.get("switchport_mode") == "trunk":
            lines.append(" switchport mode trunk")
        if props.get("ip") and is_svi_name(iface):
            lines.append(f" ip address {props['ip']} {props.get('netmask', '')}".rstrip())
        lines.append(" shutdown" if props.get("shutdown") else " no shutdown")
        lines.append("exit")

    for r in device.get("routed_interfaces", []) or []:
        (iface, props), = r.items()
        lines.append(f"interface {iface}")
        lines.append(" no switchport")
        lines.append(f" ip address {props['ip']} {props.get('netmask', '')}".rstrip())
        lines.append(" shutdown" if props.get("shutdown") else " no shutdown")
        lines.append("exit")
    if device.get("ip_default_gateway"):
        lines.append(f"ip default-gateway {device['ip_default_gateway']}")
    ip_routing = device.get("ip_routing", {})
    if ip_routing.get("enabled"):
        lines.append("ip routing")
        for s in ip_routing.get("static", []) or []:
            lines.append(f"ip route {s['destination']} {s['netmask']} {s['next_hop']}")
        ospf = ip_routing.get("ospf")
        if ospf and ospf.get("enabled"):
            lines.append(f"router ospf {ospf['process_id']}")
            for net in ospf.get("networks", []):
                lines.append(f" network {net['network']} {net['wildcard']} area {net['area']}")
            if ospf.get("default-information_originate"):
                lines.append(" default-information originate")
            lines.append("exit")

    for acl in device.get("acls", []) or []:
        lines += build_acl_lines(acl)
    lines += build_interface_acl_bindings(device.get("interfaces_acls"))

    ntp = device.get("ntp", {})
    if ntp.get("enabled"):
        for s in as_list(ntp.get("servers")):
            lines.append(f"ntp server {s}")

    syslog = device.get("syslog", {})
    if syslog.get("enabled"):
        for s in as_list(syslog.get("servers")):
            lines.append(f"logging host {s}")
        level = syslog.get("level")
        if level:
            level = SYSLOG_LEVEL_ALIASES.get(level, level)
            lines.append(f"logging trap {level}")
    lines += build_snmp_lines(device.get("snmp"))
    return lines
    
def _flatten_ranges(raw):
    for item in raw or []:
        (k, v), = item.items()
        yield k, v

def build_router_commands(device):
    name = device["name"]
    lines = [f"hostname {name}"]

    ifaces = normalize_interfaces(device)
    for iface in sorted(ifaces, key=lambda x: ("." in x, x)):
        props = ifaces[iface]
        lines.append(f"interface {iface}")
        if props.get("description"):
            lines.append(f" description {props['description']}")
        if "encap_dot1q_vlan" in props:
            lines.append(f" encapsulation dot1Q {props['encap_dot1q_vlan']}")
        if props.get("ip"):
            lines.append(f" ip address {props['ip']} {props.get('netmask', '')}".rstrip())
        if props.get("ip_helper_add"):
            lines.append(f"ip helper-address {props.get('ip_helper_add')}")
        if props.get("nat_role") == "inside":
            lines.append(" ip nat inside")
        elif props.get("nat_role") == "outside":
            lines.append(" ip nat outside")
        lines.append(" shutdown" if props.get("shutdown") else " no shutdown")
        lines.append("exit")

    for t in device.get("tunnel", []) or []:
        lines.append(f"interface {t['name']}")
        lines.append(f" tunnel source {t['source']}")
        lines.append(f" tunnel destination {t['destination']}")
        lines.append(f" ip address {t['ip']} {t.get('netmask', '')}".rstrip())
        lines.append(" shutdown" if t.get("shutdown") else " no shutdown")
        lines.append("exit")

    for s in device.get("static", []) or []:
        lines.append(f"ip route {s['destination']} {s['netmask']} {s['next_hop']}")

    ospf = device.get("ospf")
    if ospf and ospf.get("enabled"):
        lines.append(f"router ospf {ospf['process_id']}")
        for net in ospf.get("networks", []):
            lines.append(f" network {net['network']} {net['wildcard']} area {net['area']}")
        lines.append("exit")

    nat = device.get("nat")
    if nat and nat.get("enabled"):
        nat_pool_lines = []
        for pool in nat.get("pools", []) or []:
            nat_pool_lines.append(
                f"ip nat pool {pool['name']} {pool['start_ip']} {pool['end_ip']} "
                f"netmask {pool['netmask']}"
            )
        outside_ip_to_iface = {
            p.get("ip"): iface
            for iface, p in ifaces.items()
            if p.get("nat_role") == "outside" and p.get("ip")
        }
        nat_rule_lines = []
        for rule in nat.get("rules", []) or []:
            overload = " overload" if rule.get("overload") else ""
            if rule["type"] == "dynamic":
                nat_rule_lines.append(f"ip nat inside source list {rule['acl']} pool {rule['pool']}{overload}")
            elif rule["type"] == "static":
                local = rule.get("inside_local", rule.get("insideLocal"))
                glob = rule.get("inside_global", rule.get("insideGlobal"))
                nat_rule_lines.append(f"ip nat inside source static {local} {glob}")
            elif rule["type"] == "pat":
                glob = rule.get("inside_global", rule.get("insideGlobal"))
                iface = outside_ip_to_iface.get(glob)
                if iface:
                    nat_rule_lines.append(
                        f"ip nat inside source list {rule['acl']} interface {iface}{overload}"
                    )
                else:
                    tmp_pool = f"{rule['acl']}_PAT_POOL"
                    ip_ = glob
                    nat_pool_lines.append(
                        f"ip nat pool {tmp_pool} {ip_} {ip_} netmask 255.255.255.255"
                    )
                    nat_rule_lines.append(f"ip nat inside source list {rule['acl']} pool {tmp_pool}{overload}")
        lines += nat_pool_lines + nat_rule_lines

    for acl in device.get("acls", []) or []:
        lines += build_acl_lines(acl)
    lines += build_interface_acl_bindings(device.get("interfaces_acls"))

    dhcp = device.get("dhcp")
    if dhcp and dhcp.get("enabled"):
        excluded_lines = []
        pool_lines = []
        for pool in dhcp.get("pools", []) or []:
            for ex in pool.get("excluded_add", []) or []:
                excluded_lines.append(f"ip dhcp excluded-address {ex}")
            pool_lines.append(f"ip dhcp pool {pool['name']}")
            pool_lines.append(f" network {pool['network']} {pool.get('netmask', '')}".rstrip())
            if pool.get("ip_default_gateway"):
                pool_lines.append(f" default-router {pool['ip_default_gateway']}")
            if pool.get("dns_server"):
                pool_lines.append(f" dns-server {pool['dns_server']}")
            pool_lines.append("exit")
        lines += excluded_lines + pool_lines

    ntp = device.get("ntp", {})
    if ntp and ntp.get("enabled"):
        for s in as_list(ntp.get("servers")):
            lines.append(f"ntp server {s}")

    syslog = device.get("syslog", {})
    if syslog and syslog.get("enabled"):
        for s in as_list(syslog.get("servers")):
            lines.append(f"logging host {s}")
        level = syslog.get("level")
        if level:
            level = SYSLOG_LEVEL_ALIASES.get(level, level)
            lines.append(f"logging trap {level}")
    lines += build_snmp_lines(device.get("snmp"))
    return lines

def is_router_schema(device):
    return "protocol" in device


def build_commands_for_device(device):
    if is_router_schema(device):
        return build_router_commands(device)
    return build_switch_commands(device)


def build_backup_commands(device):
    tftp = device.get("tftp")
    server = get_tftp_server(tftp)
    if not tftp or not server or not tftp.get("backup_config"):
        return []
    if "enabled" in tftp and not tftp.get("enabled"):
        return []
    filename = f"{device['name']}-running.cfg"
    return [f"copy running-config tftp://{server}/{filename}"]

def load_all_devices(paths):
    import yaml

    devices = []
    for p in paths:
        with open(p) as f:
            data = yaml.safe_load(f)
        for d in data.get("devices", []):
            d = dict(d)
            d["_source_file"] = p
            devices.append(d)
    return devices


def main():
    paths = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not paths:
        print("Dung: python3 config_builder.py <file1.yaml> <file2.yaml> ... [--dry-run]")
        sys.exit(1)

    devices = load_all_devices(paths)
    ok, failed = 0, []
    for d in devices:
        name = d.get("name", "?")
        print(f"\n{'='*60}\n{name}  (source: {d.get('_source_file')})\n{'='*60}")
        try:
            cmds = build_commands_for_device(d)
            for line in cmds:
                print(line)
            backup = build_backup_commands(d)
            if backup:
                print("-- EXEC mode (sau khi 'end') --")
                for line in backup:
                    print(line)
            ok += 1
        except DeviceConfigError as e:
            print(f"!! LOI DU LIEU: {e}")
            failed.append(name)
        except Exception as e:
            print(f"!! LOI KHONG XAC DINH: {type(e).__name__}: {e}")
            failed.append(name)

    print(f"\n\nTong ket: {ok} thiet bi sinh lenh OK, {len(failed)} loi: {failed}")


if __name__ == "__main__":
    main()
