/**
 * 设备维修助手 - 前端逻辑
 */

// 页面加载时初始化
document.addEventListener('DOMContentLoaded', function() {
    loadEquipmentList();
});

// 加载设备列表
async function loadEquipmentList() {
    try {
        const response = await fetch('/api/equipment-list');
        const result = await response.json();
        
        if (result.success) {
            const select = document.getElementById('equipmentSelect');
            result.data.forEach(function(item) {
                const option = document.createElement('option');
                option.value = item;
                option.textContent = item;
                select.appendChild(option);
            });
        }
    } catch (error) {
        console.error('加载设备列表失败:', error);
    }
}

// 设备选择变化
function onEquipmentChange() {
    // 预留扩展
}

// 执行搜索
async function doSearch() {
    const query = document.getElementById('queryInput').value.trim();
    const equipment = document.getElementById('equipmentSelect').value;
    const category = document.getElementById('categorySelect').value;
    const searchBtn = document.getElementById('searchBtn');
    const loading = document.getElementById('loading');
    const errorMsg = document.getElementById('errorMsg');
    const resultArea = document.getElementById('resultArea');

    // 隐藏之前的结果
    errorMsg.style.display = 'none';
    resultArea.style.display = 'none';

    // 验证输入
    if (!query && !equipment && !category) {
        showError('请至少填写一项搜索条件（设备名称、故障类别或故障描述）');
        return;
    }

    // 显示加载中
    searchBtn.disabled = true;
    searchBtn.textContent = '⏳ 搜索中...';
    loading.style.display = 'block';

    try {
        const response = await fetch('/api/search', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                query: query,
                equipment: equipment,
                category: category,
                limit: 10
            })
        });

        const result = await response.json();

        if (result.success) {
            displayResults(result);
        } else {
            showError(result.error || '搜索失败，请重试');
        }
    } catch (error) {
        showError('网络错误，请检查连接后重试');
        console.error('搜索请求失败:', error);
    } finally {
        searchBtn.disabled = false;
        searchBtn.textContent = '🔍 搜索维修方案';
        loading.style.display = 'none';
    }
}

// 显示错误信息
function showError(msg) {
    const errorMsg = document.getElementById('errorMsg');
    errorMsg.textContent = '⚠️ ' + msg;
    errorMsg.style.display = 'block';
}

// 显示搜索结果
function displayResults(result) {
    const resultArea = document.getElementById('resultArea');
    const analysisBox = document.getElementById('analysisBox');
    const repeatWarning = document.getElementById('repeatWarning');
    const resultList = document.getElementById('resultList');

    resultArea.style.display = 'block';

    // 显示分析摘要
    if (result.analysis) {
        const analysis = result.analysis;
        let html = '<h3>📊 分析摘要</h3>';

        html += '<div class="stat-item"><span class="stat-label">找到记录</span><span class="stat-value">' + result.total + ' 条</span></div>';

        if (analysis.top_causes && analysis.top_causes.length > 0) {
            html += '<div class="stat-item"><span class="stat-label">常见原因</span><span class="stat-value highlight">' + analysis.top_causes.slice(0, 3).join('、') + '</span></div>';
        }

        if (analysis.top_actions && analysis.top_actions.length > 0) {
            html += '<div class="stat-item"><span class="stat-label">推荐方案</span><span class="stat-value">' + analysis.top_actions.slice(0, 2).join('、') + '</span></div>';
        }

        if (analysis.total_records) {
            html += '<div class="stat-item"><span class="stat-label">数据库总记录</span><span class="stat-value">' + analysis.total_records + ' 条</span></div>';
        }

        analysisBox.innerHTML = html;
    }

    // 显示重复警告
    if (result.analysis && result.analysis.repeat_equipment && result.analysis.repeat_equipment.length > 0) {
        let warningHtml = '<div class="warning-icon">⚠️</div>';
        warningHtml += '<div class="warning-text"><strong>重复发生预警：</strong><br>';
        warningHtml += '以下设备出现过类似故障，建议重点关注：<br>';
        result.analysis.repeat_equipment.forEach(function(item) {
            warningHtml += '🔴 ' + item + '<br>';
        });
        warningHtml += '</div>';
        repeatWarning.innerHTML = warningHtml;
        repeatWarning.style.display = 'flex';
    } else {
        repeatWarning.style.display = 'none';
    }

    // 显示结果列表
    if (result.data && result.data.length > 0) {
        let listHtml = '';
        result.data.forEach(function(item, index) {
            listHtml += buildCard(item, index);
        });
        resultList.innerHTML = listHtml;
    } else {
        resultList.innerHTML = '<div class="no-results"><div class="icon">🔍</div><p>未找到相关维修记录</p><p>请尝试其他关键词搜索</p></div>';
    }

    // 滚动到结果区域
    resultArea.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// 构建结果卡片
function buildCard(item, index) {
    let html = '<div class="result-card">';

    // 卡片头部
    html += '<div class="card-header">';
    html += '<span class="equipment-name">' + escapeHtml(item.设备名称 || '未知设备') + '</span>';
    if (item.relevance_score) {
        html += '<span class="score-badge">匹配 ' + Math.round(item.relevance_score * 100) + '%</span>';
    }
    html += '</div>';

    // 基本信息
    html += '<div class="info-row"><span class="info-label">📂 类别：</span><span class="info-value">' + escapeHtml(item.故障类别 || '-') + '</span></div>';

    // 故障描述
    if (item.故障描述) {
        html += '<div class="section">';
        html += '<div class="section-title">❗ 故障描述</div>';
        html += '<div class="section-content">' + escapeHtml(item.故障描述) + '</div>';
        html += '</div>';
    }

    // 故障原因
    if (item.故障原因) {
        html += '<div class="section">';
        html += '<div class="section-title">🔎 故障原因</div>';
        html += '<div class="section-content">' + escapeHtml(item.故障原因) + '</div>';
        html += '</div>';
    }

    // 维修措施
    if (item.维修措施) {
        html += '<div class="section">';
        html += '<div class="section-title">🛠️ 维修措施</div>';
        html += '<div class="section-content">' + escapeHtml(item.维修措施) + '</div>';
        html += '</div>';
    }

    // 日期信息
    if (item.发生日期 || item.完成日期) {
        html += '<div class="date-info">';
        if (item.发生日期) html += '发生: ' + formatDate(item.发生日期) + ' ';
        if (item.完成日期) html += '| 完成: ' + formatDate(item.完成日期);
        html += '</div>';
    }

    html += '</div>';
    return html;
}

// HTML转义
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
}

// 格式化日期
function formatDate(dateStr) {
    if (!dateStr) return '';
    try {
        // 处理各种日期格式
        const date = new Date(dateStr);
        if (isNaN(date.getTime())) return String(dateStr);
        const y = date.getFullYear();
        const m = String(date.getMonth() + 1).padStart(2, '0');
        const d = String(date.getDate()).padStart(2, '0');
        return y + '-' + m + '-' + d;
    } catch (e) {
        return String(dateStr);
    }
}
