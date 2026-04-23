document.addEventListener("DOMContentLoaded", () => {
    
    // --- 1. Session Timer Logic ---
    let seconds = 0;
    const timerElement = document.getElementById('sessionTimer');
    
    function updateTimer() {
        seconds++;
        const mins = Math.floor(seconds / 60).toString().padStart(2, '0');
        const secs = (seconds % 60).toString().padStart(2, '0');
        if (timerElement) timerElement.textContent = `${mins}:${secs}`;
    }
    setInterval(updateTimer, 1000);

    // --- Matplotlib Image Refresh Logic ---
    function refreshChartImage() {
        const img = document.getElementById('moodChartImg');
        if (img) {
            img.src = "/chart-image/?t=" + new Date().getTime();
        }
    }

    // --- 3. Mock Real-time Data Fetching ---
    // In a real app, this would hit an endpoint that returns the *current* emotion from the DB.
    // For now, we simulate the "Live" feel by updating stats based on the static API data
    // plus some random variation to make it look alive.

    function fetchData() {
        fetch('/api/chart-data/')
            .then(response => response.json())
            .then(data => {
                // Update Avg Stress
                const avgStressEl = document.getElementById('avgStress');
                if (avgStressEl) {
                    let avgStress;
                    if (data.stress_levels && data.stress_levels.length > 0) {
                        avgStress = Math.round(data.stress_levels.reduce((a, b) => a + b, 0) / data.stress_levels.length);
                    } else {
                        avgStress = 0; // Default to 0 if no stress data
                    }
                    
                    avgStressEl.textContent = `${avgStress}%`;
                    avgStressEl.className = avgStress > 50 ? "fs-2 text-warning fw-bold" : "fs-2 text-white fw-bold";
                }

                // Dominant Mood Logic
                const dominantMoodEl = document.getElementById('dominantMood');
                if (dominantMoodEl) {
                    dominantMoodEl.textContent = data.dominant_mood || "Waiting..."; 
                }
                
                // Update Emotion Badge 
                const badge = document.getElementById('emotionBadge');
                if (badge && data.dominant_mood) {
                    badge.className = `emotion-display ${data.dominant_mood}`;
                    badge.innerHTML = `<i class="bi bi-emoji-smile me-2"></i><span>${data.dominant_mood}</span>`;
                }

                // Refresh the static chart image
                refreshChartImage();
            })
            .catch(err => console.error("Error loading data:", err));
    }

    // Load chart once on page load (no automatic polling)
    fetchData();

    // Chart polling - ONLY when camera is on; no requests when idle
    let chartInterval = null;

    // Start Camera Button Logic
    const startBtn = document.getElementById('startCameraBtn');
    const stopBtn = document.getElementById('stopCameraBtn');
    const placeholder = document.getElementById('cameraPlaceholder');
    const videoFeed = document.getElementById('videoFeed');
    const scanLine = document.getElementById('scanLine');

    if (startBtn) {
        startBtn.addEventListener('click', function() {
            // Hide placeholder
            placeholder.classList.add('d-none');
            
            // Show video and start stream
            videoFeed.classList.remove('d-none');
            videoFeed.src = "/video_feed/"; 
            
            // Show scan line and Stop button
            scanLine.classList.remove('d-none');
            stopBtn.classList.remove('d-none');

            // Start chart polling (every 5 sec) when camera is on
            if (chartInterval) clearInterval(chartInterval);
            chartInterval = setInterval(fetchData, 5000);
        });
    }

    if (stopBtn) {
        stopBtn.addEventListener('click', function() {
            // Show placeholder and hide controls
            placeholder.classList.remove('d-none');
            stopBtn.classList.add('d-none');
            
            // Hide video and stop stream - this aborts the /video_feed/ request
            videoFeed.classList.add('d-none');
            videoFeed.src = "";
            scanLine.classList.add('d-none');

            // Stop chart polling - terminal goes quiet when camera is off
            if (chartInterval) {
                clearInterval(chartInterval);
                chartInterval = null;
            }
        });
    }
});