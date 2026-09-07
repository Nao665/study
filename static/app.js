/**
 * Korean Vocab Extractor - Main Client Application Logic
 */

// Application State
const state = {
  currentTab: 'youtube',
  extractedWords: [],
  filteredWords: [],
  videoInfo: null,
  currentLevel: 'intermediate',
  viewMode: 'cards', // 'cards' | 'table'
  activeFilterPos: 'all',
  searchQuery: '',
  hasServerGeminiKey: false,
  hasServerYoutubeKey: false
};

// DOM Elements
const elements = {
  // Tabs
  tabYoutube: document.getElementById('tabYoutube'),
  tabText: document.getElementById('tabText'),
  tabContentYoutube: document.getElementById('tabContentYoutube'),
  tabContentText: document.getElementById('tabContentText'),

  // Inputs
  youtubeUrlInput: document.getElementById('youtubeUrlInput'),
  rawTextInput: document.getElementById('rawTextInput'),
  btnClearUrl: document.getElementById('btnClearUrl'),
  btnPasteUrl: document.getElementById('btnPasteUrl'),
  btnExtract: document.getElementById('btnExtract'),

  // Modal / Settings
  btnOpenSettings: document.getElementById('btnOpenSettings'),
  btnCloseSettings: document.getElementById('btnCloseSettings'),
  settingsModal: document.getElementById('settingsModal'),
  inputGeminiKey: document.getElementById('inputGeminiKey'),
  inputYoutubeKey: document.getElementById('inputYoutubeKey'),
  btnSaveSettings: document.getElementById('btnSaveSettings'),
  apiKeyBadge: document.getElementById('apiKeyBadge'),

  // Progress
  progressSection: document.getElementById('progressSection'),
  progressTitle: document.getElementById('progressTitle'),
  progressSubtitle: document.getElementById('progressSubtitle'),
  step1: document.getElementById('step1'),
  step2: document.getElementById('step2'),
  step3: document.getElementById('step3'),

  // Video Info
  videoInfoSection: document.getElementById('videoInfoSection'),
  videoThumb: document.getElementById('videoThumb'),
  videoTitle: document.getElementById('videoTitle'),
  videoChannel: document.getElementById('videoChannel'),
  videoLevelBadge: document.getElementById('videoLevelBadge'),
  wordCountBadge: document.getElementById('wordCountBadge'),
  videoLink: document.getElementById('videoLink'),

  // Results
  resultsSection: document.getElementById('resultsSection'),
  filterInput: document.getElementById('filterInput'),
  posSelect: document.getElementById('posSelect'),
  posStatsBar: document.getElementById('posStatsBar'),
  wordsContainerCards: document.getElementById('wordsContainerCards'),
  wordsContainerTable: document.getElementById('wordsContainerTable'),
  wordsTableBody: document.getElementById('wordsTableBody'),
  btnViewCards: document.getElementById('btnViewCards'),
  btnViewTable: document.getElementById('btnViewTable'),
  btnExportCsv: document.getElementById('btnExportCsv'),
  btnCopyAnki: document.getElementById('btnCopyAnki'),

  // Toast
  toast: document.getElementById('toast')
};

// Initialize Application
document.addEventListener('DOMContentLoaded', async () => {
  initEventListeners();
  loadStoredApiKeys();
  await checkServerConfig();
  updateApiKeyStatusUI();
});

// Event Listeners Setup
function initEventListeners() {
  // Tabs
  elements.tabYoutube.addEventListener('click', () => switchTab('youtube'));
  elements.tabText.addEventListener('click', () => switchTab('text'));

  // URL Input utilities
  elements.youtubeUrlInput.addEventListener('input', () => {
    elements.btnClearUrl.style.display = elements.youtubeUrlInput.value ? 'flex' : 'none';
  });

  elements.btnClearUrl.addEventListener('click', () => {
    elements.youtubeUrlInput.value = '';
    elements.btnClearUrl.style.display = 'none';
    elements.youtubeUrlInput.focus();
  });

  elements.btnPasteUrl.addEventListener('click', async () => {
    try {
      const text = await navigator.clipboard.readText();
      elements.youtubeUrlInput.value = text.trim();
      elements.btnClearUrl.style.display = 'flex';
      showToast('クリップボードから貼り付けました');
    } catch (e) {
      showToast('クリップボードの読み取り権限がありませんでした', true);
    }
  });

  // Sample buttons
  document.querySelectorAll('.btn-sample-link').forEach(btn => {
    btn.addEventListener('click', () => {
      const url = btn.getAttribute('data-url');
      elements.youtubeUrlInput.value = url;
      elements.btnClearUrl.style.display = 'flex';
      switchTab('youtube');
      showToast('サンプル動画を設定しました');
    });
  });

  // Settings Modal
  elements.btnOpenSettings.addEventListener('click', openSettingsModal);
  elements.btnCloseSettings.addEventListener('click', closeSettingsModal);
  elements.settingsModal.addEventListener('click', (e) => {
    if (e.target === elements.settingsModal) closeSettingsModal();
  });
  elements.btnSaveSettings.addEventListener('click', saveSettings);

  // Toggle Password Visibility
  document.querySelectorAll('.btn-toggle-pw').forEach(btn => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-target');
      const input = document.getElementById(targetId);
      if (input.type === 'password') {
        input.type = 'text';
        btn.textContent = '🔒';
      } else {
        input.type = 'password';
        btn.textContent = '👁';
      }
    });
  });

  // Main Action: Extract
  elements.btnExtract.addEventListener('click', handleExtract);

  // Filters & Search
  elements.filterInput.addEventListener('input', (e) => {
    state.searchQuery = e.target.value.toLowerCase().trim();
    applyFilters();
  });

  elements.posSelect.addEventListener('change', (e) => {
    state.activeFilterPos = e.target.value;
    applyFilters();
  });

  // View Switcher
  elements.btnViewCards.addEventListener('click', () => switchViewMode('cards'));
  elements.btnViewTable.addEventListener('click', () => switchViewMode('table'));

  // Exports
  elements.btnExportCsv.addEventListener('click', handleExportCsv);
  elements.btnCopyAnki.addEventListener('click', handleCopyAnki);
}

// Tab Switching
function switchTab(tab) {
  state.currentTab = tab;
  if (tab === 'youtube') {
    elements.tabYoutube.classList.add('active');
    elements.tabText.classList.remove('active');
    elements.tabContentYoutube.style.display = 'block';
    elements.tabContentText.style.display = 'none';
  } else {
    elements.tabText.classList.add('active');
    elements.tabYoutube.classList.remove('active');
    elements.tabContentText.style.display = 'block';
    elements.tabContentYoutube.style.display = 'none';
  }
}

// View Mode Switching
function switchViewMode(mode) {
  state.viewMode = mode;
  if (mode === 'cards') {
    elements.btnViewCards.classList.add('active');
    elements.btnViewTable.classList.remove('active');
    elements.wordsContainerCards.style.display = 'grid';
    elements.wordsContainerTable.style.display = 'none';
  } else {
    elements.btnViewTable.classList.add('active');
    elements.btnViewCards.classList.remove('active');
    elements.wordsContainerCards.style.display = 'none';
    elements.wordsContainerTable.style.display = 'block';
  }
}

// API Key Management
function loadStoredApiKeys() {
  const geminiKey = localStorage.getItem('kword_gemini_api_key') || '';
  const ytKey = localStorage.getItem('kword_youtube_api_key') || '';
  elements.inputGeminiKey.value = geminiKey;
  elements.inputYoutubeKey.value = ytKey;
}

async function checkServerConfig() {
  try {
    const res = await fetch('/api/config');
    if (res.ok) {
      const data = await res.json();
      state.hasServerGeminiKey = data.has_server_gemini_key;
      state.hasServerYoutubeKey = data.has_server_youtube_key;
    }
  } catch (e) {
    console.warn('Config check error:', e);
  }
}

function updateApiKeyStatusUI() {
  const localGemini = localStorage.getItem('kword_gemini_api_key');
  const isSet = state.hasServerGeminiKey || (localGemini && localGemini.length > 5);

  if (isSet) {
    elements.apiKeyBadge.textContent = '設定済';
    elements.apiKeyBadge.className = 'key-badge set';
  } else {
    elements.apiKeyBadge.textContent = '未設定';
    elements.apiKeyBadge.className = 'key-badge not-set';
  }
}

function openSettingsModal() {
  elements.settingsModal.style.display = 'flex';
}

function closeSettingsModal() {
  elements.settingsModal.style.display = 'none';
}

function saveSettings() {
  const gemini = elements.inputGeminiKey.value.trim();
  const yt = elements.inputYoutubeKey.value.trim();

  if (gemini) {
    localStorage.setItem('kword_gemini_api_key', gemini);
  } else {
    localStorage.removeItem('kword_gemini_api_key');
  }

  if (yt) {
    localStorage.setItem('kword_youtube_api_key', yt);
  } else {
    localStorage.removeItem('kword_youtube_api_key');
  }

  updateApiKeyStatusUI();
  closeSettingsModal();
  showToast('APIキー設定を保存しました');
}

// Progress Steps Animation
function setProgressStep(step, title, subtitle) {
  elements.progressTitle.textContent = title;
  elements.progressSubtitle.textContent = subtitle;

  elements.step1.className = 'step-item';
  elements.step2.className = 'step-item';
  elements.step3.className = 'step-item';

  if (step === 1) {
    elements.step1.classList.add('active');
  } else if (step === 2) {
    elements.step1.classList.add('completed');
    elements.step2.classList.add('active');
  } else if (step === 3) {
    elements.step1.classList.add('completed');
    elements.step2.classList.add('completed');
    elements.step3.classList.add('active');
  }
}

// Main Extraction Handler
async function handleExtract() {
  const localGeminiKey = localStorage.getItem('kword_gemini_api_key');
  const localYoutubeKey = localStorage.getItem('kword_youtube_api_key');

  // Check key availability
  if (!state.hasServerGeminiKey && (!localGeminiKey || !localGeminiKey.trim())) {
    openSettingsModal();
    showToast('Gemini APIキーを設定してください', true);
    return;
  }

  // Selected Level
  const selectedLevel = document.querySelector('input[name="targetLevel"]:checked')?.value || 'intermediate';
  state.currentLevel = selectedLevel;

  // Prepare Payload
  const payload = {
    level: selectedLevel,
    gemini_api_key: localGeminiKey || null,
    youtube_api_key: localYoutubeKey || null
  };

  if (state.currentTab === 'youtube') {
    const url = elements.youtubeUrlInput.value.trim();
    if (!url) {
      showToast('YouTubeのURLを入力してください', true);
      elements.youtubeUrlInput.focus();
      return;
    }
    payload.youtube_url = url;
  } else {
    const text = elements.rawTextInput.value.trim();
    if (!text) {
      showToast('韓国語テキストを入力してください', true);
      elements.rawTextInput.focus();
      return;
    }
    payload.raw_text = text;
  }

  // UI to Loading State
  elements.btnExtract.disabled = true;
  elements.progressSection.style.display = 'block';
  elements.videoInfoSection.style.display = 'none';
  elements.resultsSection.style.display = 'none';

  setProgressStep(1, '字幕データを取得中...', 'YouTubeの韓国語字幕トラックをダウンロードしています');

  // Timer animation simulation for smooth step transitions
  const step2Timer = setTimeout(() => {
    setProgressStep(2, 'Gemini APIで単語を抽出中...', '目標レベル（' + getLevelLabel(selectedLevel) + '）に該当する単語を特定・正規化しています');
  }, 1800);

  const step3Timer = setTimeout(() => {
    setProgressStep(3, '意味・例文・辞書データを生成中...', '日本語の意味、品詞、カタカナ発音、自然な例文を整理しています');
  }, 4500);

  try {
    const response = await fetch('/api/extract', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    clearTimeout(step2Timer);
    clearTimeout(step3Timer);

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'リクエスト処理に失敗しました' }));
      throw new Error(err.detail || '抽出に失敗しました');
    }

    const data = await response.json();
    state.extractedWords = data.words || [];
    state.filteredWords = [...state.extractedWords];
    state.videoInfo = data.video_info;

    // Render results
    renderVideoInfo(data.video_info, selectedLevel, data.total_count);
    renderPosStats();
    renderWords();

    elements.progressSection.style.display = 'none';
    elements.resultsSection.style.display = 'block';
    showToast(`抽出完了！ ${data.total_count}個の単語を生成しました`);

    // Smooth scroll to results
    elements.videoInfoSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

  } catch (error) {
    clearTimeout(step2Timer);
    clearTimeout(step3Timer);
    elements.progressSection.style.display = 'none';

    const errMsg = error.message || '単語の抽出に失敗しました';
    showToast(errMsg, true, 8000);

    // If YouTube subtitle blocked, focus user on text tab option
    if (errMsg.includes('アクセス制限') || errMsg.includes('見つかりませんでした') || errMsg.includes('無効化')) {
      // Optional subtle prompt
      console.warn('Subtitle fetch notice:', errMsg);
    }
  } finally {
    elements.btnExtract.disabled = false;
  }
}

// Render Video Information Card
function renderVideoInfo(info, level, count) {
  if (!info) {
    elements.videoInfoSection.style.display = 'none';
    return;
  }

  elements.videoThumb.src = info.thumbnail_url;
  elements.videoTitle.textContent = info.title;
  elements.videoChannel.textContent = info.channel;
  elements.videoLevelBadge.textContent = getLevelLabel(level);
  elements.videoLevelBadge.className = `badge-level ${level}-badge`;
  elements.wordCountBadge.textContent = `${count}単語 抽出`;
  elements.videoLink.href = info.url;

  elements.videoInfoSection.style.display = 'block';
}

function getLevelLabel(level) {
  const map = {
    beginner: '初級',
    intermediate: '中級',
    advanced: '上級',
    all: '全レベル'
  };
  return map[level] || level;
}

// Render Part of Speech Stats
function renderPosStats() {
  const counts = {};
  state.extractedWords.forEach(w => {
    const pos = w.part_of_speech || 'その他';
    counts[pos] = (counts[pos] || 0) + 1;
  });

  let html = `<div class="pos-stat-pill ${state.activeFilterPos === 'all' ? 'active' : ''}" data-pos="all">すべて <b>(${state.extractedWords.length})</b></div>`;

  Object.entries(counts).forEach(([pos, count]) => {
    const isActive = state.activeFilterPos === pos ? 'active' : '';
    html += `<div class="pos-stat-pill ${isActive}" data-pos="${pos}">${pos} <b>(${count})</b></div>`;
  });

  elements.posStatsBar.innerHTML = html;

  // Click on pill to filter
  elements.posStatsBar.querySelectorAll('.pos-stat-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      const pos = pill.getAttribute('data-pos');
      state.activeFilterPos = pos;
      elements.posSelect.value = pos;
      applyFilters();
    });
  });
}

// Filter Logic
function applyFilters() {
  state.filteredWords = state.extractedWords.filter(item => {
    // POS filter
    if (state.activeFilterPos !== 'all' && item.part_of_speech !== state.activeFilterPos) {
      return false;
    }
    // Query search
    if (state.searchQuery) {
      const q = state.searchQuery;
      const matchWord = item.word.toLowerCase().includes(q);
      const matchMeaning = item.meaning.toLowerCase().includes(q);
      const matchHanja = (item.hanja || '').toLowerCase().includes(q);
      const matchPron = (item.pronunciation || '').toLowerCase().includes(q);
      const matchExKo = (item.example_ko || '').toLowerCase().includes(q);
      const matchExJa = (item.example_ja || '').toLowerCase().includes(q);
      if (!matchWord && !matchMeaning && !matchHanja && !matchPron && !matchExKo && !matchExJa) {
        return false;
      }
    }
    return true;
  });

  renderWords();
  renderPosStats();
}

// Render Words (Cards & Table)
function renderWords() {
  renderCards();
  renderTable();
}

function renderCards() {
  if (state.filteredWords.length === 0) {
    elements.wordsContainerCards.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 40px; color: var(--text-muted);">
        条件に一致する単語が見つかりませんでした。
      </div>
    `;
    return;
  }

  const cardsHtml = state.filteredWords.map((item, index) => {
    const hanjaHtml = item.hanja ? `<span class="card-hanja">(${escapeHtml(item.hanja)})</span>` : '';
    return `
      <div class="word-card" data-index="${index}">
        <div>
          <div class="card-header-row">
            <div class="card-word-title">
              <span>${escapeHtml(item.word)}</span>
              ${hanjaHtml}
            </div>
            <button class="btn-tts" onclick="speakKorean('${escapeJsString(item.word)}')" title="発音を聞く">
              🔊
            </button>
          </div>

          <div class="card-meta-row">
            <span class="tag-pronunciation">[${escapeHtml(item.pronunciation)}]</span>
            <span class="tag-pos">${escapeHtml(item.part_of_speech)}</span>
            <span class="tag-level ${escapeHtml(item.level)}">${escapeHtml(item.level)}</span>
          </div>

          <div class="card-meaning-box" style="margin-top: 14px;">
            <div class="meaning-label">意味</div>
            <div class="meaning-text">${escapeHtml(item.meaning)}</div>
          </div>
        </div>

        <div>
          <div class="card-example-box">
            <div class="example-ko-row">
              <div class="example-ko">${escapeHtml(item.example_ko)}</div>
              <button class="btn-tts-small" onclick="speakKorean('${escapeJsString(item.example_ko)}')" title="例文を再生">
                🔊
              </button>
            </div>
            <div class="example-ja">${escapeHtml(item.example_ja)}</div>
          </div>

          <div class="card-footer-row" style="margin-top: 10px;">
            <button class="btn-copy-card" onclick="copySingleWord(${index})">
              📋 コピー
            </button>
          </div>
        </div>
      </div>
    `;
  }).join('');

  elements.wordsContainerCards.innerHTML = cardsHtml;
}

function renderTable() {
  const rowsHtml = state.filteredWords.map((item, index) => {
    return `
      <tr>
        <td style="text-align: center;">
          <button class="btn-tts-small" onclick="speakKorean('${escapeJsString(item.word)}')" title="発音を聞く">🔊</button>
        </td>
        <td class="tbl-word">${escapeHtml(item.word)}</td>
        <td style="color: var(--text-muted);">${escapeHtml(item.hanja || '-')}</td>
        <td><span class="tag-pos">${escapeHtml(item.part_of_speech)}</span></td>
        <td style="color: #38bdf8;">[${escapeHtml(item.pronunciation)}]</td>
        <td style="font-weight: 600;">${escapeHtml(item.meaning)}</td>
        <td class="tbl-example-ko">${escapeHtml(item.example_ko)}</td>
        <td style="color: var(--text-secondary);">${escapeHtml(item.example_ja)}</td>
      </tr>
    `;
  }).join('');

  elements.wordsTableBody.innerHTML = rowsHtml;
}

// Web Speech API Native Korean TTS
function speakKorean(text) {
  if (!('speechSynthesis' in window)) {
    showToast('お使いのブラウザは音声合成に対応していません', true);
    return;
  }

  window.speechSynthesis.cancel(); // cancel any previous utterance

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = 'ko-KR';
  utterance.rate = 0.9; // Slightly slower for language learners

  // Prioritize Korean voice if available
  const voices = window.speechSynthesis.getVoices();
  const koreanVoice = voices.find(v => v.lang.startsWith('ko'));
  if (koreanVoice) {
    utterance.voice = koreanVoice;
  }

  window.speechSynthesis.speak(utterance);
}

// Copy single word to clipboard
function copySingleWord(index) {
  const item = state.filteredWords[index];
  if (!item) return;

  const text = `${item.word} [${item.pronunciation}] (${item.part_of_speech}): ${item.meaning}\n例文: ${item.example_ko}\n訳: ${item.example_ja}`;
  navigator.clipboard.writeText(text).then(() => {
    showToast(`「${item.word}」をコピーしました`);
  });
}

// CSV Export
async function handleExportCsv() {
  if (state.extractedWords.length === 0) {
    showToast('エクスポートする単語がありません', true);
    return;
  }

  try {
    const videoTitle = state.videoInfo ? state.videoInfo.title.replace(/[\\/:*?"<>|]/g, '_') : 'korean_vocab';
    const filename = `${videoTitle}_words.csv`;

    const res = await fetch('/api/export-csv', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        words: state.filteredWords,
        filename: filename
      })
    });

    if (!res.ok) throw new Error('CSV生成に失敗しました');

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);

    showToast('CSVファイルをダウンロードしました');
  } catch (e) {
    showToast(e.message, true);
  }
}

// Anki TSV Copy (Tab separated for easy flashcard import)
function handleCopyAnki() {
  if (state.filteredWords.length === 0) {
    showToast('コピーする単語がありません', true);
    return;
  }

  // Front: Word + Hanja + Pronunciation
  // Back: Meaning + POS + Example + Translation
  const tsvLines = state.filteredWords.map(item => {
    const front = `${item.word}${item.hanja ? ` (${item.hanja})` : ''}<br><small>[${item.pronunciation}]</small>`;
    const back = `<b>${item.meaning}</b> (${item.part_of_speech})<br><br><b>例文:</b> ${item.example_ko}<br><b>訳:</b> ${item.example_ja}`;
    return `${front}\t${back}`;
  });

  const fullTsv = tsvLines.join('\n');
  navigator.clipboard.writeText(fullTsv).then(() => {
    showToast(`Anki形式で${state.filteredWords.length}語をクリップボードにコピーしました！`);
  }).catch(() => {
    showToast('クリップボードへのコピーに失敗しました', true);
  });
}

// Toast Notification Helper
function showToast(message, isError = false, duration = null) {
  elements.toast.innerHTML = message;
  elements.toast.style.display = 'block';
  elements.toast.style.borderColor = isError ? 'rgba(239, 68, 68, 0.5)' : 'rgba(99, 102, 241, 0.4)';
  elements.toast.style.background = isError ? 'rgba(63, 21, 21, 0.95)' : 'rgba(30, 41, 59, 0.95)';
  elements.toast.style.lineHeight = '1.5';
  elements.toast.style.maxWidth = '460px';

  const timeout = duration || (isError ? 6500 : 3500);

  clearTimeout(elements.toast._timer);
  elements.toast._timer = setTimeout(() => {
    elements.toast.style.display = 'none';
  }, timeout);
}

// Utility: Escape HTML
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// Utility: Escape String for JS onclick attribute
function escapeJsString(str) {
  if (!str) return '';
  return String(str)
    .replace(/\\/g, '\\\\')
    .replace(/'/g, "\\'")
    .replace(/"/g, '\\"');
}
