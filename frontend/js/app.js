/**
 * ESP32-CAM Gallery Frontend Application
 * Pure vanilla JavaScript SPA that calls the backend REST API
 */

// 前端与 API 由同一台服务器提供，使用同源相对地址。
const API_BASE_URL = '';
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

function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
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
            
            document.getElementById('pending-commands').textContent = stats.pending_commands;
            document.getElementById('esp32-status').textContent =
                stats.device_online ? '✅ 在线' : '❌ 离线';
            document.getElementById('device-last-seen').textContent =
                stats.device_last_seen
                    ? formatDate(stats.device_last_seen)
                    : '尚未连接';
            
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
        }
    } catch (error) {
        showToast('加载图片失败: ' + error.message, 'error');
        console.error('Failed to load images:', error);
        
        // Show error state
        const grid = document.getElementById('image-grid');
        grid.innerHTML = `
            <div class="empty-state">
                <div class="icon">⚠️</div>
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
                <div class="icon">📷</div>
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
            <a class="btn-download" href="${API_BASE_URL}/download/${encodeURIComponent(img.filename)}" title="下载照片">↓</a>
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
                        <div class="icon">📷</div>
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
    const captureButton = document.getElementById('capture-button');
    captureButton.disabled = true;

    try {
        showToast('正在创建拍照命令...', 'info');
        
        const data = await apiRequest('/trigger', { method: 'POST' });
        
        if (data.status === 'ok') {
            showToast('拍照命令已排队，等待设备领取...', 'success');
            await waitForCommand(data.command.id);
        } else {
            showToast(data.message || '触发失败', 'error');
        }
    } catch (error) {
        showToast('触发失败: ' + error.message, 'error');
    } finally {
        captureButton.disabled = false;
    }
}

async function waitForCommand(commandId) {
    for (let attempt = 0; attempt < 30; attempt++) {
        await delay(2000);
        const data = await apiRequest(`/api/commands/${encodeURIComponent(commandId)}`);
        const command = data.command;

        if (command.status === 'completed') {
            showToast('拍照完成，照片已上传', 'success');
            await Promise.all([loadImages(), loadStats()]);
            return;
        }
        if (command.status === 'failed') {
            showToast(command.message || '设备拍照失败', 'error');
            await loadStats();
            return;
        }
    }

    showToast('命令仍在等待设备，可稍后刷新查看', 'info');
    await loadStats();
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
