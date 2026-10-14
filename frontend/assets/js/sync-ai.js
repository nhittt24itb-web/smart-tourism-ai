/**
 * File: frontend/assets/js/sync-ai.js
 */
const SYNC_API_BASE = "http://127.0.0.1:8000/api";
const aiChannel = new BroadcastChannel('smart_tourism_ai_sync');

// Lắng nghe tín hiệu từ các tab khác
aiChannel.onmessage = (event) => {
  if (event.data && (event.data.type === 'FAVORITE_UPDATED' || event.data.type === 'VIEW_TRACKED')) {
    console.log("⚡ [Sync AI] Nhận tín hiệu tương tác mới, reload lại toàn bộ gợi ý:", event.data);
    updateHeartIconsOnScreen();
    reloadCurrentPageRecommendations();
  }
};

function getFavorites() {
  try {
    const list = JSON.parse(localStorage.getItem('user_favorites') || '[]');
    return Array.isArray(list) ? list.map(Number) : [];
  } catch (e) {
    return [];
  }
}
const getLocalFavorites = getFavorites;

async function syncFavoritesFromDatabase() {
  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const userId = user.id || 1;

  try {
    const res = await fetch(`${SYNC_API_BASE}/recommendations/favorites/my-ids?user_id=${userId}`);
    if (res.ok) {
      const data = await res.json();
      const favList = (data.favorite_ids || []).map(Number);
      localStorage.setItem('user_favorites', JSON.stringify(favList));
      updateHeartIconsOnScreen();
    }
  } catch (err) {}
}

function updateHeartIconsOnScreen() {
  const favs = getFavorites();
  document.querySelectorAll('[data-dest-id], .btn-favorite-heart').forEach(btn => {
    let destId = btn.getAttribute('data-dest-id');
    if (!destId) {
      const clickAttr = btn.getAttribute('onclick') || '';
      const match = clickAttr.match(/toggleFavorite\((\d+)/);
      if (match) {
        destId = match[1];
        btn.setAttribute('data-dest-id', destId);
      }
    }
    if (!destId) return;

    const idNum = Number(destId);
    const icon = btn.querySelector('i') || btn;

    if (favs.includes(idNum)) {
      btn.classList.add('favorited', 'text-red-500');
      if (icon.tagName === 'I') icon.className = 'bi bi-heart-fill text-danger';
    } else {
      btn.classList.remove('favorited', 'text-red-500');
      if (icon.tagName === 'I') icon.className = 'bi bi-heart';
    }
  });
}

// BẤM TIM -> LƯU CSDL -> PHÁT TÍN HIỆU ĐA TAB -> LOAD LẠI GỢI Ý NGAY
async function toggleFavorite(destId, btnElement, event) {
  if (event) {
    event.stopPropagation();
    event.preventDefault();
  }

  const idNum = Number(destId);
  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const userId = user.id || 1;

  try {
    const res = await fetch(`${SYNC_API_BASE}/recommendations/favorites/toggle`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, destination_id: idNum })
    });

    if (res.ok) {
      const data = await res.json();
      let favs = getFavorites();

      if (data.is_favorite) {
        if (!favs.includes(idNum)) favs.push(idNum);
      } else {
        favs = favs.filter(id => id !== idNum);
      }

      localStorage.setItem('user_favorites', JSON.stringify(favs));
      updateHeartIconsOnScreen();

      // Báo sang tất cả các tab khác
      aiChannel.postMessage({ type: 'FAVORITE_UPDATED', destination_id: idNum });

      // Reload lại danh sách gợi ý của chính trang hiện tại ngay lập tức
      reloadCurrentPageRecommendations();
    }
  } catch (err) {
    console.error("Lỗi toggle tim:", err);
  }
}

// BẤM XEM POPUP -> GHI NHẬN LƯỢT XEM -> PHÁT TÍN HIỆU CHO AI HỌC
async function trackDestinationView(destId) {
  if (!destId) return;
  const idNum = Number(destId);
  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const userId = user.id || 1;

  try {
    await fetch(`${SYNC_API_BASE}/recommendations/track`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: userId,
        destination_id: idNum,
        action: 'VIEW_POPUP'
      })
    });

    // Thông báo cho các tab khác
    aiChannel.postMessage({ type: 'VIEW_TRACKED', destination_id: idNum });
    
    // Tự động tính toán lại trọng số cho trang chủ
    if (typeof loadDatabaseDestinations === 'function') {
      loadDatabaseDestinations();
    }
  } catch (err) {}
}

// HÀM TỰ ĐỘNG GỌI LẠI LOAD DỮ LIỆU TÙY THEO TRANG
function reloadCurrentPageRecommendations() {
  // Trang Chủ (index.html)
  if (typeof loadDatabaseDestinations === 'function') {
    loadDatabaseDestinations();
  }
  // Trang Khám Phá (explore.html)
  if (typeof loadExploreData === 'function') {
    loadExploreData();
  }
  // Trang Lập Lịch Trình (trip-planner.html)
  if (typeof currentItineraryData !== 'undefined' && currentItineraryData) {
    const city = document.getElementById('param-city') ? document.getElementById('param-city').value : 'Đà Nẵng';
    const interests = typeof getSelectedInterests === 'function' ? getSelectedInterests() : ["Thiên nhiên", "Văn hóa"];

    fetch(`${SYNC_API_BASE}/trips/itinerary`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        city: city,
        days: currentItineraryData.total_days || 3,
        pace: typeof currentPacing !== 'undefined' ? currentPacing : "relax",
        transport: "taxi",
        interests: interests
      })
    })
    .then(r => r.json())
    .then(d => {
      if (d && d.suggested_destinations) {
        availableSuggestions = d.suggested_destinations;
        if (typeof renderActiveDayTimeline === 'function') {
          renderActiveDayTimeline();
        }
      }
    })
    .catch(() => {});
  }
}

document.addEventListener("DOMContentLoaded", () => {
  syncFavoritesFromDatabase();
});