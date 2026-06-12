import { Room, RoomEvent, Track } from 'livekit-client';

// Global State
let activeTab = 'explore';
let personas = [];
let activePersona = null;
let voiceOn = localStorage.getItem('candy_voice_on') === 'true';
let audioPlayer = null;
let avatarRoom = null;
let avatarSessionId = null;
let avatarStartedAt = 0;
let avatarTimer = null;
let studioCapabilities = null;

// AI Undress State
let uploadedImageBase64 = null;
let selectedLocalImagePath = null;
let activeUndressMode = 'undress';
let isGeneratingUndress = false;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  // Setup voice button styling
  updateVoiceButtonUI();
  updateAvatarCallUI('idle', 'LemonSlice LiveKit');
  
  // Load initial view
  loadCompanions();

  // Handle Enter key in chat input
  const chatInput = document.getElementById('chatMsgInput');
  if (chatInput) {
    chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        sendChatMessage();
      }
    });
  }
});

// Tab Switcher
window.switchTab = function(tabId) {
  activeTab = tabId;
  
  // Update nav menu active states
  document.querySelectorAll('.nav-item').forEach(btn => btn.classList.remove('active'));
  const activeBtn = document.getElementById(`btn-tab-${tabId}`);
  if (activeBtn) activeBtn.classList.add('active');

  // Toggle visible sections
  document.querySelectorAll('.view-section').forEach(view => view.classList.remove('active'));
  
  if (tabId === 'explore') {
    document.getElementById('exploreView').classList.add('active');
    loadCompanions();
  } else if (tabId === 'chat') {
    document.getElementById('chatView').classList.add('active');
    if (activePersona) {
      loadChatHistory();
    }
  } else if (tabId === 'studio') {
    document.getElementById('studioView').classList.add('active');
    loadStudioCapabilities();
    populateStudioPersonas();
  } else if (tabId === 'undress') {
    document.getElementById('undressView').classList.add('active');
  }
};

// Load companions from the backend API
async function loadCompanions() {
  try {
    const res = await fetch('/api/personas');
    if (!res.ok) throw new Error('Failed to fetch personas');
    const data = await res.json();
    
    personas = Object.entries(data.personas).map(([key, val]) => ({
      key,
      ...val
    }));
    const activeKey = data.active;
    
    // Find active persona object
    activePersona = personas.find(p => p.key === activeKey) || personas[0];
    
    renderCompanionsGrid();
    populateStudioPersonas();
  } catch (error) {
    console.error('Error loading companions:', error);
    const grid = document.getElementById('characterGrid');
    if (grid) {
      grid.innerHTML = `
        <div class="loading-state">
          <span style="font-size: 40px;">⚠️</span>
          <p>Failed to connect to the NovaMaster Chat API. Please ensure the server on port 8069 is running.</p>
        </div>
      `;
    }
  }
}

// Render the grid of companions
function renderCompanionsGrid() {
  const grid = document.getElementById('characterGrid');
  if (!grid) return;
  
  grid.innerHTML = '';
  
  personas.forEach(p => {
    const isCurrentActive = activePersona && activePersona.key === p.key;
    const card = document.createElement('div');
    card.className = `companion-card ${isCurrentActive ? 'active' : ''}`;
    card.onclick = () => selectCompanion(p.key);
    
    // Use fallback emoji or avatar path
    const avatarUrl = p.avatar ? p.avatar : 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 24 24" fill="%23e8467c"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 3c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3zm0 14.2c-2.5 0-4.71-1.28-6-3.22.03-1.99 4-3.08 6-3.08 1.99 0 5.97 1.09 6 3.08-1.29 1.94-3.5 3.22-6 3.22z"/></svg>';
    const bioText = p.system_prompt ? p.system_prompt.split('.')[0] + '.' : 'Uncensored companion.';
    
    card.innerHTML = `
      <div class="card-img-wrapper">
        <img class="card-img" src="${avatarUrl}" alt="${p.name}" onerror="this.src='https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=400&q=80'" />
        <span class="card-badge">${p.type || 'Flemish'}</span>
      </div>
      <div class="card-info">
        <h3>${p.name}</h3>
        <p>${bioText}</p>
        <div class="card-actions">
          <span class="tag-personality">Chat Companion</span>
          <button class="chat-now-btn">💬</button>
        </div>
      </div>
    `;
    
    grid.appendChild(card);
  });
}

// Select a companion and switch to the chat view
async function selectCompanion(personaKey) {
  try {
    if (avatarRoom || avatarSessionId) {
      await window.stopAvatarCall();
    }
    const res = await fetch('/api/switch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ persona: personaKey })
    });
    
    if (!res.ok) throw new Error('Switch failed');
    const data = await res.json();
    
    // Update active companion
    activePersona = personas.find(p => p.key === personaKey);
    
    // Refresh grid selections and jump to chat
    switchTab('chat');
  } catch (error) {
    console.error('Error switching companion:', error);
  }
}

function escapeHTML(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function populateStudioPersonas() {
  const select = document.getElementById('studioPersona');
  if (!select) return;
  const items = personas.length ? personas : [{ key: 'nova', name: 'Nova' }];
  select.innerHTML = items.map(p => {
    const selected = activePersona && activePersona.key === p.key ? 'selected' : '';
    return `<option value="${escapeHTML(p.key)}" ${selected}>${escapeHTML(p.name || p.key)}</option>`;
  }).join('');
}

window.loadStudioCapabilities = async function() {
  const providersEl = document.getElementById('studioProviders');
  const statusEl = document.getElementById('studioStatus');
  if (statusEl) statusEl.textContent = 'Loading';
  if (providersEl) providersEl.innerHTML = '<div class="loading-state">Loading providers...</div>';

  try {
    const res = await fetch('/api/studio/capabilities');
    if (!res.ok) throw new Error(`Studio API returned ${res.status}`);
    studioCapabilities = await res.json();
    renderStudioProviders(studioCapabilities.providers || []);
    if (statusEl) statusEl.textContent = studioCapabilities.status || 'Ready';
  } catch (error) {
    console.error('Error loading studio capabilities:', error);
    if (statusEl) statusEl.textContent = 'Offline';
    if (providersEl) {
      providersEl.innerHTML = '<div class="loading-state">Studio API unavailable.</div>';
    }
  }
};

function renderStudioProviders(providers) {
  const providersEl = document.getElementById('studioProviders');
  if (!providersEl) return;
  if (!providers.length) {
    providersEl.innerHTML = '<div class="loading-state">No providers registered.</div>';
    return;
  }
  providersEl.innerHTML = providers.map(provider => {
    const outputs = (provider.outputs || [])
      .map(output => `<span class="studio-output-chip">${escapeHTML(output)}</span>`)
      .join('');
    return `
      <div class="studio-provider-card">
        <div class="studio-provider-top">
          <div>
            <h3>${escapeHTML(provider.name)}</h3>
            <div class="studio-provider-kind">${escapeHTML(provider.kind || 'local')}</div>
          </div>
          <span class="studio-ready-dot ${provider.ready ? 'ready' : ''}"></span>
        </div>
        <div class="studio-output-row">${outputs}</div>
      </div>
    `;
  }).join('');
}

window.createStudioJob = async function() {
  const statusEl = document.getElementById('studioStatus');
  const resultEl = document.getElementById('studioJobResult');
  const prompt = document.getElementById('studioPrompt')?.value?.trim() || '';
  const payload = {
    mode: document.getElementById('studioMode')?.value || 'image',
    preset: document.getElementById('studioPreset')?.value || 'custom',
    persona: document.getElementById('studioPersona')?.value || activePersona?.key || 'nova',
    prompt,
    allow_hosted_fallback: Boolean(document.getElementById('studioFallback')?.checked),
  };

  if (!prompt) {
    if (resultEl) resultEl.innerHTML = '<div class="studio-job-card">Prompt is required.</div>';
    return;
  }

  if (statusEl) statusEl.textContent = 'Queueing';
  try {
    const res = await fetch('/api/studio/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `Studio API returned ${res.status}`);
    if (statusEl) statusEl.textContent = 'Queued';
    if (resultEl) {
      resultEl.innerHTML = `
        <div class="studio-job-card">
          <strong>${escapeHTML(data.id)}</strong>
          <div>Provider: ${escapeHTML(data.provider)}</div>
          <div>Mode: ${escapeHTML(data.mode)} · Preset: ${escapeHTML(data.preset)}</div>
        </div>
      `;
    }
  } catch (error) {
    console.error('Error creating studio job:', error);
    if (statusEl) statusEl.textContent = 'Error';
    if (resultEl) resultEl.innerHTML = `<div class="studio-job-card">${escapeHTML(error.message)}</div>`;
  }
};

// Generate the dynamic session ID for database history matching the Python backend
function getSessionId() {
  if (!activePersona) return 'nsfw';
  return 'x_' + activePersona.key;
}

// Fetch and render chat history for the active companion
async function loadChatHistory() {
  if (!activePersona) return;

  // Show header and sidebar panel
  document.getElementById('chatHeader').style.display = 'flex';
  document.getElementById('chatInputContainer').style.display = 'block';
  document.getElementById('chatSidebar').style.display = 'flex';

  // Update header info
  document.getElementById('chatHeaderName').textContent = activePersona.name;
  document.getElementById('chatHeaderAvatar').src = activePersona.avatar || '';
  
  // Update sidebar info
  document.getElementById('chatSidebarName').textContent = activePersona.name;
  document.getElementById('chatSidebarAvatar').src = activePersona.avatar || '';
  document.getElementById('chatSidebarTag').textContent = activePersona.type || 'Flemish';
  document.getElementById('chatSidebarDesc').textContent = activePersona.system_prompt || 'No description available.';

  const chatMessages = document.getElementById('chatMessages');
  chatMessages.innerHTML = `
    <div class="loading-state">
      <div class="pulsing-circle"></div>
      Loading chat history...
    </div>
  `;

  try {
    const sessionId = getSessionId();
    const res = await fetch(`/api/history/${sessionId}`);
    if (!res.ok) throw new Error('History load failed');
    const data = await res.json();
    
    chatMessages.innerHTML = '';
    
    if (data.history && data.history.length > 0) {
      data.history.forEach(msg => {
        const isUser = msg.role === 'user';
        appendMessageUI(isUser ? 'user' : 'companion', msg.text, isUser ? 'You' : activePersona.name);
      });
    } else {
      appendMessageUI('companion', `Hallo! Ik ben ${activePersona.name}. Hoe kan ik je vandaag helpen?`, activePersona.name);
    }
    
    scrollToBottom();
  } catch (error) {
    console.error('Error loading history:', error);
    chatMessages.innerHTML = '';
    appendMessageUI('companion', `Hallo! Ik ben ${activePersona.name}. Laten we beginnen!`, activePersona.name);
  }
}

// Send chat message
async function sendChatMessage() {
  const input = document.getElementById('chatMsgInput');
  const text = input.value.trim();
  if (!text || !activePersona) return;
  
  input.value = '';
  
  // Append user message immediately
  appendMessageUI('user', text, 'You');
  scrollToBottom();
  
  try {
    const sessionId = getSessionId();
    const res = await fetch('/api/chat/nsfw', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        session_id: sessionId,
        user_id: preferencesManager.userId
      })
    });
    
    if (!res.ok) throw new Error('Send failed');
    const data = await res.json();
    
    // Append AI reply
    appendMessageUI('companion', data.response, activePersona.name);
    
    // Play voice if enabled
    if (voiceOn && data.audio_base64) {
      playVoiceAudio(data.audio_base64);
    }

    // If response is multimodal, handle the visual loading container in chat thread
    if (data.type === 'multimodal' && data.visuals) {
      appendMediaPlaceholderUI(data.visuals);
    }
    
    scrollToBottom();
  } catch (error) {
    console.error('Error sending message:', error);
    appendMessageUI('companion', 'Er is een fout opgetreden bij het verzenden van je bericht. Probeer het opnieuw.', 'System');
    scrollToBottom();
  }
}

// Append media bubble placeholder with polling loader
function appendMediaPlaceholderUI(visuals) {
  const container = document.getElementById('chatMessages');
  if (!container) return;

  const div = document.createElement('div');
  div.className = 'message companion media-bubble';
  div.style.maxWidth = '320px';
  
  const uniqueId = 'chat_media_' + Math.random().toString(36).substr(2, 9);
  
  div.innerHTML = `
    <div class="msg-tag">${activePersona.name}</div>
    <div class="media-wrapper" id="${uniqueId}" style="margin-top: 10px; position: relative; border-radius: 12px; overflow: hidden; background: #07070a; border: 1px solid var(--border-color); display: flex; align-items: center; justify-content: center; min-height: 180px; width: 100%;">
      <div class="spinner-box" style="display: flex; flex-direction: column; align-items: center; gap: 10px;">
        <div class="spinner" style="width: 28px; height: 28px; border: 3px solid rgba(255,107,53,0.1); border-left-color: var(--primary-color); border-radius: 50%; animation: spin 1s linear infinite;"></div>
        <span style="font-size: 11px; color: var(--primary-color); font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">Generating ${visuals.type}...</span>
      </div>
      <img class="result-img" style="display: none; width: 100%; border-radius: 12px;" />
      <video class="result-video" controls style="display: none; width: 100%; border-radius: 12px;"></video>
    </div>
  `;
  
  container.appendChild(div);
  scrollToBottom();
  
  // Start polling
  const mediaWrapper = document.getElementById(uniqueId);
  const spinnerBox = mediaWrapper.querySelector('.spinner-box');
  const imgElement = mediaWrapper.querySelector('.result-img');
  const videoElement = mediaWrapper.querySelector('.result-video');
  
  const pollUrl = visuals.url;
  let attempts = 0;
  const maxAttempts = 45; // 90 seconds max
  
  const interval = setInterval(async () => {
    attempts++;
    
    try {
      const checkRes = await fetch(pollUrl, { method: 'HEAD' });
      if (checkRes.status === 200) {
        clearInterval(interval);
        spinnerBox.style.display = 'none';
        mediaWrapper.style.minHeight = 'auto';
        
        if (visuals.type === 'video') {
          videoElement.src = pollUrl;
          videoElement.style.display = 'block';
        } else {
          imgElement.src = pollUrl;
          imgElement.style.display = 'block';
        }
        scrollToBottom();
      }
    } catch (e) {
      // Ignore errors during polling
    }
    
    if (attempts >= maxAttempts) {
      clearInterval(interval);
      spinnerBox.innerHTML = '<span style="font-size: 11px; color: var(--text-muted);">Timed out. Please check backend.</span>';
    }
  }, 2000);
}

// Append message block to container
function appendMessageUI(senderType, text, tag) {
  const container = document.getElementById('chatMessages');
  if (!container) return;
  
  // Remove empty state if present
  const empty = container.querySelector('.empty-chat-state');
  if (empty) empty.remove();
  
  const div = document.createElement('div');
  div.className = `message ${senderType}`;
  
  if (senderType === 'companion') {
    div.innerHTML = `<div class="msg-tag">${tag}</div>${text}`;
  } else {
    div.textContent = text;
  }
  
  container.appendChild(div);
}

// Scroll chat thread to bottom
function scrollToBottom() {
  const container = document.getElementById('chatMessages');
  if (container) {
    container.scrollTop = container.scrollHeight;
  }
}

// Toggle voice/audio on and off
window.toggleVoice = function() {
  voiceOn = !voiceOn;
  localStorage.setItem('candy_voice_on', voiceOn);
  updateVoiceButtonUI();
  
  if (!voiceOn && audioPlayer) {
    audioPlayer.pause();
  }
};

function updateVoiceButtonUI() {
  const btn = document.getElementById('voiceToggleBtn');
  if (btn) {
    if (voiceOn) {
      btn.classList.add('active');
      btn.innerHTML = '🔊';
    } else {
      btn.classList.remove('active');
      btn.innerHTML = '🔇';
    }
  }
}

// Play speech audio from base64 string
function playVoiceAudio(base64Data) {
  if (audioPlayer) {
    audioPlayer.pause();
  }
  audioPlayer = new Audio('data:audio/mp3;base64,' + base64Data);
  audioPlayer.play().catch(e => console.error('Audio play failed:', e));
}

function updateAvatarCallUI(state, detail = '') {
  const panel = document.getElementById('avatarCallPanel');
  const stateEl = document.getElementById('avatarCallState');
  const detailEl = document.getElementById('avatarCallDetail');
  const callBtn = document.getElementById('avatarCallBtn');
  const endBtn = document.getElementById('avatarEndBtn');
  const empty = document.getElementById('avatarCallEmpty');
  const video = document.getElementById('avatarCallVideo');
  if (panel) panel.style.display = state === 'idle' ? 'none' : 'flex';
  if (stateEl) stateEl.textContent = state;
  if (detailEl) detailEl.textContent = detail || 'LemonSlice LiveKit';
  if (endBtn) endBtn.disabled = state === 'idle' || state === 'ending';
  if (callBtn) {
    callBtn.classList.toggle('active', state !== 'idle');
    callBtn.title = state === 'idle' ? 'Start Avatar Call' : 'Stop Avatar Call';
  }
  if (empty) empty.style.display = state === 'ready' ? 'none' : 'flex';
  if (video && state !== 'ready') video.style.display = 'none';
}

function setAvatarTimer() {
  clearInterval(avatarTimer);
  avatarTimer = setInterval(() => {
    if (!avatarStartedAt) return;
    const elapsed = Math.max(0, Math.round((Date.now() - avatarStartedAt) / 1000));
    const detail = elapsed < 5 ? `warming up ${elapsed}s` : `waiting ${elapsed}s`;
    updateAvatarCallUI('ringing', detail);
  }, 1000);
}

function attachAvatarTrack(track) {
  if (track.kind === Track.Kind.Video) {
    const video = document.getElementById('avatarCallVideo');
    if (!video) return;
    track.attach(video);
    video.style.display = 'block';
  }
  if (track.kind === Track.Kind.Audio) {
    const audioHost = document.getElementById('avatarCallAudio');
    if (!audioHost) return;
    const audioEl = track.attach();
    audioEl.autoplay = true;
    audioHost.replaceChildren(audioEl);
  }
}

function handleLemonSliceData(payload, topic) {
  if (topic !== 'lemonslice') return;
  let parsed;
  try {
    parsed = JSON.parse(new TextDecoder().decode(payload));
  } catch {
    return;
  }
  if (!parsed || parsed.type !== 'bot_ready') return;
  clearInterval(avatarTimer);
  updateAvatarCallUI('ready', `session ${parsed.session_id || avatarSessionId || 'ready'}`);
}

window.toggleAvatarCall = async function() {
  if (avatarRoom || avatarSessionId) {
    await window.stopAvatarCall();
  } else {
    await window.startAvatarCall();
  }
};

window.startAvatarCall = async function() {
  if (!activePersona) {
    appendMessageUI('companion', 'Select a companion first.', 'System');
    return;
  }
  updateAvatarCallUI('ringing', 'starting');
  avatarStartedAt = Date.now();
  setAvatarTimer();
  try {
    const response = await fetch('/api/avatar/lemonslice/session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ persona_key: activePersona.key })
    });
    const data = await response.json();
    if (!response.ok) {
      const missing = Array.isArray(data.missing) ? data.missing.join(', ') : 'configuration';
      throw new Error(`Missing ${missing}`);
    }

    avatarSessionId = data.session_id;
    avatarRoom = new Room({ adaptiveStream: true, dynacast: true });
    avatarRoom.on(RoomEvent.TrackSubscribed, attachAvatarTrack);
    avatarRoom.on(RoomEvent.DataReceived, handleLemonSliceData);
    avatarRoom.on(RoomEvent.Disconnected, () => {
      clearInterval(avatarTimer);
      avatarRoom = null;
      updateAvatarCallUI('idle', 'LemonSlice LiveKit');
    });
    await avatarRoom.connect(data.livekit_url, data.participant_token);
    updateAvatarCallUI('ringing', `room ${data.room}`);
  } catch (error) {
    console.error('Avatar call failed:', error);
    clearInterval(avatarTimer);
    avatarRoom = null;
    avatarSessionId = null;
    updateAvatarCallUI('error', error.message || 'call failed');
  }
};

window.stopAvatarCall = async function() {
  updateAvatarCallUI('ending', 'closing');
  clearInterval(avatarTimer);
  const sessionId = avatarSessionId;
  avatarSessionId = null;
  if (avatarRoom) {
    avatarRoom.disconnect();
    avatarRoom = null;
  }
  const video = document.getElementById('avatarCallVideo');
  if (video) {
    video.srcObject = null;
    video.style.display = 'none';
  }
  const audioHost = document.getElementById('avatarCallAudio');
  if (audioHost) audioHost.replaceChildren();
  if (sessionId) {
    try {
      await fetch(`/api/avatar/lemonslice/session/${encodeURIComponent(sessionId)}/control`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ event: 'terminate' })
      });
    } catch (error) {
      console.error('Avatar terminate failed:', error);
    }
  }
  updateAvatarCallUI('idle', 'LemonSlice LiveKit');
};

// Clear active companion's conversation history
window.clearActiveHistory = async function() {
  if (!activePersona) return;
  if (!confirm(`Are you sure you want to clear chat history with ${activePersona.name}?`)) return;
  
  try {
    const sessionId = getSessionId();
    const res = await fetch(`/api/clear/${sessionId}`, { method: 'POST' });
    if (!res.ok) throw new Error('Clear history failed');
    
    // Clear display
    document.getElementById('chatMessages').innerHTML = '';
    appendMessageUI('companion', `Chat history is gewist. Hoe kan ik je vandaag helpen?`, activePersona.name);
  } catch (error) {
    console.error('Error clearing chat history:', error);
  }
};

// Jump to Undress View preselected with active companion's photo
window.jumpToUndress = function() {
  if (!activePersona) return;
  
  // Set the selected character's avatar
  if (activePersona.avatar) {
    // If the avatar is `/avatar/name.jpg`, we can pass it as a path for local rendering
    const filename = activePersona.avatar.split('/').pop();
    selectedLocalImagePath = `/home/faramix/avatar_engine/identities/${filename}`;
    
    // Set UI preview image to companion avatar
    const preview = document.getElementById('undressPreview');
    const placeholder = document.getElementById('undressPlaceholder');
    preview.src = activePersona.avatar;
    preview.style.display = 'block';
    placeholder.style.display = 'none';
    
    // Clear any previously uploaded file base64
    uploadedImageBase64 = null;
  }
  
  switchTab('undress');
};

// ======================================================================
// AI Undress Logic
// ======================================================================

window.triggerUndressUpload = function() {
  if (isGeneratingUndress) return;
  document.getElementById('undressFileInput').click();
};

window.handleUndressFile = function(event) {
  const file = event.target.files[0];
  if (!file) return;
  
  const reader = new FileReader();
  reader.onload = function(e) {
    uploadedImageBase64 = e.target.result;
    selectedLocalImagePath = null; // Clear local identity path override
    
    const preview = document.getElementById('undressPreview');
    const placeholder = document.getElementById('undressPlaceholder');
    
    preview.src = uploadedImageBase64;
    preview.style.display = 'block';
    placeholder.style.display = 'none';
  };
  reader.readAsDataURL(file);
};

window.selectUndressMode = function(element, modeId) {
  if (isGeneratingUndress) return;
  activeUndressMode = modeId;
  
  // Toggle card state
  document.querySelectorAll('.mode-card').forEach(card => card.classList.remove('active'));
  element.classList.add('active');
};

window.executeUndress = async function() {
  if (isGeneratingUndress) return;
  if (!uploadedImageBase64 && !selectedLocalImagePath) {
    alert('Please upload a photo first by clicking the phone screen mockup!');
    triggerUndressUpload();
    return;
  }
  
  isGeneratingUndress = true;
  const overlay = document.getElementById('undressOverlay');
  const statusText = document.getElementById('undressStatus');
  
  overlay.style.display = 'flex';
  statusText.textContent = 'Uploading...';
  
  try {
    // Map mode to scenes supported by backend
    let sceneId = 'strip'; // default fallback
    if (activeUndressMode === 'undress') sceneId = 'strip';
    else if (activeUndressMode === 'tits') sceneId = 'spanking';
    else if (activeUndressMode === 'pussy') sceneId = 'kutje';
    else if (activeUndressMode === 'ahegao') sceneId = 'ahegao';
    else if (activeUndressMode === 'blowjob') sceneId = 'bj';
    else if (activeUndressMode === 'doggy') sceneId = 'doggy';
    else if (activeUndressMode === 'cumshot') sceneId = 'squirt';
    else if (activeUndressMode === 'masturbation') sceneId = 'aftrekken';

    statusText.textContent = 'Contacting Venice AI...';
    
    // Prepare request payload
    const body = {
      scene_id: sceneId,
      mode: 'image_undress',
      parameters: {}
    };
    
    if (uploadedImageBase64) {
      body.parameters.image = uploadedImageBase64;
    } else if (selectedLocalImagePath) {
      body.parameters.image_path = selectedLocalImagePath;
    }

    const response = await fetch('/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    
    if (!response.ok) {
      throw new Error('Failed to generate image. Please ensure the Candy NSFW API is active on port 9500.');
    }
    
    const data = await response.json();
    console.log('Undress generate response:', data);
    
    if (data.status === 'queued') {
      const imageFile = data.image_file;
      const filename = imageFile.split('/').pop();
      const imageUrl = `/output/images/${filename}`;
      
      statusText.textContent = 'Rendering details...';
      
      // Start polling the output URL for the completed image file
      pollUndressOutputImage(imageUrl);
    } else {
      throw new Error('Invalid backend response status: ' + data.status);
    }
  } catch (error) {
    alert(error.message);
    overlay.style.display = 'none';
    isGeneratingUndress = false;
  }
};

function pollUndressOutputImage(url) {
  const statusText = document.getElementById('undressStatus');
  let seconds = 0;
  const maxSeconds = 60; // 60 seconds limit
  
  const interval = setInterval(async () => {
    seconds += 2;
    statusText.textContent = `Refining... (${seconds}s)`;
    
    try {
      const res = await fetch(url, { method: 'HEAD' });
      if (res.status === 200) {
        clearInterval(interval);
        
        // Output image is generated! Update preview
        const preview = document.getElementById('undressPreview');
        preview.src = url;
        
        document.getElementById('undressOverlay').style.display = 'none';
        isGeneratingUndress = false;
        
        // Dedup coins (just UI cosmetic polish)
        const coins = document.getElementById('coinsCount');
        if (coins) {
          const current = parseInt(coins.textContent.replace(/,/g, ''));
          if (!isNaN(current) && current >= 10) {
            coins.textContent = (current - 10).toLocaleString();
            document.querySelectorAll('.coins-indicator').forEach(el => el.textContent = '🪙 ' + (current - 10).toLocaleString());
          }
        }
      }
    } catch (e) {
      // Ignore network errors during polling
    }
    
    if (seconds >= maxSeconds) {
      clearInterval(interval);
      alert('The generation request timed out. Please check the backend service logs.');
      document.getElementById('undressOverlay').style.display = 'none';
      isGeneratingUndress = false;
    }
  }, 2000);
}

// User preferences management
class UserPreferencesManager {
    constructor() {
        this.userId = localStorage.getItem('candy_user_id') || this.generateUserId();
        localStorage.setItem('candy_user_id', this.userId);
        
        this.preferences = {};
        this.loadPreferences();
    }
    
    generateUserId() {
        return 'user_' + Math.random().toString(36).substr(2, 9);
    }
    
    async loadPreferences() {
        try {
            const response = await fetch(`/api/user/preferences/${this.userId}`);
            const data = await response.json();
            
            this.preferences = {
                ...data.preferences,
                boundaries: data.boundaries
            };
        } catch (error) {
            console.error('Error loading preferences:', error);
        }
    }
    
    async savePreferences(preferences) {
        try {
            const response = await fetch(`/api/user/preferences`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    user_id: this.userId,
                    ...preferences
                })
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                await this.loadPreferences(); // Reload preferences
            }
            
            return data;
        } catch (error) {
            console.error('Error saving preferences:', error);
            return { status: 'error', message: error.message };
        }
    }
    
    async getLearningSummary() {
        try {
            const response = await fetch(`/api/user/learning/${this.userId}`);
            return await response.json();
        } catch (error) {
            console.error('Error getting learning summary:', error);
            return null;
        }
    }
}

// Initialize preferences manager
const preferencesManager = new UserPreferencesManager();

// Expose preferencesManager to window for debug or access
window.preferencesManager = preferencesManager;

// Expose showPreferencesDialog globally
window.showPreferencesDialog = async function() {
    // Fetch learning summary to display user stats in real-time
    const summary = await preferencesManager.getLearningSummary();
    
    const dialog = document.createElement('div');
    dialog.className = 'preferences-dialog';
    
    let topKinksHtml = 'None detected yet';
    if (summary && summary.top_kinks && summary.top_kinks.length > 0) {
        topKinksHtml = summary.top_kinks.map(([kink, score]) => `<span style="background: rgba(232, 70, 124, 0.15); color: var(--primary-color); padding: 2px 8px; border-radius: 12px; margin-right: 5px; font-size: 11px;">${kink} (${Math.round(score * 100)}%)</span>`).join('');
    }
    
    let statsHtml = '';
    if (summary) {
        statsHtml = `
            <div class="preference-section">
                <h3>🧠 Learning Engine Insights</h3>
                <div class="learning-stats">
                    <div class="learning-stat-row">
                        <span>Total Interactions:</span>
                        <span class="learning-stat-val">${summary.interaction_count}</span>
                    </div>
                    <div class="learning-stat-row">
                        <span>Media Requests:</span>
                        <span class="learning-stat-val">${summary.media_request_count} (Rate: ${Math.round(summary.media_request_rate * 100)}%)</span>
                    </div>
                    <div class="learning-stat-row">
                        <span>Learning Confidence:</span>
                        <span class="learning-stat-val">${Math.round(summary.learning_confidence * 100)}%</span>
                    </div>
                    <div class="learning-stat-row" style="flex-direction: column; align-items: flex-start; gap: 6px;">
                        <span>Detected Kinks & Preferences:</span>
                        <div style="margin-top: 4px; display: flex; flex-wrap: wrap; gap: 4px;">${topKinksHtml}</div>
                    </div>
                </div>
            </div>
        `;
    }

    dialog.innerHTML = `
        <div class="dialog-content">
            <h2>Adjust Preferences & Boundaries</h2>
            
            <form id="preferences-form">
                <div class="preference-section">
                    <h3>Content Intensity</h3>
                    <div class="intensity-selector">
                        <label><input type="radio" name="intensity" value="soft"> Soft</label>
                        <label><input type="radio" name="intensity" value="medium"> Medium</label>
                        <label><input type="radio" name="intensity" value="hard"> Hard</label>
                        <label><input type="radio" name="intensity" value="extreme"> Extreme</label>
                    </div>
                </div>
                
                <div class="preference-section">
                    <h3>Content Boundaries (No-Go Zones)</h3>
                    <div class="boundary-selector">
                        <label><input type="checkbox" name="boundary.bondage" value="hard"> 🔒 No Bondage</label>
                        <label><input type="checkbox" name="boundary.pain" value="hard"> 🩸 No Pain</label>
                        <label><input type="checkbox" name="boundary.public" value="hard"> 🏢 No Public</label>
                        <label><input type="checkbox" name="boundary.age_play" value="hard"> 🍼 No Age Play</label>
                    </div>
                </div>
                
                <div class="preference-section">
                    <h3>Visual Preferences</h3>
                    <div class="visual-selector">
                        <label style="width: 100%; justify-content: flex-start;"><input type="checkbox" name="visual_preference" value="true"> 📸 Prefer Visual Content</label>
                    </div>
                </div>
                
                ${statsHtml}
                
                <div class="dialog-actions">
                    <button type="button" id="cancel-preferences">Cancel</button>
                    <button type="button" id="save-preferences">Save Preferences</button>
                </div>
            </form>
        </div>
    `;
    
    document.body.appendChild(dialog);
    
    // Set current values
    const currentIntensity = preferencesManager.preferences.intensity?.preferred_level || 0.5;
    const intensityMap = {0.25: 'soft', 0.5: 'medium', 0.75: 'hard', 1.0: 'extreme'};
    const intensityValue = intensityMap[currentIntensity] || 'medium';
    
    const intensityInput = dialog.querySelector(`input[name="intensity"][value="${intensityValue}"]`);
    if (intensityInput) intensityInput.checked = true;
    
    const visualPref = preferencesManager.preferences.media?.visual_preference || 0.5;
    const visualInput = dialog.querySelector('input[name="visual_preference"]');
    if (visualInput) visualInput.checked = visualPref > 0.5;
    
    // Set boundaries
    const boundaries = preferencesManager.preferences.boundaries || {};
    for (const [key, value] of Object.entries(boundaries)) {
        if (value === 'hard') {
            const input = dialog.querySelector(`input[name="${key}"]`);
            if (input) input.checked = true;
        }
    }
    
    // Handle save
    document.getElementById('save-preferences').addEventListener('click', async () => {
        const form = document.getElementById('preferences-form');
        const formData = new FormData(form);
        const preferences = {};
        
        // Get intensity
        const intensityValue = formData.get('intensity');
        const intensityReverseMap = {'soft': 0.25, 'medium': 0.5, 'hard': 0.75, 'extreme': 1.0};
        preferences.intensity = intensityReverseMap[intensityValue] || 0.5;
        
        // Get boundaries (defaulting to 'soft' if not selected as 'hard')
        const boundaryKeys = ['boundary.bondage', 'boundary.pain', 'boundary.public', 'boundary.age_play'];
        boundaryKeys.forEach(key => {
            preferences[key] = formData.get(key) === 'hard' ? 'hard' : 'soft';
        });
        
        // Get visual preference
        preferences.visual_preference = formData.get('visual_preference') ? 1.0 : 0.0;
        
        // Save preferences
        await preferencesManager.savePreferences(preferences);
        
        // Close dialog
        document.body.removeChild(dialog);
    });
    
    // Handle cancel
    document.getElementById('cancel-preferences').addEventListener('click', () => {
        document.body.removeChild(dialog);
    });
};

// Adaptive Content Manager
class AdaptiveContentManager {
    constructor() {
        this.readyContent = [];
        this.checkInterval = null;
        this.predictionAccuracy = 0.0;
        this.init();
    }
    
    init() {
        this.addReadyContentNotification();
        this.startContentCheck();
        this.loadPredictionAccuracy();
    }
    
    startContentCheck() {
        // Check for ready content immediately, then every 30 seconds
        setTimeout(() => this.checkForReadyContent(), 2000);
        this.checkInterval = setInterval(async () => {
            await this.checkForReadyContent();
        }, 30000);
    }
    
    async checkForReadyContent() {
        try {
            const userId = preferencesManager.userId;
            if (!userId) return;
            
            const response = await fetch(`/api/user/ready_content/${userId}`);
            if (!response.ok) return;
            
            const data = await response.json();
            if (data.ready_content && data.ready_content.length > 0) {
                this.readyContent = data.ready_content;
                this.showReadyContentNotification();
            } else {
                this.readyContent = [];
                const notification = document.getElementById('ready-content-notification');
                if (notification) notification.style.display = 'none';
            }
        } catch (error) {
            console.error('Error checking for ready content:', error);
        }
    }
    
    async loadPredictionAccuracy() {
        try {
            const userId = preferencesManager.userId;
            if (!userId) return;
            const response = await fetch(`/api/user/accuracy/${userId}`);
            if (!response.ok) return;
            const data = await response.json();
            this.predictionAccuracy = data.accuracy.accuracy || 0.0;
            this.updateAccuracyDisplay();
        } catch (error) {
            console.error('Error loading prediction accuracy:', error);
        }
    }
    
    updateAccuracyDisplay() {
        const accuracyElement = document.getElementById('prediction-accuracy');
        if (accuracyElement) {
            accuracyElement.textContent = `${Math.round(this.predictionAccuracy * 100)}%`;
        }
    }
    
    addReadyContentNotification() {
        let notification = document.getElementById('ready-content-notification');
        if (!notification) {
            notification = document.createElement('div');
            notification.id = 'ready-content-notification';
            notification.className = 'ready-content-notification';
            notification.style.display = 'none';
            document.body.appendChild(notification);
        }
    }
    
    showReadyContentNotification() {
        const notification = document.getElementById('ready-content-notification');
        if (!notification) return;
        
        if (this.readyContent.length > 0) {
            notification.innerHTML = `
                <div class="notification-content">
                    <h3>🎁 Predictive Content Ready</h3>
                    <p>Companion has prepared ${this.readyContent.length} special moment(s) based on your desires!</p>
                    <div style="display: flex; gap: 8px; margin-top: 10px;">
                        <button id="view-ready-content" style="background: var(--primary-gradient); color: white; border: none; padding: 6px 12px; border-radius: 8px; font-weight: 700; cursor: pointer;">Reveal</button>
                        <button id="dismiss-notification" style="background: rgba(255,255,255,0.05); border: 1px solid var(--border-color); color: var(--text-secondary); padding: 6px 12px; border-radius: 8px; cursor: pointer;">Dismiss</button>
                    </div>
                </div>
            `;
            
            notification.style.display = 'block';
            
            document.getElementById('view-ready-content').addEventListener('click', () => {
                this.showReadyContentDialog();
            });
            
            document.getElementById('dismiss-notification').addEventListener('click', () => {
                notification.style.display = 'none';
            });
        } else {
            notification.style.display = 'none';
        }
    }
    
    showReadyContentDialog() {
        // Hide notification
        const notification = document.getElementById('ready-content-notification');
        if (notification) notification.style.display = 'none';
        
        // Remove existing dialog if any
        const existing = document.querySelector('.ready-content-dialog');
        if (existing) document.body.removeChild(existing);
        
        // Create dialog
        const dialog = document.createElement('div');
        dialog.className = 'ready-content-dialog';
        dialog.innerHTML = `
            <div class="dialog-content">
                <h2>🎁 Your Predictive Moments</h2>
                <div class="prediction-accuracy" style="margin-top: 10px; background: rgba(255,255,255,0.03); border: 1px solid var(--border-color); padding: 10px; border-radius: 8px; display: flex; justify-content: space-between; font-size: 14px;">
                    <span class="accuracy-label" style="color: var(--text-secondary);">Prediction Accuracy:</span>
                    <span class="accuracy-value" id="prediction-accuracy" style="color: var(--primary-color); font-weight: 700;">${Math.round(this.predictionAccuracy * 100)}%</span>
                </div>
                <div class="content-list" style="margin-top: 15px; max-height: 300px; overflow-y: auto;">
                    ${this.readyContent.map(content => {
                        const confidence = Math.round((content.content.prediction_metadata?.confidence || 0.5) * 100);
                        const reasoning = content.content.prediction_metadata?.reasoning || 'Unknown';
                        return `
                        <div class="content-item" data-content-id="${content.content_id}" style="margin-bottom: 12px; background: rgba(255,255,255,0.02); border: 1px solid var(--border-color); padding: 12px; border-radius: 8px;">
                            <div class="content-type" style="color: var(--primary-color); font-weight: 700; font-size: 12px;">✨ PREDICTED ${content.content_type.toUpperCase()}</div>
                            <div class="content-scheduled" style="color: var(--text-secondary); font-size: 11px; margin-top: 2px;">Generated: ${new Date(content.scheduled_time).toLocaleString()}</div>
                            <div class="content-confidence" style="font-size: 11px; margin-top: 4px; color: var(--text-muted);">Confidence: ${confidence}%</div>
                            <div class="content-reasoning" style="font-size: 11px; margin-top: 2px; color: var(--text-muted);">Reason: ${reasoning}</div>
                            <div class="content-actions" style="margin-top: 10px; display: flex; gap: 8px;">
                                <button class="view-content-btn" style="background: var(--primary-gradient); color: white; border: none; padding: 6px 12px; border-radius: 8px; font-weight: 700; cursor: pointer;">Reveal</button>
                                <button class="dismiss-content-btn" style="background: rgba(255,255,255,0.05); border: 1px solid var(--border-color); color: var(--text-secondary); padding: 6px 12px; border-radius: 8px; cursor: pointer;">Discard</button>
                            </div>
                        </div>
                        `;
                    }).join('')}
                </div>
                <div class="dialog-actions" style="margin-top: 20px; text-align: right;">
                    <button id="close-ready-content-dialog" style="background: transparent; border: 1px solid var(--border-color); color: var(--text-secondary); padding: 8px 16px; border-radius: 8px; cursor: pointer;">Close</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(dialog);
        
        // Add event listeners
        dialog.querySelectorAll('.view-content-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const contentId = e.target.closest('.content-item').dataset.contentId;
                this.viewContent(contentId);
            });
        });
        
        dialog.querySelectorAll('.dismiss-content-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const contentId = e.target.closest('.content-item').dataset.contentId;
                this.dismissContent(contentId);
            });
        });
        
        document.getElementById('close-ready-content-dialog').addEventListener('click', () => {
            document.body.removeChild(dialog);
        });
    }
    
    async viewContent(contentId) {
        try {
            const item = this.readyContent.find(c => c.content_id === contentId);
            if (!item) return;
            
            const content = item.content; // experience dict
            const personaName = activePersona ? activePersona.name : 'Companion';
            
            // Switch to chat view tab automatically
            switchTab('chat');
            
            const reasoning = content.prediction_metadata?.reasoning || 'preferences';
            const confidence = Math.round((content.prediction_metadata?.confidence || 0.5) * 100);
            
            // Append AI text narrative
            appendMessageUI('companion', `(I've prepared this special moment based on ${reasoning} with ${confidence}% confidence) ${content.text || ''}`, personaName);
            
            // Play audio voice if enabled
            if (voiceOn && content.audio_base64) {
                playVoiceAudio(content.audio_base64);
            }
            
            // Append visual direct
            if (content.visuals && content.visuals.url) {
                const container = document.getElementById('chatMessages');
                if (container) {
                    const div = document.createElement('div');
                    div.className = 'message companion media-bubble';
                    div.style.maxWidth = '320px';
                    
                    const isVideo = content.visuals.type === 'video';
                    div.innerHTML = `
                        <div class="msg-tag">${personaName}</div>
                        <div class="media-wrapper" style="margin-top: 10px; border-radius: 12px; overflow: hidden; background: #07070a; border: 1px solid var(--border-color); display: flex; align-items: center; justify-content: center; width: 100%;">
                            ${isVideo ? 
                                `<video class="result-video" src="${content.visuals.url}" controls style="width: 100%; border-radius: 12px; display: block;"></video>` :
                                `<img class="result-img" src="${content.visuals.url}" style="width: 100%; border-radius: 12px; display: block;" />`
                            }
                        </div>
                    `;
                    container.appendChild(div);
                }
            }
            scrollToBottom();
            
            // Mark delivered on server
            await fetch('/api/content/deliver', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content_id: contentId })
            });
            
            // Remove locally
            this.readyContent = this.readyContent.filter(c => c.content_id !== contentId);
            
            // Update accuracy
            await this.loadPredictionAccuracy();
            
            this.updateReadyContentDialog();
            
        } catch (error) {
            console.error('Error revealing content:', error);
        }
    }
    
    async dismissContent(contentId) {
        try {
            await fetch('/api/content/deliver', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content_id: contentId })
            });
            
            this.readyContent = this.readyContent.filter(c => c.content_id !== contentId);
            this.updateReadyContentDialog();
        } catch (error) {
            console.error('Error dismissing content:', error);
        }
    }
    
    updateReadyContentDialog() {
        const dialog = document.querySelector('.ready-content-dialog');
        if (dialog) {
            if (this.readyContent.length === 0) {
                document.body.removeChild(dialog);
            } else {
                const contentList = dialog.querySelector('.content-list');
                if (contentList) {
                    contentList.innerHTML = this.readyContent.map(content => {
                        const confidence = Math.round((content.content.prediction_metadata?.confidence || 0.5) * 100);
                        const reasoning = content.content.prediction_metadata?.reasoning || 'Unknown';
                        return `
                        <div class="content-item" data-content-id="${content.content_id}" style="margin-bottom: 12px; background: rgba(255,255,255,0.02); border: 1px solid var(--border-color); padding: 12px; border-radius: 8px;">
                            <div class="content-type" style="color: var(--primary-color); font-weight: 700; font-size: 12px;">✨ PREDICTED ${content.content_type.toUpperCase()}</div>
                            <div class="content-scheduled" style="color: var(--text-secondary); font-size: 11px; margin-top: 2px;">Generated: ${new Date(content.scheduled_time).toLocaleString()}</div>
                            <div class="content-confidence" style="font-size: 11px; margin-top: 4px; color: var(--text-muted);">Confidence: ${confidence}%</div>
                            <div class="content-reasoning" style="font-size: 11px; margin-top: 2px; color: var(--text-muted);">Reason: ${reasoning}</div>
                            <div class="content-actions" style="margin-top: 10px; display: flex; gap: 8px;">
                                <button class="view-content-btn" style="background: var(--primary-gradient); color: white; border: none; padding: 6px 12px; border-radius: 8px; font-weight: 700; cursor: pointer;">Reveal</button>
                                <button class="dismiss-content-btn" style="background: rgba(255,255,255,0.05); border: 1px solid var(--border-color); color: var(--text-secondary); padding: 6px 12px; border-radius: 8px; cursor: pointer;">Discard</button>
                            </div>
                        </div>
                        `;
                    }).join('');
                    
                    // Rebind event listeners
                    dialog.querySelectorAll('.view-content-btn').forEach(btn => {
                        btn.addEventListener('click', (e) => {
                            const contentId = e.target.closest('.content-item').dataset.contentId;
                            this.viewContent(contentId);
                        });
                    });
                    
                    dialog.querySelectorAll('.dismiss-content-btn').forEach(btn => {
                        btn.addEventListener('click', (e) => {
                            const contentId = e.target.closest('.content-item').dataset.contentId;
                            this.dismissContent(contentId);
                        });
                    });
                }
            }
        }
    }
}

// Initialize adaptive content manager
const adaptiveContentManager = new AdaptiveContentManager();
window.adaptiveContentManager = adaptiveContentManager;
window.sendChatMessage = sendChatMessage;
