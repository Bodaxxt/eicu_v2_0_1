# 🏥 ICU Guard — HL7 Simulator & Integration Layer

A high-performance HL7 v2.5 simulation and integration framework designed to emulate bedside telemetry, arterial blood gas (ABG) analyzers, central lab LIS, smart infusion pumps, and mechanical ventilators found across Egyptian intensive care units (e.g., Philips IntelliVue, GE CARESCAPE, Mindray BeneVision, Radiometer ABL800, Roche Cobas 8000, Abbott ARCHITECT, Siemens Atellica, B.Braun Space, BD Alaris, Fresenius Agilia, Draeger Evita V800, Hamilton Medical, Puritan Bennett 980).

---

## 📁 Repository Architecture

```text
├── docs/
│   ├── mirth_setup.md                # Complete Mirth Connect (NextGen) setup & transformer guide
│   └── data_flow.md                  # End-to-end data flow, timing, and latencies
├── hl7_simulator/
│   ├── __init__.py
│   ├── cli.py                        # Unified CLI for all 5 device modalities
│   ├── core/
│   │   ├── loinc_codes.py            # LOINC ontology & abnormal flags (21+ features & drugs)
│   │   ├── segments.py               # HL7 v2.5 segment builders (MSH, PID, OBR, OBX, ACK)
│   │   ├── message_builder.py        # Fluent ORU^R01 message builder & MLLP framing
│   │   └── mllp_server.py            # Asynchronous TCP MLLP Server & Client (Port 6661)
│   ├── devices/
│   │   ├── base_device.py            # Standardized abstract device class & stream pipeline
│   │   ├── patient_monitor.py        # Philips / GE / Mindray Bedside Monitor
│   │   ├── abg_analyzer.py           # Radiometer / Cobas / GEM Premier ABG Analyzer
│   │   ├── central_lab.py            # Roche / Abbott / Siemens Central Lab LIS
│   │   ├── smart_pumps.py            # B.Braun / Alaris / Fresenius Smart Pumps
│   │   └── ventilator.py             # Draeger / Hamilton / Puritan Bennett Ventilator
│   ├── scenarios/
│   │   ├── patient_monitor_scenarios.py
│   │   ├── abg_scenarios.py
│   │   ├── lab_scenarios.py
│   │   ├── pump_scenarios.py
│   │   └── ventilator_scenarios.py
│   └── tests/
│       ├── test_hl7_core.py          # Core foundation tests
│       ├── test_patient_monitor.py   # Patient monitor tests
│       ├── test_abg_analyzer.py      # ABG analyzer & clinical tests
│       ├── test_central_lab.py       # Central Lab & KDIGO/ISTH tests
│       ├── test_smart_pumps.py       # Smart Pumps & vasoactive infusion tests
│       ├── test_ventilator.py        # Mechanical Ventilator & ARDS mechanics tests
│       └── test_integration_layer.py # End-to-End MLLP bridge & SeverityAgent tests
└── severity_agent/
    └── hl7/
        ├── __init__.py
        ├── receiver.py               # Multi-device async MLLP ingestion server (Port 6661)
        ├── parser.py                 # Segment decomposition & LOINC extraction
        ├── buffer.py                 # Rolling 6-hour sliding window & statistical aggregates
        ├── device_manager.py         # Multi-device inventory & bed-to-patient tracking
        ├── feature_extractor.py      # 154-Feature vector engineering
        └── integration.py            # ICUGuardBridge connecting HL7 directly to SeverityAgent
```

---

## ⚡ Real-Time Integration Flow

```text
[5 Bedside Devices]
        │  HL7 ORU^R01 (MLLP Port 6661)
        ▼
[HL7Receiver] ──> Responds with HL7 ACK (MSA|AA) (<10ms)
        │
        ▼
[HL7Parser] ────> Extracts MSH, PID, OBR, and OBX observations
        │
        ▼
[DeviceManager] ─> Updates device health & bed-to-patient mapping
        │
        ▼
[PatientBuffer] ─> Rolling 6-hour clinical window (mean, min, max, std)
        │
        ▼
[FeatureExtractor] ─> Computes exact 154-feature vector
        │
        ▼
[SeverityAgent] ─> Full Clinical Assessment (Tier, Organ Dysfunctions, SBAR)
```

---

## 🚀 Unified CLI Usage Guide

### 1. Run the Full Integration Bridge (Listener)
```bash
python -c "import asyncio; from severity_agent.hl7.integration import ICUGuardBridge; asyncio.run(ICUGuardBridge(port=6661).start()); asyncio.get_event_loop().run_forever()"
```

### 2. Stream Bedside Monitor
```bash
python -m hl7_simulator.cli --device monitor --scenario critical --brand philips --dilation 60
```

### 3. On-Demand ABG Analysis
```bash
python -m hl7_simulator.cli --device abg --scenario septic --brand radiometer --on-demand
```

### 4. Routine Central Laboratory Panel
```bash
python -m hl7_simulator.cli --device lab --scenario renal --brand roche --on-demand
```

### 5. Smart Infusion Pumps Titration
```bash
python -m hl7_simulator.cli --device pumps --scenario high --brand bbraun --on-demand
```

### 6. Mechanical Ventilator Snapshot
```bash
python -m hl7_simulator.cli --device ventilator --scenario severe --brand draeger --on-demand
```

---

## 🧪 Running the Full Test Suite (59 Tests)
```bash
python -m unittest discover -s hl7_simulator/tests
```
All 59 unit, integration, and scenario tests pass in under 3 seconds!
