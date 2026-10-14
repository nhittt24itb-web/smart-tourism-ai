

(function () {
  'use strict';

  // Trạng thái hiện tại của bộ điều hướng Google Maps
  const gDirState = {
    origin: null,          // { lat, lon, name, address }
    destination: null,     // { lat, lon, name, address }
    mode: 'd',             // 'd' (ô tô), 'b' (xe máy/đạp), 'w' (đi bộ), 'r' (xe buýt)
    activeView: 'map',     // 'map' | 'steps'
    isFullscreen: false,
    originOptions: [],
    userGps: null
  };

  /**
   * 1. Khởi tạo và chèn Modal Google Maps vào trang web (nếu chưa có)
   */
  function ensureModalInDOM() {
    if (document.getElementById('google-maps-directions-modal')) return;

    const modalHTML = `
      <div id="google-maps-directions-modal" class="gdir-backdrop" style="display: none; position: fixed; inset: 0; z-index: 999999; background: rgba(15, 23, 42, 0.75); backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px); align-items: center; justify-content: center; padding: 12px; font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;">
        <div id="gdir-modal-card" style="background: #ffffff; border-radius: 24px; width: 100%; max-width: 960px; height: 90vh; max-height: 800px; display: flex; flex-direction: column; overflow: hidden; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.35); border: 1px solid rgba(226, 232, 240, 0.9); transition: all 0.3s ease;">
          
          <!-- THANH HEADER GOOGLE MAPS -->
          <div style="padding: 14px 20px; background: #f8fafc; border-bottom: 1px solid #e2e8f0; display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-shrink: 0;">
            <div style="display: flex; align-items: center; gap: 10px;">
              <div style="width: 36px; height: 36px; border-radius: 12px; background: #ffffff; border: 1px solid #e2e8f0; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                <svg width="22" height="22" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M24 4C14.06 4 6 12.06 6 22c0 13.25 15.35 21.03 16.98 21.82.32.16.69.24 1.02.24s.7-.08 1.02-.24C26.65 43.03 42 35.25 42 22c0-9.94-8.06-18-18-18z" fill="#4285F4"/>
                  <path d="M24 13a9 9 0 100 18 9 9 0 000-18z" fill="#EA4335"/>
                  <path d="M24 18a4 4 0 100 8 4 4 0 000-8z" fill="#FFFFFF"/>
                  <path d="M12 22c0-6.63 5.37-12 12-12s12 5.37 12 12c0 7.82-8.52 14.53-12 16.89C20.52 36.53 12 29.82 12 22z" fill="#34A853" opacity="0.2"/>
                </svg>
              </div>
              <div>
                <div style="display: flex; align-items: center; gap: 6px;">
                  <span style="font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px; background: #eff6ff; color: #1d4ed8; padding: 2px 8px; border-radius: 999px;">Google Maps Live</span>
                  <span style="font-size: 11px; color: #64748b; font-weight: 600;">• Không chuyển tab</span>
                </div>
                <h3 id="gdir-title" style="margin: 2px 0 0 0; font-size: 16px; font-weight: 900; color: #0f172a; line-height: 1.2;">Chỉ Đường Google Maps Trực Tiếp</h3>
              </div>
            </div>

            <div style="display: flex; align-items: center; gap: 6px;">
              <!-- Nút chuyển đổi giao diện: Google Maps / Turn-by-turn -->
              <div style="display: flex; background: #e2e8f0; padding: 3px; border-radius: 12px; gap: 2px;">
                <button type="button" id="gdir-view-map-btn" onclick="window.switchGoogleDirectionsView('map')" style="padding: 5px 12px; font-size: 11px; font-weight: 800; border-radius: 9px; border: 0; cursor: pointer; transition: all 0.2s; background: #ffffff; color: #0f172a; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                  🗺️ Bản đồ
                </button>
                <button type="button" id="gdir-view-steps-btn" onclick="window.switchGoogleDirectionsView('steps')" style="padding: 5px 12px; font-size: 11px; font-weight: 800; border-radius: 9px; border: 0; cursor: pointer; transition: all 0.2s; background: transparent; color: #64748b;">
                  📋 Lộ trình chi tiết
                </button>
              </div>

              <!-- Phóng to / Thu nhỏ -->
              <button type="button" onclick="window.toggleGoogleDirectionsFullscreen()" title="Toàn màn hình / Thu nhỏ" style="width: 34px; height: 34px; border-radius: 10px; background: #ffffff; border: 1px solid #e2e8f0; color: #475569; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.2s;">
                <span id="gdir-fs-icon" style="font-size: 16px;">⛶</span>
              </button>

              <!-- Đóng -->
              <button type="button" onclick="window.closeGoogleDirectionsModal()" title="Đóng" style="width: 34px; height: 34px; border-radius: 10px; background: #fee2e2; border: 1px solid #fecaca; color: #b91c1c; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.2s; font-weight: 800;">
                ✕
              </button>
            </div>
          </div>

          <!-- BẢNG ĐIỀU KHIỂN ĐIỂM ĐI - ĐIỂM ĐẾN & PHƯƠNG TIỆN -->
          <div style="padding: 12px 20px; background: #ffffff; border-bottom: 1px solid #f1f5f9; display: flex; flex-wrap: wrap; gap: 12px; align-items: center; justify-content: space-between; flex-shrink: 0;">
            
            <!-- Box A & B có nút đảo chiều -->
            <div style="display: flex; align-items: center; gap: 10px; flex: 1; min-width: 300px;">
              
              <!-- 2 Hàng Điểm đi / Điểm đến -->
              <div style="flex: 1; display: flex; flex-direction: column; gap: 6px;">
                <!-- Điểm xuất phát A -->
                <div style="display: flex; align-items: center; gap: 8px; background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 12px; padding: 4px 10px;">
                  <span style="color: #2563eb; font-size: 16px; line-height: 1;">●</span>
                  <div style="flex: 1; min-width: 0;">
                    <span style="font-size: 9px; font-weight: 800; color: #64748b; text-transform: uppercase; display: block; line-height: 1;">Xuất phát:</span>
                    <select id="gdir-origin-select" onchange="window.onGoogleDirectionsOriginChanged()" style="width: 100%; border: 0; background: transparent; font-size: 12px; font-weight: 700; color: #0f172a; outline: none; cursor: pointer; padding: 2px 0;">
                    </select>
                  </div>
                  <button type="button" onclick="window.useMyGpsAsOrigin()" title="Lấy vị trí GPS hiện tại" style="padding: 4px 8px; font-size: 10px; font-weight: 800; background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; border-radius: 8px; cursor: pointer; display: flex; align-items: center; gap: 4px; white-space: nowrap;">
                    <span>📍 GPS của tôi</span>
                  </button>
                </div>

                <!-- Điểm đến B -->
                <div style="display: flex; align-items: center; gap: 8px; background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 12px; padding: 4px 10px;">
                  <span style="color: #dc2626; font-size: 16px; line-height: 1;">📍</span>
                  <div style="flex: 1; min-width: 0;">
                    <span style="font-size: 9px; font-weight: 800; color: #64748b; text-transform: uppercase; display: block; line-height: 1;">Điểm đến:</span>
                    <div id="gdir-dest-text" style="font-size: 12px; font-weight: 800; color: #0f172a; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                      Đang chọn điểm đến...
                    </div>
                  </div>
                </div>
              </div>

              <!-- Nút Đảo chiều Điểm đi <-> Điểm đến -->
              <button type="button" onclick="window.swapGoogleDirectionsPoints()" title="Hoán đổi điểm xuất phát và điểm đến" style="width: 36px; height: 36px; border-radius: 50%; background: #ffffff; border: 1px solid #cbd5e1; color: #0f172a; display: flex; align-items: center; justify-content: center; cursor: pointer; box-shadow: 0 2px 4px rgba(0,0,0,0.05); font-size: 16px; font-weight: 900; transition: transform 0.2s;" onmouseenter="this.style.transform='rotate(180deg)'" onmouseleave="this.style.transform='none'">
                ⇅
              </button>
            </div>

            <!-- Nút chọn Phương tiện giao thông -->
            <div style="display: flex; align-items: center; gap: 4px; background: #f1f5f9; padding: 4px; border-radius: 14px;">
              <button type="button" id="gdir-mode-d" onclick="window.setGoogleDirectionsMode('d')" style="padding: 6px 12px; border-radius: 10px; font-size: 12px; font-weight: 800; border: 0; cursor: pointer; transition: all 0.2s; background: #1e293b; color: #ffffff; display: flex; align-items: center; gap: 4px;">
                <span>🚗 Ô tô</span>
              </button>
              <button type="button" id="gdir-mode-b" onclick="window.setGoogleDirectionsMode('b')" style="padding: 6px 12px; border-radius: 10px; font-size: 12px; font-weight: 800; border: 0; cursor: pointer; transition: all 0.2s; background: transparent; color: #475569; display: flex; align-items: center; gap: 4px;">
                <span>🛵 Xe máy</span>
              </button>
              <button type="button" id="gdir-mode-w" onclick="window.setGoogleDirectionsMode('w')" style="padding: 6px 12px; border-radius: 10px; font-size: 12px; font-weight: 800; border: 0; cursor: pointer; transition: all 0.2s; background: transparent; color: #475569; display: flex; align-items: center; gap: 4px;">
                <span>🚶 Đi bộ</span>
              </button>
              <button type="button" id="gdir-mode-r" onclick="window.setGoogleDirectionsMode('r')" style="padding: 6px 12px; border-radius: 10px; font-size: 12px; font-weight: 800; border: 0; cursor: pointer; transition: all 0.2s; background: transparent; color: #475569; display: flex; align-items: center; gap: 4px;">
                <span>🚌 Xe buýt</span>
              </button>
            </div>

          </div>

          <!-- KHUNG NỘI DUNG CHÍNH (BẢN ĐỒ HOẶC DANH SÁCH BƯỚC) -->
          <div style="flex: 1; position: relative; overflow: hidden; background: #e5e7eb;">
            
            <!-- 1. Iframe Google Maps trực tiếp -->
            <div id="gdir-map-panel" style="width: 100%; height: 100%; position: relative;">
              <iframe id="gdir-iframe" style="width: 100%; height: 100%; border: 0; display: block;" allowfullscreen loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>
              
              <!-- Spinner khi tải bản đồ -->
              <div id="gdir-iframe-loading" style="display: none; position: absolute; inset: 0; background: rgba(255,255,255,0.7); backdrop-filter: blur(2px); align-items: center; justify-content: center; z-index: 10;">
                <div style="text-align: center; color: #1e293b; font-weight: 700; font-size: 13px;">
                  <div style="width: 32px; height: 32px; border: 3px solid #e2e8f0; border-top-color: #2563eb; border-radius: 50%; animation: gdir-spin 0.8s linear infinite; margin: 0 auto 8px auto;"></div>
                  Đang tải dữ liệu Google Maps...
                </div>
              </div>
            </div>

            <!-- 2. Bảng Lộ trình chi tiết từng bước (Turn-by-turn steps) -->
            <div id="gdir-steps-panel" style="display: none; width: 100%; height: 100%; overflow-y: auto; background: #ffffff; padding: 20px;">
              <div style="max-width: 650px; margin: 0 auto;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #e2e8f0;">
                  <div>
                    <h4 style="margin: 0; font-size: 15px; font-weight: 900; color: #0f172a;">Chi Tiết Từng Ngã Rẽ & Đoạn Đường</h4>
                    <p style="margin: 2px 0 0 0; font-size: 11px; color: #64748b;">Dẫn đường chuẩn xác theo tên đường tiếng Việt</p>
                  </div>
                  <div id="gdir-steps-summary-badge" style="background: #eff6ff; color: #1d4ed8; font-size: 12px; font-weight: 800; padding: 4px 12px; border-radius: 999px;">
                    -- km • -- phút
                  </div>
                </div>

                <div id="gdir-steps-list" style="display: flex; flex-direction: column; gap: 10px;">
                  <!-- Các bước chỉ đường sẽ nạp vào đây -->
                </div>
              </div>
            </div>

          </div>

          <!-- FOOTER MODAL -->
          <div style="padding: 10px 20px; background: #f8fafc; border-top: 1px solid #e2e8f0; display: flex; align-items: center; justify-content: space-between; font-size: 11px; color: #64748b; flex-shrink: 0;">
            <button type="button" onclick="window.closeGoogleDirectionsModal()" style="padding: 6px 18px; border-radius: 10px; background: #e2e8f0; hover:background: #cbd5e1; border: 0; color: #334155; font-size: 12px; font-weight: 800; cursor: pointer; transition: all 0.2s;">
              Đóng
            </button>
          </div>

        </div>
      </div>
      
      <style>
        @keyframes gdir-spin { to { transform: rotate(360deg); } }
      </style>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHTML);

    const iframe = document.getElementById('gdir-iframe');
    if (iframe) {
      iframe.addEventListener('load', () => {
        const loading = document.getElementById('gdir-iframe-loading');
        if (loading) loading.style.display = 'none';
      });
    }
  }

  /**
   * 2. Mở Modal Chỉ đường Google Maps với các thông số điểm đến & điểm xuất phát
   */
  window.openGoogleDirectionsModal = function (config) {
    ensureModalInDOM();

    // Chuẩn hóa điểm đến
    let destLat = config.destLat || (config.destination && config.destination.lat);
    let destLon = config.destLon || (config.destination && config.destination.lon);
    let destName = config.destName || (config.destination && config.destination.name) || 'Điểm đến đã chọn';
    let destAddress = config.destAddress || (config.destination && config.destination.address) || '';

    // Làm sạch text icon lọt vào (ví dụ location_on, bi bi-cursor-fill, v.v.)
    destName = (destName || '').replace(/location_on|location_pin|pin_drop|place/gi, '').trim() || 'Điểm đến đã chọn';
    destAddress = (destAddress || '').replace(/location_on|location_pin|pin_drop|place/gi, '').trim();

    gDirState.destination = {
      lat: parseFloat(destLat),
      lon: parseFloat(destLon),
      name: destName,
      address: destAddress
    };

    // Thiết lập danh sách lựa chọn điểm xuất phát
    const originSelect = document.getElementById('gdir-origin-select');
    originSelect.innerHTML = '';

    // Tùy chọn 1: Nếu người dùng truyền vào trạm trước hoặc danh sách trạm (ví dụ từ trip-planner)
    if (config.originOptions && config.originOptions.length > 0) {
      config.originOptions.forEach((opt, idx) => {
        const oEl = document.createElement('option');
        oEl.value = `opt_${idx}`;
        oEl.innerText = opt.label;
        oEl.dataset.lat = opt.lat;
        oEl.dataset.lon = opt.lon;
        oEl.dataset.name = opt.name || opt.label;
        if (opt.selected || idx === 0) oEl.selected = true;
        originSelect.appendChild(oEl);
      });
    } else if (config.originLat && config.originLon) {
      const oEl = document.createElement('option');
      oEl.value = 'custom_origin';
      oEl.innerText = config.originName || 'Điểm xuất phát ban đầu';
      oEl.dataset.lat = config.originLat;
      oEl.dataset.lon = config.originLon;
      oEl.dataset.name = config.originName || 'Điểm xuất phát';
      oEl.selected = true;
      originSelect.appendChild(oEl);
    } else {
      // Mặc định: Vị trí GPS hoặc trung tâm thành phố Đà Nẵng / thành phố hiện tại
      const oGps = document.createElement('option');
      oGps.value = 'current_location';
      oGps.innerText = '📍 Vị trí GPS hiện tại của tôi';
      oGps.selected = true;
      originSelect.appendChild(oGps);

      const oCenter = document.createElement('option');
      oCenter.value = 'city_center';
      oCenter.innerText = 'Trung tâm thành phố (Đà Nẵng)';
      oCenter.dataset.lat = 16.0544;
      oCenter.dataset.lon = 108.2022;
      oCenter.dataset.name = 'Trung tâm Đà Nẵng';
      originSelect.appendChild(oCenter);
    }

    // Hiển thị tên điểm đến sạch đẹp
    const destDisplay = destAddress ? `${destName} (${destAddress})` : destName;
    document.getElementById('gdir-dest-text').innerText = destDisplay;
    document.getElementById('gdir-title').innerText = `Chỉ đường đến: ${destName}`;

    // Cập nhật phương tiện mặc định: Ô tô
    gDirState.mode = config.mode || 'd';
    updateTransportButtonsUI();

    // Chế độ xem mặc định: Bản đồ
    window.switchGoogleDirectionsView('map');

    // Hiển thị modal
    const modal = document.getElementById('google-maps-directions-modal');
    modal.style.display = 'flex';

    // Tải lộ trình Google Maps
    loadGoogleDirectionsRoute();
  };

  /**
   * Đóng modal
   */
  window.closeGoogleDirectionsModal = function () {
    const modal = document.getElementById('google-maps-directions-modal');
    if (modal) modal.style.display = 'none';
  };

  /**
   * Thay đổi phương tiện di chuyển (d: car, b: bike, w: walk, r: transit)
   */
  window.setGoogleDirectionsMode = function (mode) {
    gDirState.mode = mode;
    updateTransportButtonsUI();
    loadGoogleDirectionsRoute();
    if (gDirState.activeView === 'steps') {
      loadTurnByTurnSteps();
    }
  };

  function updateTransportButtonsUI() {
    const modes = ['d', 'b', 'w', 'r'];
    modes.forEach(m => {
      const btn = document.getElementById(`gdir-mode-${m}`);
      if (!btn) return;
      if (m === gDirState.mode) {
        btn.style.background = '#1e293b';
        btn.style.color = '#ffffff';
      } else {
        btn.style.background = 'transparent';
        btn.style.color = '#475569';
      }
    });
  }

  /**
   * Chuyển đổi giữa chế độ Bản đồ Google Maps và Danh sách bước chỉ đường
   */
  window.switchGoogleDirectionsView = function (view) {
    gDirState.activeView = view;
    const mapPanel = document.getElementById('gdir-map-panel');
    const stepsPanel = document.getElementById('gdir-steps-panel');
    const btnMap = document.getElementById('gdir-view-map-btn');
    const btnSteps = document.getElementById('gdir-view-steps-btn');

    if (view === 'map') {
      mapPanel.style.display = 'block';
      stepsPanel.style.display = 'none';
      btnMap.style.background = '#ffffff';
      btnMap.style.color = '#0f172a';
      btnMap.style.boxShadow = '0 1px 3px rgba(0,0,0,0.1)';
      btnSteps.style.background = 'transparent';
      btnSteps.style.color = '#64748b';
      btnSteps.style.boxShadow = 'none';
    } else {
      mapPanel.style.display = 'none';
      stepsPanel.style.display = 'block';
      btnSteps.style.background = '#ffffff';
      btnSteps.style.color = '#0f172a';
      btnSteps.style.boxShadow = '0 1px 3px rgba(0,0,0,0.1)';
      btnMap.style.background = 'transparent';
      btnMap.style.color = '#64748b';
      btnMap.style.boxShadow = 'none';
      loadTurnByTurnSteps();
    }
  };

  /**
   * Đảo chiều Điểm xuất phát <-> Điểm đến
   */
  window.swapGoogleDirectionsPoints = function () {
    const curDest = gDirState.destination;
    const select = document.getElementById('gdir-origin-select');
    const selectedOpt = select.options[select.selectedIndex];

    let originLat = selectedOpt ? selectedOpt.dataset.lat : null;
    let originLon = selectedOpt ? selectedOpt.dataset.lon : null;
    let originName = selectedOpt ? selectedOpt.dataset.name || selectedOpt.innerText : 'Điểm xuất phát';

    if (!originLat || !originLon) {
      if (gDirState.userGps) {
        originLat = gDirState.userGps.lat;
        originLon = gDirState.userGps.lon;
      } else {
        originLat = 16.0544;
        originLon = 108.2022;
      }
    }

    // Hoán đổi
    gDirState.destination = {
      lat: parseFloat(originLat),
      lon: parseFloat(originLon),
      name: originName,
      address: ''
    };

    // Đặt lại origin select thành điểm đích cũ
    select.innerHTML = '';
    const newOpt = document.createElement('option');
    newOpt.value = 'swapped_origin';
    newOpt.dataset.lat = curDest.lat;
    newOpt.dataset.lon = curDest.lon;
    newOpt.dataset.name = curDest.name;
    newOpt.innerText = curDest.name;
    newOpt.selected = true;
    select.appendChild(newOpt);

    document.getElementById('gdir-dest-text').innerText = originName;
    document.getElementById('gdir-title').innerText = `Chỉ đường đến: ${originName}`;

    loadGoogleDirectionsRoute();
  };

  /**
   * Sử dụng vị trí GPS hiện tại của người dùng
   */
  window.useMyGpsAsOrigin = function () {
    if (!navigator.geolocation) {
      alert("Trình duyệt không hỗ trợ định vị GPS!");
      return;
    }

    const select = document.getElementById('gdir-origin-select');
    let gpsOpt = select.querySelector('option[value="current_location"]');
    if (!gpsOpt) {
      gpsOpt = document.createElement('option');
      gpsOpt.value = 'current_location';
      gpsOpt.innerText = '📍 Vị trí GPS hiện tại của tôi';
      select.insertBefore(gpsOpt, select.firstChild);
    }
    select.value = 'current_location';

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        gDirState.userGps = {
          lat: pos.coords.latitude,
          lon: pos.coords.longitude
        };
        gpsOpt.dataset.lat = pos.coords.latitude;
        gpsOpt.dataset.lon = pos.coords.longitude;
        gpsOpt.dataset.name = "Vị trí GPS của tôi";
        loadGoogleDirectionsRoute();
      },
      (err) => {
        console.warn("Không thể lấy GPS chính xác, dùng Current+Location mặc định của Google Maps:", err);
        loadGoogleDirectionsRoute();
      },
      { enableHighAccuracy: true, timeout: 6000 }
    );
  };

  window.onGoogleDirectionsOriginChanged = function () {
    loadGoogleDirectionsRoute();
    if (gDirState.activeView === 'steps') {
      loadTurnByTurnSteps();
    }
  };

  /**
   * Phóng to / Thu nhỏ Modal
   */
  window.toggleGoogleDirectionsFullscreen = function () {
    const card = document.getElementById('gdir-modal-card');
    const icon = document.getElementById('gdir-fs-icon');
    gDirState.isFullscreen = !gDirState.isFullscreen;

    if (gDirState.isFullscreen) {
      card.style.maxWidth = '100vw';
      card.style.height = '100vh';
      card.style.maxHeight = '100vh';
      card.style.borderRadius = '0px';
      icon.innerText = '🗗';
    } else {
      card.style.maxWidth = '960px';
      card.style.height = '90vh';
      card.style.maxHeight = '800px';
      card.style.borderRadius = '24px';
      icon.innerText = '⛶';
    }
  };

  /**
   * 3. Nạp đường đi vào Iframe Google Maps thực tế
   */
  function loadGoogleDirectionsRoute() {
    const iframe = document.getElementById('gdir-iframe');
    const loading = document.getElementById('gdir-iframe-loading');
    if (!iframe) return;

    if (loading) loading.style.display = 'flex';

    const select = document.getElementById('gdir-origin-select');
    const selectedOpt = select.options[select.selectedIndex];

    let saddr = 'Current+Location';
    if (selectedOpt && selectedOpt.dataset.lat && selectedOpt.dataset.lon) {
      saddr = `${selectedOpt.dataset.lat},${selectedOpt.dataset.lon}`;
    } else if (gDirState.userGps) {
      saddr = `${gDirState.userGps.lat},${gDirState.userGps.lon}`;
    }

    let daddr = `${gDirState.destination.lat},${gDirState.destination.lon}`;

    // Link Google Maps Directions nhúng chuẩn
    const gmapsUrl = `https://maps.google.com/maps?saddr=${encodeURIComponent(saddr)}&daddr=${encodeURIComponent(daddr)}&dirflg=${gDirState.mode}&hl=vi&output=embed`;
    iframe.src = gmapsUrl;
  }

  /**
   * 4. Tính toán và nạp danh sách bước rẽ (Turn-by-turn) bằng OSRM
   */
  async function loadTurnByTurnSteps() {
    const list = document.getElementById('gdir-steps-list');
    const badge = document.getElementById('gdir-steps-summary-badge');
    if (!list) return;

    list.innerHTML = `
      <div style="text-align: center; padding: 40px 0; color: #64748b;">
        <div style="width: 28px; height: 28px; border: 3px solid #e2e8f0; border-top-color: #2563eb; border-radius: 50%; animation: gdir-spin 0.8s linear infinite; margin: 0 auto 8px auto;"></div>
        <p style="font-size: 12px; font-weight: 700; margin: 0;">Đang phân tích chi tiết tuyến đường...</p>
      </div>
    `;

    const select = document.getElementById('gdir-origin-select');
    const selectedOpt = select.options[select.selectedIndex];

    let originLat = selectedOpt ? selectedOpt.dataset.lat : null;
    let originLon = selectedOpt ? selectedOpt.dataset.lon : null;

    if (!originLat || !originLon) {
      if (gDirState.userGps) {
        originLat = gDirState.userGps.lat;
        originLon = gDirState.userGps.lon;
      } else {
        originLat = 16.0544;
        originLon = 108.2022;
      }
    }

    const destLat = gDirState.destination.lat;
    const destLon = gDirState.destination.lon;

    const osrmProfile = (gDirState.mode === 'w') ? 'walking' : 'driving';
    const osrmUrl = `https://router.project-osrm.org/route/v1/${osrmProfile}/${originLon},${originLat};${destLon},${destLat}?overview=full&geometries=geojson&steps=true`;

    try {
      const res = await fetch(osrmUrl);
      if (res.ok) {
        const data = await res.json();
        if (data.routes && data.routes.length > 0) {
          const route = data.routes[0];
          const distKm = (route.distance / 1000).toFixed(1);
          let durationMin = Math.ceil(route.duration / 60);

          if (gDirState.mode === 'b') durationMin = Math.max(2, Math.ceil((route.distance / 1000) / 28 * 60));
          if (gDirState.mode === 'w') durationMin = Math.max(3, Math.ceil((route.distance / 1000) / 4.5 * 60));

          if (badge) badge.innerText = `${distKm} km • ${durationMin} phút`;

          const steps = (route.legs && route.legs[0] && route.legs[0].steps) ? route.legs[0].steps : [];
          renderStepsHTML(steps, distKm);
          return;
        }
      }
      throw new Error("Không có dữ liệu OSRM");
    } catch (e) {
      // Fallback
      list.innerHTML = `
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 16px; padding: 16px;">
          <h5 style="margin: 0 0 6px 0; font-size: 13px; font-weight: 800; color: #0f172a;">Lộ trình qua trục đường chính</h5>
          <p style="margin: 0; font-size: 12px; color: #475569;">Xuất phát từ vị trí của bạn và di chuyển theo chỉ dẫn trực quan trên bản đồ Google Maps để đến <strong>${gDirState.destination.name}</strong>.</p>
        </div>
      `;
    }
  }

  function renderStepsHTML(steps, totalKm) {
    const list = document.getElementById('gdir-steps-list');
    if (!list || steps.length === 0) return;

    list.innerHTML = steps.map((s, idx) => {
      const isFirst = idx === 0;
      const isLast = idx === steps.length - 1;
      const distM = Math.round(s.distance || 0);
      const distStr = distM > 1000 ? `${(distM / 1000).toFixed(1)} km` : (distM > 20 ? `${distM} m` : '');

      let icon = '➜';
      let title = s.name ? `Đi vào <strong>${s.name}</strong>` : 'Đi thẳng tiếp tục';
      if (isFirst) {
        icon = '●';
        title = `Xuất phát hướng về <strong>${s.name || gDirState.destination.name}</strong>`;
      } else if (isLast) {
        icon = '★';
        title = `Đến nơi: <strong>${gDirState.destination.name}</strong>`;
      } else if (s.maneuver && s.maneuver.modifier) {
        if (s.maneuver.modifier.includes('right')) icon = '⮡';
        if (s.maneuver.modifier.includes('left')) icon = '⮠';
      }

      return `
        <div style="display: flex; align-items: flex-start; gap: 12px; padding: 10px 14px; background: ${isLast ? '#ecfdf5' : '#f8fafc'}; border: 1px solid ${isLast ? '#a7f3d0' : '#e2e8f0'}; border-radius: 14px;">
          <div style="width: 26px; height: 26px; border-radius: 50%; background: ${isLast ? '#059669' : '#1e293b'}; color: #ffffff; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 900; shrink: 0; margin-top: 1px;">
            ${icon}
          </div>
          <div style="flex: 1; min-width: 0;">
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
              <span style="font-size: 12px; font-weight: 800; color: #0f172a;">${title}</span>
              ${distStr ? `<span style="font-size: 10px; font-weight: 800; color: #64748b; background: #ffffff; padding: 2px 6px; border-radius: 6px; border: 1px solid #cbd5e1; white-space: nowrap;">${distStr}</span>` : ''}
            </div>
          </div>
        </div>
      `;
    }).join('');
  }

  /**
   * 5. SMART GLOBAL INTERCEPTOR:
   * Tự động bắt sự kiện click trên TẤT CẢ các card hoặc nút có chữ "Chỉ đường" hoặc link google.com/maps
   * và kích hoạt Modal Google Maps trực tiếp, không bao giờ chuyển tab mới!
   */
  document.addEventListener('click', function (e) {
    const target = e.target.closest('a, button');
    if (!target) return;

    const href = target.getAttribute('href') || '';
    const text = (target.textContent || '').trim().toLowerCase();
    const title = (target.getAttribute('title') || '').toLowerCase();
    const id = target.id || '';

    // Điều kiện nhận diện nút / link chỉ đường:
    const isDirectionsTrigger =
      id === 'm-map-btn' ||
      id === 'm-map-url' ||
      text.includes('chỉ đường') ||
      title.includes('chỉ đường') ||
      href.includes('google.com/maps') ||
      href.includes('maps.google.com');

    if (isDirectionsTrigger) {
      e.preventDefault();
      e.stopPropagation();

      // Trích xuất tọa độ & tên điểm đến từ element hoặc card chứa nó
      let lat = target.dataset.lat || target.dataset.latitude;
      let lon = target.dataset.lon || target.dataset.longitude;
      let name = target.dataset.name || '';
      let address = target.dataset.address || '';

      // Nếu không có trong dataset, thử parse từ href Google Maps URL
      if ((!lat || !lon) && href) {
        // Pattern 1: /Current+Location/lat,lon
        const matchLoc = href.match(/Current\+Location\/([-\d.]+),([-\d.]+)/i);
        if (matchLoc) {
          lat = matchLoc[1];
          lon = matchLoc[2];
        }
        // Pattern 2: ?q=lat,lon hoặc &destination=lat,lon hoặc &daddr=lat,lon
        if (!lat || !lon) {
          const matchParam = href.match(/[?&](?:q|destination|daddr)=([-\d.]+),([-\d.]+)/i);
          if (matchParam) {
            lat = matchParam[1];
            lon = matchParam[2];
          }
        }
        // Pattern 3: /@lat,lon
        if (!lat || !lon) {
          const matchAt = href.match(/@([-\d.]+),([-\d.]+)/i);
          if (matchAt) {
            lat = matchAt[1];
            lon = matchAt[2];
          }
        }
      }

      // Nếu không có tên, tìm trong card cha
      if (!name) {
        const card = target.closest('article, .bg-white, .rounded-2xl, .card, .p-4, .p-3, .d-flex');
        if (card) {
          const titleEl = card.querySelector('h3, h4, h5, h6, .fw-bold, .font-black');
          if (titleEl) name = titleEl.innerText.trim();
        }
      }

      // Nếu vẫn chưa có, kiểm tra nếu đang ở trong Modal Chi tiết hiện tại
      if ((!lat || !lon) && document.getElementById('detail-modal')) {
        const coordsEl = document.getElementById('m-coords');
        if (coordsEl && coordsEl.innerText.includes(',')) {
          const parts = coordsEl.innerText.split(',');
          lat = parts[0].trim();
          lon = parts[1].trim();
        }
        const mTitle = document.getElementById('m-title');
        if (mTitle) name = mTitle.innerText.trim();
        const mAddr = document.getElementById('m-address');
        if (mAddr) address = mAddr.innerText.trim();
      }

      // Giá trị dự phòng nếu không tìm thấy tọa độ
      lat = lat || 16.0544;
      lon = lon || 108.2022;
      name = name || 'Địa điểm du lịch';

      // Mở modal chỉ đường Google Maps trực tiếp ngay trên trang
      window.openGoogleDirectionsModal({
        destLat: lat,
        destLon: lon,
        destName: name,
        destAddress: address
      });
    }
  }, true);

})();
