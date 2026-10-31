# Public CAN Bus Datasets Catalog

> Research date: 2026-07-19
> Purpose: Supplement existing Toyota MF4 data (4,274 decoded frames) for model training

---

## Ranked Top 10 Datasets

### 1. HCRL Car-Hacking Dataset (Kia Soul) — BEST OVERALL
- **URL**: https://www.dropbox.com/scl/fo/9rwsf9pclhvv9xxloojom/AF7JeRW893grZkigkulkAHk?rlkey=3h6zamu3kc262lrnipu5qden8&st=3g52q9hd&dl=0
- **Vehicle**: Kia Soul
- **Size**: ~30-40 min per attack file, ~2M+ total frames
- **Format**: CSV (Timestamp, CAN ID, DLC, DATA[0-7], Flag)
- **Attack labels**: YES — per-frame (T=injected, R=normal)
- **DBC files**: NO (raw CAN IDs only)
- **License**: Academic use (cite papers)
- **Access**: Free Dropbox download
- **Why #1**: Real vehicle, per-frame labels, 4 attack types (DoS, Fuzzy, Gear Spoofing, RPM Spoofing) + attack-free baseline. Most cited CAN IDS dataset.

---

### 2. HCRL OTIDS Dataset (Kia Soul) — LARGEST RAW DATASET
- **URL**: https://www.dropbox.com/scl/fo/8kll7yvbgogkp0vahowvm/ADhDIC8LRFL8wHUexib3C3w?rlkey=8cp7scxgw25yt4wp8v2c2v8mp&st=rplc74rm&dl=0
- **Vehicle**: Kia Soul
- **Size**: ~4.5M frames (200 MB attack-free), 391 MB total
- **Format**: TXT (whitespace-separated: Timestamp, ID, DLC, DATA[0-7])
- **Attack labels**: YES (file-level: DoS=ID 0x000 injection; Fuzzy= random; Impersonation= ID 0x164)
- **DBC files**: NO
- **License**: Academic use
- **Access**: Free Dropbox download
- **Why #2**: Massive dataset (4.5M benign frames). The de facto benchmark. File-level labels require careful handling.

---

### 3. CrySyS Lab Dataset (Nature Scientific Data 2023) — HIGHEST QUALITY
- **URL**: https://doi.org/10.6084/m9.figshare.c.6726165.v1 (Figshare)
- **Vehicle**: Unspecified (European test vehicle)
- **Size**: 26 benign traces (~2.5 hours), 1274 total traces, ~12 GB extracted
- **Format**: SocketCAN candump logs (.log), JSON metadata
- **Attack labels**: YES — per-frame (fabrication + masquerade attacks)
  - 6 signal modification strategies: CONST, REPLAY, POS-OFFSET, NEG-OFFSET, ADD-INCR, ADD-DECR
  - Single-signal and double-signal variants
- **DBC files**: Partially (78 signals manually reverse-engineered, documented in paper)
- **License**: CC-BY 4.0
- **Access**: Free Figshare download (2.85 GB ZIP)
- **Why #3**: Peer-reviewed, Nature publication. 1274 traces with fabrication + masquerade attacks. Source code for attack generation released. Open source.

---

### 4. ROAD Dataset
- **URL**: https://roaddataset.nyc3.digitaloceanspaces.com/road.zip
- **Vehicle**: Real vehicle (on dynamometer)
- **Size**: Large (fabrication + masquerade attacks on real CAN network)
- **Format**: SocketCAN candump logs
- **Attack labels**: YES (physically verified attacks)
- **DBC files**: NO (but labeling scripts provided)
- **License**: Academic use
- **Access**: Free direct download (zip)
- **Why #4**: Considered "most complete" by CrySyS paper. Both fabrication and masquerade attacks verified on real vehicle. Scripts for parsing included.

---

### 5. HCRL Car Hacking Challenge 2020 (Hyundai Avante CN7)
- **URL**: https://dx.doi.org/10.21227/qvr7-n418 (IEEE DataPort)
- **Vehicle**: Hyundai Avante CN7
- **Size**: Multiple CSV files (train/test splits)
- **Format**: CSV (Timestamp, Arbitration_ID, DLC, Data, Class, SubClass)
- **Attack labels**: YES — per-frame (Normal/Attack + SubClass: Flooding, Spoofing, Replay, Fuzzing)
- **DBC files**: NO
- **License**: Open via IEEE DataPort
- **Access**: Free download (IEEE account required)
- **Why #5**: Newer Hyundai vehicle, multi-class labels (not just binary), 4 attack types. Competition dataset from NDSS 2021 portfolio security workshop.

---

### 6. Bit-Scanner CAN Dataset (35 traces)
- **URL**: https://github.com/happy-little-zhang/Bit-Scanner/tree/main/CAN_dataset
- **Vehicle**: Multiple vehicles (35 traces)
- **Size**: 35 CAN traffic traces (all attack-free/normal)
- **Format**: CSV (timestamp_us, ID, byte1-byte8)
- **Attack labels**: NO (normal traffic only)
- **DBC files**: NO
- **License**: Academic use
- **Access**: Direct GitHub download
- **Why #6**: Clean normal traffic traces from multiple vehicles. Good for training baseline models on diverse CAN patterns.

---

### 7. HCRL B-CAN Intrusion Dataset (Genesis G80)
- **URL**: https://www.dropbox.com/scl/fi/wckmq7vmm8to9eudz1mjl/B-CAN-Intrusion-Dataset.zip?rlkey=7to4vnrntgawxjljzusxtr02q&st=m2e9q22s&dl=0
- **Vehicle**: Hyundai Genesis G80
- **Size**: ~24 min of driving data
- **Format**: CSV (Timestamp, ID, DLC, Payload, Label)
- **Attack labels**: YES — per-frame (Label: 0.0=normal, 1.0=injected)
- **Attack types**: DoS (25 attacks), Fuzzing (10 attacks)
- **DBC files**: NO
- **License**: Academic use
- **Access**: Free Dropbox download
- **Why #7**: Body CAN (B-CAN) bus data — different bus type than powertrain CAN. Genesis G80 is a luxury vehicle with different ECU architecture.

---

### 8. CAN-MIRGU Dataset (Moving Vehicles, NDSS 2024)
- **URL**: https://drive.google.com/drive/folders/1uUKLEu_tFVMy9WkDnf1rqqPwuQLQFwBL?usp=sharing
- **Vehicle**: Modern vehicle with autonomous driving capabilities
- **Size**: Multi-day collection (6+ days of benign + attack scenarios)
- **Format**: .log files (CAN bus logs)
- **Attack labels**: YES — per-frame
  - Masquerade attacks (Break warning masquerade)
  - Suspension attacks (ID 0x7F suspension)
  - Real attacks (Break warning attack)
- **DBC files**: NO
- **License**: Academic use (cite NDSS 2024 paper)
- **Access**: Free Google Drive download
- **Why #8**: Real-world driving scenarios with physically verified attacks. Modern vehicle with ADAS. Published at top security venue (NDSS).

---

### 9. SynCAN Dataset (ETAS/IEEE Access 2020) — SYNTHETIC BUT WELL-STRUCTURED
- **URL**: https://github.com/etas/SynCAN (archived repo, ZIPs included)
- **Size**: 4 training sets + 6 test sets (normal, plateau, continuous, playback, suppress, flooding)
- **Format**: CSV (Label, ID, Time, Signal1-4_of_ID)
- **Attack labels**: YES — per-frame (Label: 0=normal, 1=intrusion)
- **DBC files**: N/A (signal space, not raw CAN)
- **License**: Non-commercial use (academic/personal)
- **Access**: Direct GitHub download
- **Caveat**: SYNTHETIC data — generated from signal models, not real captures
- **Why #9**: Clean, well-structured benchmark. Good for signal-space analysis. 10 CAN IDs with decoded signals.

---

### 10. CAN-MIRGU Sample Dataset / HCRL Driving Dataset
- **URL**: Various HCRL pages (https://ocslab.hksecurity.net/Datasets)
- **Additional HCRL datasets available**:
  - CAN-FD Intrusion Dataset
  - M-CAN Intrusion Dataset
  - SAE J1939 Dataset
  - CAN Signal Extraction and Translation Dataset
- **License**: Academic use
- **Access**: Free via HCRL website

---

## Additional Notable Datasets

### HCRL X-CANIDS Dataset (In-Vehicle Signal Dataset)
- URL: https://ocslab.hksecurity.net/Datasets/x-canids-dataset-in-vehicle-signal-dataset
- Focus: In-vehicle signal-level data

### 4TU CAN Bus Intrusion Dataset v2
- URL: https://data.4tu.nl (search for "CAN bus")
- Vehicle: Unknown
- Format: CSV
- Attack types: Suspension, fabrication, masquerade
- License: CC-BY 4.0

### DeepCAN / SynCAN (Eliesgherbi et al.)
- URL: https://github.com/eliesgherbi/Deep-Learning-4-IDS (uses SynCAN)
- Framework for multi-vehicle CAN IDS

---

## Comparison Matrix

| # | Dataset | Vehicle | Real Data | Frames | Labels | Attack Types | DBC | Format | License |
|---|---------|---------|-----------|--------|--------|-------------|-----|--------|---------|
| 1 | Car-Hacking | Kia Soul | Yes | ~2M+ | Per-frame | DoS/Fuzzy/Spoofing | No | CSV | Academic |
| 2 | OTIDS | Kia Soul | Yes | ~4.5M | File-level | DoS/Fuzzy/Impersonation | No | TXT | Academic |
| 3 | CrySyS | European | Yes | 1274 traces | Per-frame | Fabrication/Masquerade | Partial | SocketCAN | CC-BY 4.0 |
| 4 | ROAD | Real vehicle | Yes | Large | Per-frame | Fabrication/Masquerade | No | SocketCAN | Academic |
| 5 | Challenge 2020 | Hyundai Avante | Yes | Multiple CSVs | Per-frame | 4 types | No | CSV | Open |
| 6 | Bit-Scanner | Multiple | Yes | 35 traces | None | Normal only | No | CSV | Academic |
| 7 | B-CAN | Genesis G80 | Yes | ~24 min | Per-frame | DoS/Fuzzing | No | CSV | Academic |
| 8 | CAN-MIRGU | Modern ADAS | Yes | Multi-day | Per-frame | Masquerade/Suspension | No | LOG | Academic |
| 9 | SynCAN | Synthetic | No | Small | Per-frame | 6 types | No | CSV | Non-commercial |
| 10 | HCRL Misc | Various | Yes | Varies | Varies | Varies | No | Various | Academic |

---

## Recommendation for Our Project

**Priority downloads** (in order):
1. **Car-Hacking Dataset** — Largest, most-cited, per-frame labels
2. **OTIDS** — 4.5M frames of normal traffic for baseline training
3. **CrySyS** — Nature-published, fabrication + masquerade, open source code
4. **Challenge 2020** — Modern Hyundai, multi-class labels
5. **ROAD** — Most complete attack coverage on real vehicle

**Key observations**:
- Most datasets are for **security/IDS** (attack detection), not general telemetry
- **None include DBC files** — we'll need to reverse-engineer signals or use raw CAN IDs
- **Real vehicle data** is the norm — only SynCAN is synthetic
- **Format diversity**: CSV, TXT, SocketCAN logs — need a unified parser
- **Toyota data** is rare in public datasets — our existing data is valuable for Toyota-specific models

**Estimated total downloadable data**: ~10M+ frames across all datasets
