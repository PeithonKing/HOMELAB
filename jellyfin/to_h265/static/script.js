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

async function mergeVideo(id) {
	if (!confirm("Merge this file?\n\nThis will:\n- Delete the original source file\n- Rename this H.265 file to the original's name\n- Remove both entries from the database\n\nThis action cannot be undone!")) return;
	try {
		const res = await fetch(`/videos/${id}/merge`, { method: 'POST' });
		const data = await res.json();
		if (!res.ok) {
			alert("Merge failed: " + (data.detail || "Unknown error"));
		}
		updateTable();
	} catch (e) {
		console.error(e);
		alert("Merge failed: " + e);
	}
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
	// Icon SVGs
	const playIcon = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z"/></svg>`;
	const pauseIcon = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path d="M5.75 3a.75.75 0 00-.75.75v12.5c0 .414.336.75.75.75h1.5a.75.75 0 00.75-.75V3.75A.75.75 0 007.25 3h-1.5zM12.75 3a.75.75 0 00-.75.75v12.5c0 .414.336.75.75.75h1.5a.75.75 0 00.75-.75V3.75a.75.75 0 00-.75-.75h-1.5z"/></svg>`;
	const stopIcon = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path d="M5.25 3A2.25 2.25 0 003 5.25v9.5A2.25 2.25 0 005.25 17h9.5A2.25 2.25 0 0017 14.75v-9.5A2.25 2.25 0 0014.75 3h-9.5z"/></svg>`;
	const deleteIcon = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>`;
	const cancelIcon = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z"/></svg>`;

	const deleteBtn = `<button onclick="deleteVideo(${video.id})" class="action-btn delete" title="Remove from list">${deleteIcon}</button>`;

	if (['pending', 'error', 'completed'].includes(video.status)) {
		return `
			<button onclick="queueVideo(${video.id})" class="action-btn queue" title="Queue for encoding">${playIcon}</button>
			${deleteBtn}
		`;
	} else if (video.status === 'queued') {
		return `<button onclick="stopVideo(${video.id})" class="action-btn cancel" title="Cancel">${cancelIcon}</button>`;
	} else if (video.status === 'processing') {
		return `
			<button onclick="pauseVideo(${video.id})" class="action-btn pause" title="Pause">${pauseIcon}</button>
			<button onclick="stopVideo(${video.id})" class="action-btn stop" title="Stop">${stopIcon}</button>
		`;
	} else if (video.status === 'paused') {
		return `
			<button onclick="resumeVideo(${video.id})" class="action-btn resume" title="Resume">${playIcon}</button>
			<button onclick="stopVideo(${video.id})" class="action-btn stop" title="Stop">${stopIcon}</button>
		`;
	}
	return '';
}

function renderProgressCell(video) {
	const isActive = ['processing', 'paused', 'completed'].includes(video.status);
	const barClass = video.status === 'completed' ? 'completed' : '';

	// Worker name above progress bar (only for active)
	const workerHtml = video.worker_name ? `<div class="progress-worker">${video.worker_name}</div>` : '';

	// FPS display (right side)
	const fpsHtml = (isActive && video.fps > 0) ? `<span class="progress-fps">${video.fps.toFixed(1)} fps</span>` : '';

	return `
		<div class="progress-container">
			${workerHtml}
			<div class="progress-bar-wrapper">
				<div class="progress-bar ${barClass}" style="width: ${video.progress_pct}%"></div>
			</div>
			<div class="progress-info">
				<span class="progress-pct">
					${video.progress_pct.toFixed(1)}%
					${video.frames > 0 ? `<span class="progress-frames">(${video.frames_processed} / ${video.frames})</span>` : ''}
				</span>
				${fpsHtml}
			</div>
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
					const start = activeJob.started_at;
					const now = activeJob.completed_at ? activeJob.completed_at : Math.floor(Date.now() / 1000);
					const delta = Math.max(0, now - start); // Ensure no negative values
					const h = Math.floor(delta / 3600);
					const m = Math.floor((delta % 3600) / 60);
					const s = delta % 60;
					merged.elapsed = `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
				}

				// ETA Calculation
				if (activeJob.status === 'processing' && activeJob.fps > 0 && merged.frames > 0) {
					const remainingFrames = Math.max(0, merged.frames - activeJob.frames_processed);
					const etaSeconds = remainingFrames / activeJob.fps;
					const h = Math.floor(etaSeconds / 3600);
					const m = Math.floor((etaSeconds % 3600) / 60);
					const s = Math.floor(etaSeconds % 60);
					merged.eta = `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;

					// Wall time calculation
					const wallTime = new Date(Date.now() + etaSeconds * 1000);
					const wallHours = wallTime.getHours();
					const wallMins = wallTime.getMinutes().toString().padStart(2, '0');
					const ampm = wallHours >= 12 ? 'PM' : 'AM';
					const displayHours = wallHours % 12 || 12;
					merged.eta_wall = `${displayHours}:${wallMins} ${ampm}`;
				}

				// Worker name
				if (activeJob.worker_id && workerMap[activeJob.worker_id]) {
					merged.worker_name = workerMap[activeJob.worker_id].name;
				}
			}

			return merged;
		});


		// Identify processed source videos (those referenced as 'orig' by others)
		const processedVideoIds = new Set(videoData.map(v => v.orig).filter(id => id != null));


		// Create video map for looking up originals
		const videoMap = {};
		videoData.forEach(v => { videoMap[v.id] = v; });

		// Categorize videos into sections
		const activeVideos = videoData.filter(v => ['processing', 'queued', 'paused'].includes(v.status));
		const pendingVideos = videoData.filter(v => v.status === 'pending' && !processedVideoIds.has(v.id));
		const completedVideos = videoData.filter(v => v.status === 'completed' && v.codec === 'hevc');
		// Error videos go to pending for re-queueing
		const errorVideos = videoData.filter(v => v.status === 'error');
		pendingVideos.push(...errorVideos);

		// Sort active: processing first, then paused, then queued
		const activeOrder = { 'processing': 0, 'paused': 1, 'queued': 2 };
		activeVideos.sort((a, b) => (activeOrder[a.status] ?? 99) - (activeOrder[b.status] ?? 99));

		// Update queue count (total)
		document.getElementById('queue-count').innerText = `${videoData.length} items`;

		// Update section counts
		document.getElementById('count-active').innerText = activeVideos.length;
		document.getElementById('count-pending').innerText = pendingVideos.length;
		document.getElementById('count-completed').innerText = completedVideos.length;

		// Render each section
		updateSection('active', activeVideos, videoMap);
		updateSection('pending', pendingVideos, videoMap);
		updateSection('completed', completedVideos, videoMap);

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

// Helper: Update a specific section's table body with in-place row updates
function updateSection(sectionName, videos, videoMap) {
	const tbody = document.getElementById(`tableBody-${sectionName}`);
	if (!tbody) return;

	const isActiveSection = sectionName === 'active';
	const isCompletedSection = sectionName === 'completed';
	const newVideoIds = new Set(videos.map(v => v.id));

	// Remove rows for videos no longer in this section
	const existingRows = tbody.querySelectorAll('tr[id^="video-row-"]');
	existingRows.forEach(row => {
		const rowId = parseInt(row.id.replace('video-row-', ''), 10);
		if (!newVideoIds.has(rowId)) {
			row.remove();
		}
	});

	// Update or create rows
	videos.forEach((v, index) => {
		const rowId = `video-row-${v.id}`;
		let row = document.getElementById(rowId);

		if (row) {
			// Move row to this section if it's elsewhere
			if (row.parentElement !== tbody) {
				row.remove();
				row = null; // Force recreation in this tbody
			}
		}

		// Get original file info for completed section
		let origFile = null;
		if (isCompletedSection && v.orig && videoMap) {
			origFile = videoMap[v.orig];
		}

		if (row) {
			// Update dynamic cells
			const cells = row.querySelectorAll('td');
			if (isActiveSection) {
				// Active: File, Duration, Progress, Elapsed, ETA, Actions
				cells[2].innerHTML = renderProgressCell(v);
				cells[3].innerHTML = v.elapsed || '--:--:--';
				cells[4].innerHTML = v.eta ? `${v.eta}<span class="eta-wall">${v.eta_wall || ''}</span>` : '--:--:--';
				cells[5].innerHTML = renderActions(v);
			} else if (isCompletedSection) {
				// Completed: File, Original, Duration, Actions
				if (origFile) {
					cells[1].innerHTML = `<span class="orig-link" title="${origFile.path}">${origFile.filename}</span>`;
				} else {
					cells[1].innerHTML = '-';
				}
				// cells[2] is duration - no update needed
				cells[3].innerHTML = `<button class="btn btn-sm btn-merge" onclick="mergeVideo(${v.id})" title="Merge: Delete original, rename this file">
					<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M17 3a2.85 2.85 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/>
					</svg>
					Merge
				</button>`;
			} else {
				// Pending: File, Duration, Progress, Actions
				cells[2].innerHTML = renderProgressCell(v);
				cells[3].innerHTML = renderActions(v);
			}
		} else {
			// Create new row
			row = document.createElement('tr');
			row.id = rowId;

			if (isActiveSection) {
				row.innerHTML = `
					<td class="col-file">
						<div class="file-name" title="${v.path}">${v.filename}</div>
						<div class="file-size">${formatSize(v.size)}</div>
					</td>
					<td class="col-duration">${formatDuration(v.duration)}</td>
					<td class="col-progress">${renderProgressCell(v)}</td>
					<td class="col-elapsed">${v.elapsed || '--:--:--'}</td>
					<td class="col-eta">${v.eta ? `${v.eta}<span class="eta-wall">${v.eta_wall || ''}</span>` : '--:--:--'}</td>
					<td class="col-actions">${renderActions(v)}</td>
				`;
			} else if (isCompletedSection) {
				const origHtml = origFile ? `<span class="orig-link" title="${origFile.path}">${origFile.filename}</span>` : '-';
				const mergeBtn = `<button class="btn btn-sm btn-merge" onclick="mergeVideo(${v.id})" title="Merge: Delete original, rename this file">
					<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M17 3a2.85 2.85 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/>
					</svg>
					Merge
				</button>`;
				row.innerHTML = `
					<td class="col-file">
						<div class="file-name" title="${v.path}">${v.filename}</div>
						<div class="file-size">${formatSize(v.size)}</div>
					</td>
					<td class="col-orig">${origHtml}</td>
					<td class="col-duration">${formatDuration(v.duration)}</td>
					<td class="col-actions">${mergeBtn}</td>
				`;
			} else {
				row.innerHTML = `
					<td class="col-file">
						<div class="file-name" title="${v.path}">${v.filename}</div>
						<div class="file-size">${formatSize(v.size)}</div>
					</td>
					<td class="col-duration">${formatDuration(v.duration)}</td>
					<td class="col-progress">${renderProgressCell(v)}</td>
					<td class="col-actions">${renderActions(v)}</td>
				`;
			}
			tbody.appendChild(row);
		}

		// Ensure correct order
		const currentRowAtIndex = tbody.children[index];
		if (currentRowAtIndex !== row) {
			tbody.insertBefore(row, currentRowAtIndex);
		}
	});
}

// Toggle collapsible section
function toggleSection(sectionName) {
	const section = document.getElementById(`section-${sectionName}`);
	if (section) {
		section.classList.toggle('collapsed');
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
