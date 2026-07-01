/**
 * ESP32-CAM Gallery Frontend Application
 * Pure vanilla JavaScript SPA that calls the backend REST API
 */

// Configuration - Change this to match your backend server
const API_BASE_URL = 'http://localhost:5000';
const REFRESH_INTERVAL = 10000; // 10 seconds

// State
let refreshTimer = null;
let isLoading = false;

// ============================================
// Toast Notifications
// ============================================

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = 'toast show';
    
    if (type === 'error') {
        toast.classList.add('error');
    } else if (type === 'success') {
        toast.classList.add('success');
    }
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// ============================================
// Utility Functions
// ============================================

function formatSize(bytes) {
    if (bytes === 0) return '0B';
    if (bytes < 1024) return bytes + 'B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB';
    return (bytes / (1024 * 1024)).toFixed(2) + 'MB';
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    }).replace(/\//g, '-');
}

async function apiRequest(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    try {
        const response = await fetch(url, {
            ...options,
            mode: 'cors'
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
            return await response.json();
        }
        return response;
    } catch (error) {
        console.error(`API request failed: ${endpoint}`, error);
        throw error;
    }
}

// ============================================
// Data Loading Functions
// ============================================

async function loadStats() {
    try {
        const data = await apiRequest('/api/stats');
        
        if (data.status === 'ok') {
            const stats = data.stats;
            
            // Update stats display
            document.getElementById('processed-count').textContent = stats.processed_count;
            document.getElementById('raw-count').textContent = stats.raw_count;
            document.getElementById('total-size').textContent = formatSize(stats.total_size);
            document.getElementById('photo-count').textContent = stats.processed_count;
            
            // Update ESP32 status
            if (stats.esp32_configured) {
                document.getElementById('esp32-status').textContent = '已连接';
            const dot = document.querySelector('.status-dot');
            if (dot) { dot.classList.remove('status-dot--offline'); dot.classList.add('status-dot--online'); }
            const sText = document.getElementById('sidebar-status-text');
            if (sText) sText.textContent = 'ESP32 已连接';
                
                // Show ESP32 stream card
                const esp32Card = document.getElementById('esp32-card');
                if (stats.esp32_url) {
                    const streamUrl = stats.esp32_url.replace('/capture', '/stream');
                    const baseUrl = stats.esp32_url.replace('/capture', '/');
                    
                    document.getElementById('esp32-stream').src = streamUrl;
                    document.getElementById('esp32-fullscreen').href = baseUrl;
                    esp32Card.style.display = 'block';
                }
            } else {
                document.getElementById('esp32-status').textContent = '未配置';
            const dot = document.querySelector('.status-dot');
            if (dot) { dot.classList.remove('status-dot--online'); dot.classList.add('status-dot--offline'); }
            const sText = document.getElementById('sidebar-status-text');
            if (sText) sText.textContent = '未连接';
                document.getElementById('esp32-card').style.display = 'none';
            }
            
            return stats;
        }
    } catch (error) {
        showToast('加载统计失败: ' + error.message, 'error');
        console.error('Failed to load stats:', error);
    }
}

async function loadImages() {
    if (isLoading) return;
    isLoading = true;
    
    try {
        const data = await apiRequest('/api/images');
        
        if (data.status === 'ok') {
            renderImageGrid(data.images);
            const sub = document.getElementById('topbar-sub');
            if (sub) sub.textContent = '共 ' + data.images.length + ' 张照片';
        }
    } catch (error) {
        showToast('加载图片失败: ' + error.message, 'error');
        console.error('Failed to load images:', error);
        
        // Show error state
        const grid = document.getElementById('image-grid');
        grid.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon"><svg viewBox="0 0 24 24" width="40" height="40" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg></div>
                <p>无法连接到后端服务器 (${API_BASE_URL})</p>
            </div>
        `;
    } finally {
        isLoading = false;
    }
}

// ============================================
// Rendering Functions
// ============================================

function renderImageGrid(images) {
    const grid = document.getElementById('image-grid');
    
    if (!images || images.length === 0) {
        grid.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon"><svg viewBox="0 0 24 24" width="40" height="40" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg></div>
                <p>暂无照片，等待 ESP32 拍照上传...</p>
            </div>
        `;
        return;
    }
    
    grid.innerHTML = images.map(img => `
        <div class="image-card" data-filename="${img.filename}">
            <a href="${API_BASE_URL}${img.url}" target="_blank" class="image-link">
                <img src="${API_BASE_URL}${img.url}" loading="lazy" alt="${img.filename}">
            </a>
            <div class="image-info">
                <span class="image-time">${formatDate(img.created)}</span>
                <span class="image-size">${formatSize(img.size)}</span>
            </div>
            <button class="btn-delete" onclick="deleteImage('${img.filename}')" title="删除">×</button>
        </div>
    `).join('');
}

// ============================================
// Action Functions
// ============================================

async function deleteImage(filename) {
    if (!confirm('确定要删除这张图片吗？')) return;
    
    try {
        const data = await apiRequest(`/api/image/${encodeURIComponent(filename)}`, {
            method: 'DELETE'
        });
        
        if (data.status === 'ok') {
            showToast('删除成功', 'success');
            
            // Remove the card from DOM
            const card = document.querySelector(`[data-filename="${filename}"]`);
            if (card) {
                card.style.transition = 'opacity 0.3s, transform 0.3s';
                card.style.opacity = '0';
                card.style.transform = 'scale(0.8)';
                setTimeout(() => card.remove(), 300);
            }
            
            // Update count
            const countEl = document.getElementById('photo-count');
            const currentCount = parseInt(countEl.textContent) || 0;
            countEl.textContent = Math.max(0, currentCount - 1);
            
            // Also update processed count
            const processedEl = document.getElementById('processed-count');
            processedEl.textContent = Math.max(0, parseInt(processedEl.textContent) - 1);
            
            // Check if grid is now empty
            const grid = document.getElementById('image-grid');
            if (grid.querySelectorAll('.image-card').length === 0) {
                grid.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-icon"><svg viewBox="0 0 24 24" width="40" height="40" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg></div>
                        <p>暂无照片，等待 ESP32 拍照上传...</p>
                    </div>
                `;
            }
        } else {
            showToast(data.message || '删除失败', 'error');
        }
    } catch (error) {
        showToast('删除失败: ' + error.message, 'error');
    }
}

async function triggerCapture() {
    try {
        showToast('正在触发拍照...', 'info');
        
        const data = await apiRequest('/trigger');
        
        if (data.status === 'ok') {
            showToast('拍照已触发，等待图片上传...', 'success');
            
            // Refresh images after a short delay
            setTimeout(() => {
                loadImages();
                loadStats();
            }, 2000);
        } else {
            showToast(data.message || '触发失败', 'error');
        }
    } catch (error) {
        showToast('触发失败: ' + error.message, 'error');
    }
}

// ============================================
// Auto-refresh
// ============================================

function startAutoRefresh() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
    }
    
    refreshTimer = setInterval(() => {
        loadImages();
        loadStats();
    }, REFRESH_INTERVAL);
}

function stopAutoRefresh() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
        refreshTimer = null;
    }
}

// ============================================
// Initialization
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    console.log('ESP32-CAM Gallery Frontend initialized');
    console.log('API Base URL:', API_BASE_URL);
    
    // Initial load
    loadStats();
    loadImages();
    
    // Start auto-refresh
    startAutoRefresh();
    
    // Handle visibility change to pause/resume refresh
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            stopAutoRefresh();
        } else {
            loadImages();
            loadStats();
            startAutoRefresh();
        }
    });
});

// Expose functions globally for onclick handlers
window.deleteImage = deleteImage;
window.triggerCapture = triggerCapture;
window.loadStats = loadStats;
window.loadImages = loadImages;


