
import argparse

from nornir import InitNornir
from nornir.core.filter import F
from nornir_utils.plugins.functions import print_result

import config_builder as cb
from nornir_tasks import push_config_pexpect


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", help="file(s) YAML chua du lieu cau hinh (vd devices_corrected.yaml)")
    ap.add_argument("--inventory-dir", default="inventory")
    ap.add_argument("--group", help="chi chay tren 1 group: switches hoac routers")
    ap.add_argument("--host", help="chi chay tren 1 host (theo ten trong YAML)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--num-workers", type=int, default=10, help="so thread chay song song")
    args = ap.parse_args()

    devices = cb.load_all_devices(args.files)
    device_lookup = {d["name"]: d for d in devices}

    nr = InitNornir(
        runner={"plugin": "threaded", "options": {"num_workers": args.num_workers}},
        inventory={
            "plugin": "SimpleInventory",
            "options": {
                "host_file": f"{args.inventory_dir}/hosts.yaml",
                "group_file": f"{args.inventory_dir}/groups.yaml",
                "defaults_file": f"{args.inventory_dir}/defaults.yaml",
            },
        },
    )

    target = nr
    if args.group:
        target = target.filter(F(has_parent_group=args.group))
    if args.host:
        target = target.filter(name=args.host)

    result = target.run(task=push_config_pexpect, device_lookup=device_lookup, dry_run=args.dry_run)
    print_result(result)

    failed = [h for h, r in result.items() if r.failed]
    print(f"\nTONG KET: {len(result) - len(failed)} OK, {len(failed)} LOI {failed}")


if __name__ == "__main__":
    main()
