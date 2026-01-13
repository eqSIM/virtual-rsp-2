# MNO Management Console (Operator GUI)

**[← Previous: Dev GUI](06-GUI-CONTROL-CENTER.md)** | **[Index](README.md)** | **[Next: Demo Script →](08-DEMO-SCRIPT.md)**

---

## Table of Contents
1. [Overview](#overview)
2. [Administrative Architecture](#1-administrative-architecture-main_windowpy)
3. [Backend Services](#2-backend-services)
4. [Specialized Widgets](#3-specialized-widgets)
5. [Remote Lifecycle Flow](#4-remote-lifecycle-flow)
6. [Running the Application](#running-the-application)

---

The **MNO Management Console** (`mno/`) is an administrative tool that simulates the interface used by a Mobile Network Operator (MNO) to manage their SM-DP+ server and connected devices.

## Overview

- **Primary Role**: Server administration and fleet monitoring.
- **Framework**: PySide6 (Qt for Python).
- **Communication**: Interacts with `osmo-smdpp` via a custom REST API.
- **Key Features**:
  - Server health and download statistics dashboard.
  - Profile warehouse management (upload/delete packages).
  - Real-time RSP session monitoring.
  - Per-device download history audit trail.
  - Remote lifecycle management (Remote Enable/Disable).

## 1. Administrative Architecture (`main_window.py`)

Unlike the developer GUI, this application uses a tabbed navigation system to separate different administrative domains.

### Tabs
1.  **Dashboard**: High-level KPIs (Total Profiles, Success Rate, Active Sessions).
2.  **Profile Inventory**: Manages the `.der` files stored on the SM-DP+ server.
3.  **Active Sessions**: Real-time view of "in-flight" RSP downloads.
4.  **EID History**: Audit trail of which device (EID) downloaded which profile and when.
5.  **Device Control**: Remote interface to manage profiles on the connected virtual eSIM.

## 2. Backend Services

### SM-DP+ API Service (`mno/services/smdp_api.py`)
A REST client that communicates with the extensions we added to `osmo-smdpp`.
- **Endpoints**: Uses `requests` to call `/mno/profiles`, `/mno/sessions`, `/mno/stats`, etc.
- **Error Handling**: Gracefully handles server timeouts or connection issues, showing status indicators in the UI.

### LPA Command Service (`mno/services/lpa_command.py`)
Sends commands to the virtual eUICC via `lpac`, but uses the **shared ProfileStore** (`data/profiles.json`).
- **Consistency**: Ensures that actions taken in the MNO Console (like a remote enable) are reflected in the Developer GUI and vice versa.
- **Shared Store**: Imports `ProfileStore` from the `gui/` package to maintain a single source of truth.

## 3. Specialized Widgets

### Dashboard Panel (`mno/widgets/dashboard_panel.py`)
- **Metric Cards**: Displays real-time statistics retrieved from the SM-DP+ stats endpoint.
- **Auto-Refresh**: Uses a `QTimer` to poll the server every 4 seconds.

### Session Panel (`mno/widgets/session_panel.py`)
- **Live Monitor**: Lists every active RSP transaction.
- **Perspectives**: Shows the Transaction ID and the current state (Authenticating, Downloading, etc.).

### EID History (`mno/widgets/eid_panel.py`)
- **Device Audit**: Groups all historical downloads by EID.
- **Search**: Allows operators to quickly find all profiles ever delivered to a specific physical device.

## 4. Remote Lifecycle Flow

The Device Control tab allows operators to manage profiles on a connected eUICC remotely.

### Download Flow
1.  **Select Profile**: Operator clicks "Download Profile to Device".
2.  **Choose from Inventory**: A dialog shows all profiles available on the SM-DP+ server (fetched via `GET /mno/profiles`).
3.  **Async Execution**: The download runs in a `QThread` (`DownloadWorker`) to prevent UI freezing.
4.  **Real-time Logs**: The Operation Log panel shows each RSP step as it happens (authentication, BPP download, etc.).
5.  **Persistence**: On success, the profile is added to `ProfileStore` (`data/profiles.json`).

### Enable/Disable Flow
1.  **Selection**: Operator selects a profile from the "Installed Profiles" table.
2.  **Action**: Clicks "Enable" or "Disable".
3.  **Execution**: The `LpaCommandService` updates the `ProfileStore` (authoritative source), then sends an `lpac` command to the v-euicc as a best-effort sync.
4.  **Feedback**: A success/error dialog appears, and the table refreshes.

### Data Sync Between GUIs
Both the Developer GUI and MNO Console read from `data/profiles.json`. Changes made in one GUI are reflected in the other (with a slight delay based on auto-refresh intervals).

## Running the Application

```bash
./run-mno.sh
```

This script:
1. Clears stale session databases (`rm -f pysim/sm-dp-sessions*`).
2. Starts backend services with the `-m` (in-memory) flag for clean state.
3. Launches the MNO Console GUI.

### Tab Overview
- **Dashboard**: Server stats auto-refresh every 4 seconds.
- **Profile Inventory**: Upload/delete operations immediately call the SM-DP+ REST API.
- **Active Sessions**: Auto-refresh every 2 seconds.
- **EID History**: Manual refresh (data grows large over time).
- **Device Control**: Auto-refresh device state every 3 seconds, logs persist across operations.

---

**[← Previous: Dev GUI](06-GUI-CONTROL-CENTER.md)** | **[Index](README.md)** | **[Next: Demo Script →](08-DEMO-SCRIPT.md)**
