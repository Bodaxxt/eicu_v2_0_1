"""
cli.py — Command-Line Interface for ICU HL7 Device Simulator
============================================================
Allows starting patient monitors, ABG analyzers, Central Lab,
Smart Infusion Pumps, and Mechanical Ventilators with configurable
clinical scenarios, brands, intervals, and MLLP targets.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from hl7_simulator.devices.patient_monitor import PatientMonitor
from hl7_simulator.devices.abg_analyzer import ABGAnalyzer
from hl7_simulator.devices.central_lab import CentralLab
from hl7_simulator.devices.smart_pumps import SmartPumps
from hl7_simulator.devices.ventilator import Ventilator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("hl7_simulator.cli")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ICU Guard HL7 Device Simulator (Monitor, ABG, Lab, Pumps, Ventilator)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--device",
        type=str,
        default="monitor",
        choices=["monitor", "abg", "lab", "pumps", "ventilator"],
        help="Medical device type to simulate",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default="",
        help="Clinical scenario (monitor: stable/deteriorating/critical | abg: normal/acidosis/respiratory/septic | lab: normal/renal/sepsis/dic | pumps: no_vaso/moderate/high | vent: no_vent/moderate/severe)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.0,
        help="Telemetry interval in seconds (default: 30s monitor, 3600s abg, 14400s lab, 300s pumps/vent)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=360.0,
        help="Total duration of clinical observation in minutes (360 = 6 hours)",
    )
    parser.add_argument(
        "--dilation",
        type=float,
        default=60.0,
        help="Time acceleration multiplier (e.g., 60 = 1 minute per real second)",
    )
    parser.add_argument(
        "--bed",
        type=str,
        default="ICU_BED_01",
        help="Bed location identifier",
    )
    parser.add_argument(
        "--patient-id",
        type=str,
        default="224606",
        help="Patient identifier",
    )
    parser.add_argument(
        "--brand",
        type=str,
        default="",
        help="Device brand (monitor: philips/ge/mindray | abg: radiometer/roche/il_gem | lab: roche/abbott/siemens | pumps: bbraun/alaris/fresenius | vent: draeger/hamilton/puritan)",
    )
    parser.add_argument(
        "--on-demand",
        action="store_true",
        help="Execute a single on-demand sample/update",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Target MLLP server host",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=6661,
        help="Target MLLP server port",
    )
    parser.add_argument(
        "--cohort-csv",
        type=str,
        default="",
        help="Optional path to multilabel_cohort.csv to load patient specifics",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print generated HL7 messages to stdout without network transmission",
    )
    return parser.parse_args()


async def run_patient_monitor(args: argparse.Namespace):
    brand = args.brand if args.brand in ["philips", "ge", "mindray"] else "philips"
    scenario = args.scenario if args.scenario in ["stable", "deteriorating", "critical"] else "stable"
    interval = args.interval if args.interval > 0 else 30.0

    print("=" * 70)
    print("[ICU GUARD] PATIENT MONITOR SIMULATOR")
    print("=" * 70)
    print(f"Device Brand : {brand.upper()}")
    print(f"Bed ID       : {args.bed}")
    print(f"Patient ID   : {args.patient_id}")
    print(f"Scenario     : {scenario.upper()}")
    print(f"Duration     : {args.duration} minutes (Interval: {interval}s)")
    print(f"Acceleration : {args.dilation}x")
    if not args.dry_run:
        print(f"MLLP Target  : tcp://{args.host}:{args.port}")
    else:
        print("Mode         : DRY RUN (Local output only)")
    print("=" * 70)

    monitor = PatientMonitor(
        bed_id=args.bed,
        patient_id=args.patient_id,
        brand=brand,
        scenario_name=scenario,
    )

    if args.cohort_csv:
        csv_path = Path(args.cohort_csv)
        if csv_path.exists():
            monitor.load_cohort_patient(csv_path, args.patient_id)
            print(f"Loaded cohort data from: {csv_path}")

    if not args.dry_run:
        monitor.connect(host=args.host, port=args.port)

    count = 0
    try:
        async for msg, ack in monitor.stream(
            duration_minutes=args.duration,
            interval_seconds=interval,
            time_dilation=args.dilation,
        ):
            count += 1
            print(f"\n--- [Message #{count} | Control ID: {msg.message_id}] ---")
            print(msg.summary())
            if ack:
                first_line = ack.split("\r")[0] if "\r" in ack else ack
                print(f"  --> ACK Received: {first_line}")
            elif not args.dry_run:
                print("  --> No ACK (MLLP connection failed or dry run)")

    except KeyboardInterrupt:
        print("\nSimulation aborted by user.")
    finally:
        monitor.disconnect()
        print(f"\nSimulation completed. Total messages generated: {count}")


async def run_abg_analyzer(args: argparse.Namespace):
    brand = args.brand if args.brand in ["radiometer", "roche", "il_gem"] else "radiometer"
    scenario = args.scenario if args.scenario in ["normal", "acidosis", "respiratory", "septic"] else "normal"
    interval = args.interval if args.interval > 0 else 3600.0

    print("=" * 70)
    print("[ICU GUARD] ARTERIAL BLOOD GAS (ABG) ANALYZER SIMULATOR")
    print("=" * 70)
    print(f"Device Brand : {brand.upper()}")
    print(f"Bed ID       : {args.bed}")
    print(f"Patient ID   : {args.patient_id}")
    print(f"Scenario     : {scenario.upper()}")
    if args.on_demand:
        print("Mode         : ON-DEMAND SAMPLE DRAW")
    else:
        print(f"Mode         : CONTINUOUS (Interval: {interval}s, Duration: {args.duration}m)")
    if not args.dry_run:
        print(f"MLLP Target  : tcp://{args.host}:{args.port}")
    else:
        print("Network      : DRY RUN (Local output only)")
    print("=" * 70)

    abg = ABGAnalyzer(
        bed_id=args.bed,
        patient_id=args.patient_id,
        brand=brand,
        scenario_name=scenario,
    )

    if not args.dry_run:
        abg.connect(host=args.host, port=args.port)

    try:
        if args.on_demand:
            readings, interp, msg = abg.sample_on_demand(progress=1.0)
            print(f"\n--- [ABG Sample #1 | Control ID: {msg.message_id}] ---")
            print(msg.summary())
            print("\n" + interp.format_text())

            if not args.dry_run and abg._client:
                ack = await abg._client.send_message(msg.to_string())
                print(f"\n  --> ACK Received: {ack.splitlines()[0]}")
        else:
            count = 0
            async for msg, ack in abg.stream(
                duration_minutes=args.duration,
                interval_seconds=interval,
                time_dilation=args.dilation,
            ):
                count += 1
                progress = count / max(1, (args.duration * 60 / interval))
                readings = abg.get_readings(progress=min(1.0, progress))
                interp = abg.interpret(readings)

                print(f"\n--- [ABG Sample #{count} | Control ID: {msg.message_id}] ---")
                print(msg.summary())
                print("\n" + interp.format_text())
                if ack:
                    first_line = ack.split("\r")[0] if "\r" in ack else ack
                    print(f"  --> ACK Received: {first_line}")
                elif not args.dry_run:
                    print("  --> No ACK (MLLP connection failed or dry run)")

    except KeyboardInterrupt:
        print("\nSimulation aborted by user.")
    finally:
        abg.disconnect()
        print("\nABG Simulation completed.")


async def run_central_lab(args: argparse.Namespace):
    brand = args.brand if args.brand in ["roche", "abbott", "siemens"] else "roche"
    scenario = args.scenario if args.scenario in ["normal", "renal", "sepsis", "dic"] else "normal"
    interval = args.interval if args.interval > 0 else 14400.0

    print("=" * 70)
    print("[ICU GUARD] CENTRAL LABORATORY (LIS) SIMULATOR")
    print("=" * 70)
    print(f"Analyzer Brand: {brand.upper()}")
    print(f"Bed ID        : {args.bed}")
    print(f"Patient ID    : {args.patient_id}")
    print(f"Scenario      : {scenario.upper()}")
    if args.on_demand:
        print("Mode          : ON-DEMAND LAB DRAW")
    else:
        print(f"Mode          : ROUTINE SURVEILLANCE (Interval: {interval}s, Duration: {args.duration}m)")
    if not args.dry_run:
        print(f"MLLP Target   : tcp://{args.host}:{args.port}")
    else:
        print("Network       : DRY RUN (Local output only)")
    print("=" * 70)

    lab = CentralLab(
        bed_id=args.bed,
        patient_id=args.patient_id,
        brand=brand,
        scenario_name=scenario,
    )

    if not args.dry_run:
        lab.connect(host=args.host, port=args.port)

    try:
        if args.on_demand:
            readings, interp, msg = lab.sample_on_demand(progress=1.0)
            print(f"\n--- [Lab Panel #1 | Control ID: {msg.message_id}] ---")
            print(msg.summary())
            print("\n" + interp.format_text())

            if not args.dry_run and lab._client:
                ack = await lab._client.send_message(msg.to_string())
                print(f"\n  --> ACK Received: {ack.splitlines()[0]}")
        else:
            count = 0
            async for msg, ack in lab.stream(
                duration_minutes=args.duration,
                interval_seconds=interval,
                time_dilation=args.dilation,
            ):
                count += 1
                progress = count / max(1, (args.duration * 60 / interval))
                readings = lab.get_readings(progress=min(1.0, progress))
                interp = lab.interpret(readings)

                print(f"\n--- [Lab Panel #{count} | Control ID: {msg.message_id}] ---")
                print(msg.summary())
                print("\n" + interp.format_text())
                if ack:
                    first_line = ack.split("\r")[0] if "\r" in ack else ack
                    print(f"  --> ACK Received: {first_line}")
                elif not args.dry_run:
                    print("  --> No ACK (MLLP connection failed or dry run)")

    except KeyboardInterrupt:
        print("\nSimulation aborted by user.")
    finally:
        lab.disconnect()
        print("\nCentral Lab simulation completed.")


async def run_smart_pumps(args: argparse.Namespace):
    brand = args.brand if args.brand in ["bbraun", "alaris", "fresenius"] else "bbraun"
    scenario = args.scenario if args.scenario in ["no_vaso", "moderate", "high"] else "no_vaso"
    interval = args.interval if args.interval > 0 else 300.0

    print("=" * 70)
    print("[ICU GUARD] SMART INFUSION PUMPS SIMULATOR")
    print("=" * 70)
    print(f"Pump Network : {brand.upper()}")
    print(f"Bed ID       : {args.bed}")
    print(f"Patient ID   : {args.patient_id}")
    print(f"Scenario     : {scenario.upper()}")
    if args.on_demand:
        print("Mode         : ON-DEMAND INFUSION UPDATE")
    else:
        print(f"Mode         : CONTINUOUS TITRATION (Interval: {interval}s, Duration: {args.duration}m)")
    if not args.dry_run:
        print(f"MLLP Target  : tcp://{args.host}:{args.port}")
    else:
        print("Network      : DRY RUN (Local output only)")
    print("=" * 70)

    pumps = SmartPumps(
        bed_id=args.bed,
        patient_id=args.patient_id,
        brand=brand,
        scenario_name=scenario,
    )

    if not args.dry_run:
        pumps.connect(host=args.host, port=args.port)

    try:
        if args.on_demand:
            readings, interp, msg = pumps.sample_on_demand(progress=1.0)
            print(f"\n--- [Infusion Update #1 | Control ID: {msg.message_id}] ---")
            print(msg.summary())
            print("\n" + interp.format_text())

            if not args.dry_run and pumps._client:
                ack = await pumps._client.send_message(msg.to_string())
                print(f"\n  --> ACK Received: {ack.splitlines()[0]}")
        else:
            count = 0
            async for msg, ack in pumps.stream(
                duration_minutes=args.duration,
                interval_seconds=interval,
                time_dilation=args.dilation,
            ):
                count += 1
                progress = count / max(1, (args.duration * 60 / interval))
                readings = pumps.get_readings(progress=min(1.0, progress))
                interp = pumps.interpret(readings)

                print(f"\n--- [Infusion Update #{count} | Control ID: {msg.message_id}] ---")
                print(msg.summary())
                print("\n" + interp.format_text())
                if ack:
                    first_line = ack.split("\r")[0] if "\r" in ack else ack
                    print(f"  --> ACK Received: {first_line}")
                elif not args.dry_run:
                    print("  --> No ACK (MLLP connection failed or dry run)")

    except KeyboardInterrupt:
        print("\nSimulation aborted by user.")
    finally:
        pumps.disconnect()
        print("\nSmart Pumps simulation completed.")


async def run_ventilator(args: argparse.Namespace):
    brand = args.brand if args.brand in ["draeger", "hamilton", "puritan"] else "draeger"
    scenario = args.scenario if args.scenario in ["no_vent", "moderate", "severe"] else "no_vent"
    interval = args.interval if args.interval > 0 else 300.0

    print("=" * 70)
    print("[ICU GUARD] MECHANICAL VENTILATOR SIMULATOR")
    print("=" * 70)
    print(f"Ventilator   : {brand.upper()}")
    print(f"Bed ID       : {args.bed}")
    print(f"Patient ID   : {args.patient_id}")
    print(f"Scenario     : {scenario.upper()}")
    if args.on_demand:
        print("Mode         : ON-DEMAND VENTILATOR SNAPSHOT")
    else:
        print(f"Mode         : CONTINUOUS TELEMETRY (Interval: {interval}s, Duration: {args.duration}m)")
    if not args.dry_run:
        print(f"MLLP Target  : tcp://{args.host}:{args.port}")
    else:
        print("Network      : DRY RUN (Local output only)")
    print("=" * 70)

    vent = Ventilator(
        bed_id=args.bed,
        patient_id=args.patient_id,
        brand=brand,
        scenario_name=scenario,
    )

    if not args.dry_run:
        vent.connect(host=args.host, port=args.port)

    try:
        if args.on_demand:
            readings, interp, msg = vent.sample_on_demand(progress=1.0)
            print(f"\n--- [Ventilator Update #1 | Control ID: {msg.message_id}] ---")
            print(msg.summary())
            print("\n" + interp.format_text())

            if not args.dry_run and vent._client:
                ack = await vent._client.send_message(msg.to_string())
                print(f"\n  --> ACK Received: {ack.splitlines()[0]}")
        else:
            count = 0
            async for msg, ack in vent.stream(
                duration_minutes=args.duration,
                interval_seconds=interval,
                time_dilation=args.dilation,
            ):
                count += 1
                progress = count / max(1, (args.duration * 60 / interval))
                readings = vent.get_readings(progress=min(1.0, progress))
                interp = vent.interpret(readings)

                print(f"\n--- [Ventilator Update #{count} | Control ID: {msg.message_id}] ---")
                print(msg.summary())
                print("\n" + interp.format_text())
                if ack:
                    first_line = ack.split("\r")[0] if "\r" in ack else ack
                    print(f"  --> ACK Received: {first_line}")
                elif not args.dry_run:
                    print("  --> No ACK (MLLP connection failed or dry run)")

    except KeyboardInterrupt:
        print("\nSimulation aborted by user.")
    finally:
        vent.disconnect()
        print("\nVentilator simulation completed.")


async def main_async():
    args = parse_args()
    if args.device == "abg":
        await run_abg_analyzer(args)
    elif args.device == "lab":
        await run_central_lab(args)
    elif args.device == "pumps":
        await run_smart_pumps(args)
    elif args.device == "ventilator":
        await run_ventilator(args)
    else:
        await run_patient_monitor(args)


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
