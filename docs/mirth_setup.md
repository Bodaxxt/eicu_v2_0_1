# 🔌 Mirth Connect (NextGen Connect) Integration Guide for ICU Guard

This document details the configuration and deployment of **Mirth Connect (NextGen Connect Integration Engine)** as an intermediary healthcare integration engine between hospital bedside devices (Philips, GE, Draeger, Roche) and the **ICU Guard v5.0 Clinical Reasoning Engine**.

---

## 1. Architecture Overview

```text
┌────────────────────────┐      MLLP / TCP       ┌────────────────────────┐
│ Bedside Devices        │ ────────────────────> │ Mirth Connect CE       │
│ - Philips IntelliVue   │      Port 6661        │ (Integration Engine)   │
│ - Radiometer ABL800    │                       │                        │
│ - Roche Cobas LIS      │                       │ Channels:              │
│ - B.Braun Smart Pumps  │                       │ 1. Bedside_Ingestion   │
│ - Draeger Ventilator   │                       │ 2. HL7_JSON_Transform  │
└────────────────────────┘                       └───────────┬────────────┘
                                                             │ HTTP POST / MLLP
                                                             │ JSON or Clean HL7
                                                             ▼
                                                 ┌────────────────────────┐
                                                 │ ICU Guard v5.0         │
                                                 │ Bridge & Severity Core │
                                                 │ Port 6661 / 8080       │
                                                 └────────────────────────┘
```

---

## 2. Prerequisites & Installation

### Option A: Running via Docker (Recommended)
```bash
docker run -d \
  --name mirth-connect \
  -p 8443:8443 \
  -p 6661:6661 \
  -p 6662:6662 \
  nextgenhealthcare/connect:latest
```

### Option B: Standalone Java Installation
1. Install **OpenJDK 17** or **21**.
2. Download Mirth Connect Community Edition from NextGen Healthcare.
3. Unpack and launch:
   ```bash
   mcservice start
   # Open administrator console at https://localhost:8443
   ```

---

## 3. Channel Configuration: `ICU_Bedside_Ingestion`

### Step 1: Source Connector (MLLP Listener)
- **Connector Type**: `TCP Listener`
- **Transmission Mode**: `MLLP`
- **Local Port**: `6661`
- **Encoding**: `UTF-8`
- **ACK Generation**: `Auto-generate HL7 ACK (MSA-1: AA)`

### Step 2: Transformer (HL7 v2.5 to JSON)
In the Channel Transformer tab, add a **JavaScript Transformer Step** to extract normalized telemetry:

```javascript
// Mirth Connect JavaScript Transformer Step
var msgObj = {
    message_id: msg['MSH']['MSH.10']['MSH.10.1'].toString(),
    sending_device: msg['MSH']['MSH.3']['MSH.3.1'].toString(),
    bed_id: msg['MSH']['MSH.4']['MSH.4.1'].toString(),
    patient_id: msg['PID']['PID.3']['PID.3.1'].toString(),
    timestamp: msg['MSH']['MSH.7']['MSH.7.1'].toString(),
    observations: []
};

// Loop over all OBX segments in the ORU message
for each (obx in msg['OBX']) {
    var loincCode = obx['OBX.3']['OBX.3.1'].toString();
    var paramName = obx['OBX.3']['OBX.3.2'].toString();
    var val = parseFloat(obx['OBX.5']['OBX.5.1'].toString());
    var unit = obx['OBX.6']['OBX.6.1'].toString();
    var flag = obx['OBX.8']['OBX.8.1'].toString();

    msgObj.observations.push({
        loinc: loincCode,
        name: paramName,
        value: val,
        unit: unit,
        flag: flag
    });
}

// Store as JSON for Destination Connector
channelMap.put('ICU_JSON_PAYLOAD', JSON.stringify(msgObj));
```

### Step 3: Destination Connector (Forward to ICU Guard)
- **Connector Type**: `TCP Sender` (or `HTTP Sender`)
- **Remote Host**: `127.0.0.1`
- **Remote Port**: `6661` (for raw MLLP) or `8080/api/hl7/ingest` (for REST)
- **Data Template**: `${ICU_JSON_PAYLOAD}` or Pass-through raw HL7 `${message.rawData}`

---

## 4. End-to-End Verification & Testing

### 1. Test from CLI Simulator:
```bash
python -m hl7_simulator.cli --device monitor --scenario critical --host 127.0.0.1 --port 6661 --dilation 60
```

### 2. Verify in Mirth Dashboard:
- In the Mirth Connect Administrator UI, check the `Dashboard` tab.
- Verify `Received`, `Filtered`, `Queued`, and `Sent` message counts are incrementing.
- View Message Details to inspect raw HL7 and transformed JSON outputs.

---

## 5. Production Hardening & Troubleshooting

| Issue | Root Cause | Solution |
|---|---|---|
| **Connection Refused (6661)** | Firewall or port binding conflict | Verify `netstat -ano \| findstr 6661` and ensure port is open |
| **Malformed Framing Error** | Missing `<VT>` (0x0B) or `<FS><CR>` (0x1C 0x0D) | Set Mirth Transmission Mode strictly to **MLLP** |
| **High Latency (>500ms)** | Disk buffer queue enabled on low-spec IO | In Channel settings, switch queue mode to `Memory Only` or `Attempt First` |
| **Missing Patient ID** | EMR admission not yet matched | Set default PID in transformer fallback: `msgObj.patient_id = cx || 'UNKNOWN'` |
