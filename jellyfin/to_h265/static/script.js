// H.265 Encoder Dashboard JavaScript

// Load settings from localStorage
const scanPathInput = document.getElementById('scanPath');
const presetSelect = document.getElementById('preset');
const crfInput = document.getElementById('crf');

if (localStorage.getItem('scanPath')) scanPathInput.value = localStorage.getItem('scanPath');
if (localStorage.getItem('preset')) presetSelect.value = localStorage.getItem('preset');
if (localStorage.getItem('crf')) crfInput.value = localStorage.getItem('crf');

scanPathInput.addEventListener('change', (e) => localStorage.setItem('scanPath', e.target.value));
presetSelect.addEventListener('change', (e) => localStorage.setItem('preset', e.target.value));
crfInput.addEventListener('change', (e) => localStorage.setItem('crf', e.target.value));

// Helper for duration formatting
function formatDuration(seconds) {
	if (!seconds) return "00:00:00";
	const h = Math.floor(seconds / 3600);
	const m = Math.floor((seconds % 3600) / 60);
	const s = Math.floor(seconds % 60);
	return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

// Helper for file size formatting
function formatSize(bytes) {
	const mb = bytes / (1024 * 1024);
	if (mb >= 1024) {
		return `${(mb / 1024).toFixed(2)} GB`;
	}
	return `${mb.toFixed(1)} MB`;
}

// ==================== API Calls ====================

async function triggerScan() {
	const path = scanPathInput.value;
	const btn = document.querySelector('button[onclick="triggerScan()"]');
	const origText = btn.innerText;

	try {
		btn.innerText = "Scanning...";
		btn.disabled = true;

		const res = await fetch(`/scan?directory=${encodeURIComponent(path)}`, { method: 'POST' });
		const data = await res.json();

		alert(`Scan complete. Found ${data.new_files} new files.`);
		updateTable();
	} catch (e) {
		alert("Scan failed: " + e);
	} finally {
		btn.innerText = origText;
		btn.disabled = false;
	}
}

async function queueVideo(id) {
	try {
		const crf = crfInput.value;
		const preset = presetSelect.value;

		const formData = new URLSearchParams();
		formData.append('crf', crf);
		formData.append('preset', preset);

		await fetch(`/queue/${id}`, {
			method: 'POST',
			body: formData
		});
		updateTable();
	} catch (e) { console.error(e); }
}

async function stopVideo(id) {
	if (!confirm("Stop this job? This will delete the partial file.")) return;
	try {
		await fetch(`/jobs/stop/${id}`, { method: 'POST' });
		updateTable();
	} catch (e) { console.error(e); }
}

async function pauseVideo(id) {
	try {
		await fetch(`/jobs/pause/${id}`, { method: 'POST' });
		updateTable();
	} catch (e) { console.error(e); }
}

async function resumeVideo(id) {
	try {
		await fetch(`/jobs/resume/${id}`, { method: 'POST' });
		updateTable();
	} catch (e) { console.error(e); }
}

async function registerWorker(e) {
	e.preventDefault();
	const form = e.target;
	const formData = new FormData(form);
	const params = new URLSearchParams(formData);

	try {
		const res = await fetch('/workers', { method: 'POST', body: params });
		const data = await res.json();
		alert(data.message);
		if (res.ok) window.location.reload();
	} catch (e) {
		alert("Error: " + e);
	}
}

async function deleteVideo(id) {
	if (!confirm("Remove this video from the queue? The actual file will not be deleted.")) return;
	try {
		await fetch(`/videos/${id}`, { method: 'DELETE' });
		updateTable();
	} catch (e) { console.error(e); }
}

// ==================== Rendering Functions ====================

function renderStatusBadge(status) {
	const statusClass = `status-${status}`;
	const label = status.charAt(0).toUpperCase() + status.slice(1);
	return `<span class="status-badge ${statusClass}">${label}</span>`;
}

function renderActions(video) {
	const deleteBtn = `
        <button onclick="deleteVideo(${video.id})" class="action-btn delete" title="Remove from list">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd" />
            </svg>
        </button>
    `;

	if (['pending', 'error', 'completed'].includes(video.status)) {
		return `
            <button onclick="queueVideo(${video.id})" class="action-btn queue">Queue</button>
            ${deleteBtn}
        `;
	} else if (video.status === 'queued') {
		return `<button onclick="stopVideo(${video.id})" class="action-btn cancel">Cancel</button>`;
	} else if (video.status === 'processing') {
		return `
            <button onclick="pauseVideo(${video.id})" class="action-btn pause">Pause</button>
            <button onclick="stopVideo(${video.id})" class="action-btn stop">Stop</button>
        `;
	} else if (video.status === 'paused') {
		return `
            <button onclick="resumeVideo(${video.id})" class="action-btn resume">Resume</button>
            <button onclick="stopVideo(${video.id})" class="action-btn stop">Stop</button>
        `;
	}
	return '';
}

function renderProgressCell(video) {
	const isActive = ['processing', 'paused', 'completed'].includes(video.status);
	const barClass = video.status === 'completed' ? 'completed' : '';

	let statsHtml = '';
	if (isActive && (video.fps > 0 || video.frames_processed > 0)) {
		const parts = [];
		if (video.fps > 0) parts.push(`${video.fps.toFixed(1)} fps`);
		if (video.elapsed && video.elapsed !== '00:00:00') parts.push(video.elapsed);
		if (parts.length > 0) {
			statsHtml = `<div class="progress-stats">${parts.join(' · ')}</div>`;
		}
	}

	return `
        <div class="progress-container">
            <div class="progress-bar-wrapper">
                <div class="progress-bar ${barClass}" style="width: ${video.progress_pct}%"></div>
            </div>
            <div class="progress-info">
                <span class="progress-pct">${video.progress_pct.toFixed(1)}%</span>
                ${video.worker_name ? `<span class="progress-worker">${video.worker_name}</span>` : ''}
            </div>
            ${statsHtml}
        </div>
    `;
}

// ==================== Table Update ====================

async function updateTable() {
	try {
		const res = await fetch('/api/state');
		const state = await res.json();
		const { videos, jobs, workers } = state;

		// Update System Status
		const statusEl = document.getElementById('system-status');
		if (statusEl) {
			statusEl.innerHTML = '<span class="status-dot"></span><span>Online</span>';
		}

		// Create lookup maps
		const workerMap = {};
		workers.forEach(w => workerMap[w.id] = w);

		// Merge video and job data
		const videoData = videos.map(v => {
			const activeJob = jobs.find(j =>
				j.video_id === v.id &&
				['queued', 'processing', 'paused'].includes(j.status)
			);

			const merged = {
				...v,
				progress_pct: 0.0,
				fps: 0.0,
				frames_processed: 0,
				worker_id: null,
				worker_name: null,
				elapsed: '00:00:00'
			};

			if (activeJob) {
				merged.status = activeJob.status;
				merged.progress_pct = activeJob.progress_pct;
				merged.fps = activeJob.fps;
				merged.frames_processed = activeJob.frames_processed;
				merged.worker_id = activeJob.worker_id;

				// Elapsed time
				if (activeJob.started_at) {
					const start = new Date(activeJob.started_at);
					const now = activeJob.completed_at ? new Date(activeJob.completed_at) : new Date();
					const delta = Math.floor((now - start) / 1000);
					const h = Math.floor(delta / 3600);
					const m = Math.floor((delta % 3600) / 60);
					const s = delta % 60;
					merged.elapsed = `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
				}

				// Worker name
				if (activeJob.worker_id && workerMap[activeJob.worker_id]) {
					merged.worker_name = workerMap[activeJob.worker_id].name;
				}
			}

			return merged;
		});

		// Sort: Processing first, then Queued, then Paused, then Pending, then Error, then Completed
		const statusOrder = { 'processing': 0, 'queued': 1, 'paused': 2, 'pending': 3, 'error': 4, 'completed': 5 };
		videoData.sort((a, b) => (statusOrder[a.status] ?? 99) - (statusOrder[b.status] ?? 99));

		// Update queue count
		document.getElementById('queue-count').innerText = `${videoData.length} items`;

		// Render table
		const tbody = document.getElementById('videoTableBody');

		if (videoData.length === 0) {
			tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="empty-state">
                        <svg class="empty-state-icon" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z" />
                        </svg>
                        <p>No videos in queue</p>
                        <p style="font-size: 0.75rem; margin-top: 8px;">Scan a directory to add videos</p>
                    </td>
                </tr>
            `;
		} else {
			tbody.innerHTML = videoData.map(v => `
                <tr>
                    <td class="col-file">
                        <div class="file-name" title="${v.filename}">${v.filename}</div>
                        <div class="file-path" title="${v.path}">${v.path}</div>
                    </td>
                    <td class="col-size">${formatSize(v.size)}</td>
                    <td class="col-duration">${formatDuration(v.duration)}</td>
                    <td>${renderStatusBadge(v.status)}</td>
                    <td class="col-progress">${renderProgressCell(v)}</td>
                    <td class="col-actions">${renderActions(v)}</td>
                </tr>
            `).join('');
		}

		// Update Worker Status Dots
		workers.forEach(w => {
			const dot = document.getElementById(`worker-status-${w.id}`);
			if (dot) {
				dot.className = `worker-status-dot ${w.is_online ? 'online' : 'offline'}`;
				dot.title = w.is_online ? 'Online' : 'Offline';
			}
			// Also update card border color
			const card = document.getElementById(`worker-${w.id}`);
			if (card) {
				card.className = `worker-card ${w.is_online ? 'online' : 'offline'}`;
			}
		});

	} catch (e) {
		console.error("Poll failed", e);
		// Update System Status to Offline
		const statusEl = document.getElementById('system-status');
		if (statusEl) {
			statusEl.innerHTML = '<span class="status-dot offline"></span><span>Offline</span>';
		}
	}
}

// ==================== Worker Management ====================

async function toggleWorker(id) {
	try {
		await fetch(`/workers/${id}/toggle`, { method: 'POST' });
		window.location.reload();
	} catch (e) { alert(e); }
}

async function deleteWorker(id) {
	if (!confirm("Are you sure you want to delete this worker?")) return;
	try {
		await fetch(`/workers/${id}`, { method: 'DELETE' });
		window.location.reload();
	} catch (e) { alert(e); }
}

// ==================== Edit Modal ====================

function openEditModal(id, name, ip, port, threads) {
	document.getElementById('edit_id').value = id;
	document.getElementById('edit_name').value = name;
	document.getElementById('edit_ip').value = ip;
	document.getElementById('edit_port').value = port;
	document.getElementById('edit_threads').value = threads;
	document.getElementById('editModal').classList.add('active');
}

function closeEditModal() {
	document.getElementById('editModal').classList.remove('active');
}

async function submitEditWorker(e) {
	e.preventDefault();
	const id = document.getElementById('edit_id').value;
	const formData = new FormData(e.target);
	const params = new URLSearchParams(formData);

	try {
		const res = await fetch(`/workers/${id}`, { method: 'PUT', body: params });
		if (res.ok) {
			window.location.reload();
		} else {
			const d = await res.json();
			alert("Error: " + d.detail);
		}
	} catch (e) { alert(e); }
}

// Close modal on overlay click
document.getElementById('editModal').addEventListener('click', (e) => {
	if (e.target.id === 'editModal') {
		closeEditModal();
	}
});

// Close modal on Escape key
document.addEventListener('keydown', (e) => {
	if (e.key === 'Escape') {
		closeEditModal();
	}
});

// ==================== Initialization ====================

// Poll every 1 second
setInterval(updateTable, 1000);
updateTable(); // Initial load
