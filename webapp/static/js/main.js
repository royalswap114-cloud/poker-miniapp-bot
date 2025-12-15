// webapp/static/js/main.js
// Telegram WebApp 초기화 + 방 리스트/배너 렌더링 + 프로필 모달

let tg = null;
let swiperInstance = null;
let currentUser = null;

function initTelegram() {
    // Telegram WebApp 객체
    if (window.Telegram && window.Telegram.WebApp) {
        tg = window.Telegram.WebApp;
        tg.ready();
        currentUser = tg.initDataUnsafe.user || null;
    } else {
        console.warn("Telegram WebApp 객체를 찾을 수 없습니다. 일반 브라우저에서 테스트 중일 수 있습니다.");
    }
}

async function fetchJSON(url, options = {}) {
    const res = await fetch(url, options);
    if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
    }
    return res.json();
}

async function loadBanners() {
    try {
        const banners = await fetchJSON("/api/banners");
        const container = document.getElementById("banner-container");
        container.innerHTML = "";

        if (!banners.length) {
            // 기본 배너
            const slide = document.createElement("div");
            slide.className = "swiper-slide banner-slide";
            slide.innerHTML = `
                <div class="banner-title">JACKPOT 100만원</div>
                <div class="banner-desc">royalswap_kr 채널을 확인하세요.</div>
                <div class="banner-link">@royalswap_kr</div>
            `;
            container.appendChild(slide);
        } else {
            for (const b of banners) {
                const slide = document.createElement("div");
                slide.className = "swiper-slide banner-slide";
                slide.innerHTML = `
                    <div class="banner-title">${b.title || ""}</div>
                    <div class="banner-desc">${b.description || ""}</div>
                    ${b.link_url ? `<div class="banner-link">${b.link_url}</div>` : ""}
                `;
                container.appendChild(slide);
            }
        }

        if (swiperInstance) {
            swiperInstance.update();
        } else {
            swiperInstance = new Swiper(".swiper", {
                loop: true,
                autoplay: {
                    delay: 4000,
                },
                pagination: {
                    el: ".swiper-pagination",
                    clickable: true,
                },
            });
        }
    } catch (e) {
        console.error("배너 로드 실패:", e);
    }
}

function renderRooms(rooms) {
    const list = document.getElementById("room-list");
    list.innerHTML = "";

    if (!rooms.length) {
        const empty = document.createElement("div");
        empty.className = "welcome-card";
        empty.innerHTML = "<p>현재 활성화된 포커방이 없습니다.</p>";
        list.appendChild(empty);
        return;
    }

    for (const room of rooms) {
        const card = document.createElement("section");
        card.className = "room-card";

        card.innerHTML = `
            <div class="room-header">
                <h2 class="room-name">${room.room_name}</h2>
                <span class="room-status">${room.status.toUpperCase()}</span>
            </div>
            <div class="room-meta">
                <div>🪙 블라인드: ${room.blinds || "-"}</div>
                <div>👥 ${room.current_players || 0} / ${room.max_players || 9} Playing</div>
                <div>💰 최소 바이인: ${room.min_buyin || "-"}</div>
                <div>⏱️ ${room.game_time || "-"}</div>
            </div>
            <div class="room-actions">
                <button class="btn primary">🎮 게임 참여하기</button>
                <button class="btn outline">💵 바인/아웃</button>
            </div>
        `;

        const [joinBtn, buyinBtn] = card.querySelectorAll("button");
        joinBtn.addEventListener("click", () => joinGame(room));
        buyinBtn.addEventListener("click", () => showBuyinInfo(room));

        list.appendChild(card);
    }
}

async function loadRooms() {
    try {
        const rooms = await fetchJSON("/api/rooms");
        renderRooms(rooms);
    } catch (e) {
        console.error("방 목록 로드 실패:", e);
    }
}

async function joinGame(room) {
    // pokernow.club 링크로 이동
    if (tg) {
        tg.openLink(room.room_url);
    } else {
        window.open(room.room_url, "_blank");
    }

    // 참여 기록 API 호출
    if (!currentUser) return;

    const params = new URLSearchParams({
        user_id: currentUser.id,
        username: currentUser.username || "",
        first_name: currentUser.first_name || "",
    });

    try {
        await fetchJSON(`/api/rooms/${room.id}/join?` + params.toString(), {
            method: "POST",
        });
    } catch (e) {
        console.error("참여 기록 실패:", e);
    }
}

function showBuyinInfo(room) {
    const msg = `바인/아웃 안내\n\n방: ${room.room_name}\n최소 바이인: ${
        room.min_buyin || "-"
    }\n\n바인/아웃 관련 문의는 운영자에게 문의해 주세요.`;
    if (tg) {
        tg.showAlert(msg);
    } else {
        alert(msg);
    }
}

async function loadProfile() {
    const profileInfo = document.getElementById("profile-info");
    if (!currentUser) {
        profileInfo.textContent = "텔레그램 WebApp 환경이 아닙니다.";
        return;
    }

    try {
        const data = await fetchJSON(`/api/users/${currentUser.id}`);
        profileInfo.innerHTML = `
            👤 @${data.username || currentUser.id}<br/>
            참여 횟수: ${data.join_count} 회<br/>
            총 플레이 시간: ${data.total_playtime} 초<br/>
            마지막 플레이: ${data.last_played || "기록 없음"}
        `;
    } catch (e) {
        profileInfo.textContent = "아직 기록된 참여 내역이 없습니다.";
    }
}

function setupNav() {
    const navHome = document.getElementById("nav-home");
    const navProfile = document.getElementById("nav-profile");
    const profileModal = document.getElementById("profile-modal");
    const closeProfile = document.getElementById("close-profile");

    navHome.addEventListener("click", () => {
        navHome.classList.add("active");
        navProfile.classList.remove("active");
        profileModal.classList.add("hidden");
    });

    navProfile.addEventListener("click", async () => {
        navHome.classList.remove("active");
        navProfile.classList.add("active");
        await loadProfile();
        profileModal.classList.remove("hidden");
    });

    closeProfile.addEventListener("click", () => {
        profileModal.classList.add("hidden");
        navProfile.classList.remove("active");
        navHome.classList.add("active");
    });
}

function startAutoRefresh() {
    loadRooms();
    setInterval(loadRooms, 3000);
}

document.addEventListener("DOMContentLoaded", async () => {
    initTelegram();
    setupNav();
    await loadBanners();
    await loadRooms();
    startAutoRefresh();
});



