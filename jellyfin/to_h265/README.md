# Distributed H.265 Media Converter

A project to efficiently convert a large media library to H.265 (HEVC), significantly reducing storage usage while maintaining quality.

## Motivation
After realizing how much more efficient H.265 is compared to older codecs like H.264, and facing storage limitations on the main server, migrating the library became a priority. Converting terabytes of video is computationally expensive and would take months on a single low-power server (like a Raspberry Pi).

This tool solves that problem by providing a streamlined, distributed way to manage the conversion process.

## How it Works
The system uses a **Master-Slave (Manager-Worker) architecture**:

*   **Manager:** Runs on the storage server (e.g., Raspberry Pi). It scans the library, manages the database of files, tracks progress, serves the web dashboard, and dispatches jobs.
*   **Workers:** Run on powerful desktop PCs or other available hardware. They request jobs from the master, perform the CPU-intensive encoding using FFmpeg, and report status back.

## Installation

### Prerequisites
-   Python 3.10+
-   FFmpeg and ffprobe (installed on both Manager and Worker nodes)
-   The disk containing the media library should be accessible to all the nodes. I used `sshfs` to mount the media directory to all the worker nodes.

### Setup
1.  **Clone the repository** (or actually just copy the `to_h265` directory, u don't need anything else) to all the nodes (Master and Workers). Also technically u don't need the `worker_node.py` file in the master node and the `manager.py` file in the worker nodes, but just keep it, it's simpler that way.
2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Configuration:**
    Copy `.env.example` to `.env` and configure accordingly. The file is self-explanatory.
    ```bash
    cp .env.example .env
    ```
4.  **Start the Manager:**
    Run the following command on the master/storage node:
    ```bash
    uvicorn manager:app --host 0.0.0.0 --port 8000
    ```
    You can now access the dashboard at `http://<master-ip>:8000`.

5.  **Start Worker Nodes:**
    Ensure the media directory is mounted on the worker machine (e.g., using `sshfs`). Then start the worker:
    ```bash
    # Example mounting (if needed)
    # sshfs user@master:/path/to/media /local/mount/point
    
    # Start the worker
    uvicorn worker_node:app --host 0.0.0.0 --port 8001
    ```
    **Note:** If running multiple workers on the same machine (or running a worker on the manager machine), ensure they use different ports (e.g., 8001, 8002).
