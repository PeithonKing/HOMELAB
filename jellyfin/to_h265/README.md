# Distributed H.265 Media Converter

A project to efficiently convert a large media library to H.265 (HEVC), significantly reducing storage usage while maintaining quality.

## Motivation
After realizing how much more efficient H.265 is compared to older codecs like H.264, and facing storage limitations on the main server, migrating the library became a priority. Converting terabytes of video is computationally expensive and would take months on a single low-power server (like a Raspberry Pi).

This tool solves that problem by providing a streamlined, distributed way to manage the conversion process.

## How it Works
The system uses a **Master-Slave (Manager-Worker) architecture**:

*   **Master (Manager):** Runs on the storage server (e.g., Raspberry Pi). It scans the library, manages the database of files, tracks progress, serves the web dashboard, and dispatches jobs.
*   **Slaves (Workers):** Run on powerful desktop PCs or other available hardware. They request jobs from the master, perform the CPU-intensive encoding using FFmpeg, and report status back.

## Status
**Current State:** Usable Alpha. 
While functional, the project is a work in progress. Major UI updates and optimizations are planned.

## Architecture 
See [imp_plan.md](imp_plan.md) for the detailed implementation plan and technical architecture.
