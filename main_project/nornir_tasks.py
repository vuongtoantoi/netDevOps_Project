

from nornir.core.task import Result

import config_builder as cb
import deploy_pexpect as dp


def push_config_pexpect(task, device_lookup, dry_run=False, log_dir="logs"):
    """1 Nornir task = 1 host. Nornir tu goi ham nay song song cho moi host
    trong tap duoc chon (task.host.name phai TRUNG voi 'name' trong YAML,
    do generate_nornir_inventory.py dat ten host = ten thiet bi)."""
    device = device_lookup.get(task.host.name)
    if device is None:
        return Result(host=task.host, failed=True,
                      result=f"Khong tim thay du lieu cau hinh cho '{task.host.name}' trong YAML")

    try:
        commands = cb.build_commands_for_device(device)
    except cb.DeviceConfigError as e:
        return Result(host=task.host, failed=True, result=f"Loi du lieu YAML: {e}")

    if dry_run:
        return Result(host=task.host, result=f"(dry-run) se gui {len(commands)} dong lenh")

    try:
        child = dp.connect(device, log_dir)
        rejected = dp.push_commands(child, commands)
        dp.save_and_backup(child, device)
        child.sendline("exit")
        child.close()
        if rejected:
            return Result(
                host=task.host, failed=True,
                result=f"Da day nhung {len(rejected)} lenh bi IOS tu choi: {rejected}",
            )
        return Result(host=task.host, result=f"OK - da day {len(commands)} dong lenh")
    except Exception as e:  # noqa: BLE001 - muon Nornir ghi nhan LOI thay vi lam sap ca batch
        return Result(host=task.host, failed=True, result=f"{type(e).__name__}: {e}")
