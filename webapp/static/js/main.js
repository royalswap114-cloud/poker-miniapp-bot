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

        console.log("[배너] API 응답:", banners);
        console.log("[배너] 배너 개수:", banners.length);

        if (!banners.length) {
            // DB에 배너가 없을 때 기본 메시지 표시
            const slide = document.createElement("div");
            slide.className = "swiper-slide banner-slide";
            slide.innerHTML = `
                <div class="banner-placeholder">
                    <h2>배너를 추가해주세요</h2>
                    <p>관리자에게 문의: @royalswap_kr</p>
                    <p style="font-size: 11px; opacity: 0.7; margin-top: 8px;">/admin → 🎨 배너 관리</p>
                </div>
            `;
            container.appendChild(slide);
            console.log("[배너] 배너가 없어 기본 메시지 표시");
        } else {
            for (const b of banners) {
                const slide = document.createElement("div");
                slide.className = "swiper-slide banner-slide";

                const imageUrl = b.image_url || "";
                const linkUrl = b.link_url || "#";
                const bannerTitle = b.title || "배너";
                const bannerDesc = b.description || "";

                console.log(`[배너] 로딩 시도: ID=${b.id}, URL=${imageUrl}`);

                // 배너 전체를 클릭 가능한 링크로 처리
                // GIF, PNG, JPG 모두 지원 (GIF는 자동으로 애니메이션 재생됨)
                // 이미지 로딩 에러 시 플레이스홀더 표시
                slide.innerHTML = `
                    <a class="banner-image-link" href="${linkUrl}" target="_blank" rel="noopener noreferrer">
                        <img 
                            src="${imageUrl}" 
                            alt="${bannerTitle}" 
                            class="banner-image" 
                            loading="lazy"
                            onerror="console.error('[배너] 이미지 로딩 실패:', '${imageUrl}'); this.style.display='none'; const placeholder = this.parentElement.querySelector('.banner-placeholder'); if (placeholder) placeholder.style.display='flex';"
                        />
                        <div class="banner-placeholder" style="display:none;">
                            <h2>${bannerTitle}</h2>
                            ${bannerDesc ? `<p>${bannerDesc}</p>` : ""}
                            <p style="font-size: 11px; opacity: 0.7; margin-top: 8px;">@royalswap_kr</p>
                        </div>
                        <div class="banner-overlay">
                            ${b.title ? `<div class="banner-title">${b.title}</div>` : ""}
                            ${b.description ? `<div class="banner-desc">${b.description}</div>` : ""}
                            ${b.link_url ? `<div class="banner-link-text">${b.link_url}</div>` : ""}
                        </div>
                    </a>
                `;
                container.appendChild(slide);
            }
        }

        if (swiperInstance) {
            swiperInstance.update();
        } else {
            swiperInstance = new Swiper(".banner-swiper", {
                loop: true,
                autoplay: {
                    delay: 4000, // 4초마다 자동 슬라이드
                    disableOnInteraction: false,
                },
                pagination: {
                    el: ".swiper-pagination",
                    clickable: true,
                },
                navigation: {
                    nextEl: ".swiper-button-next",
                    prevEl: ".swiper-button-prev",
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
                <div class="info-row">
                    <span class="info-icon">💰</span>
                    <span class="info-label">블라인드:</span>
                    <span class="info-value">${room.blinds || '-'}</span>
                </div>
                <div class="info-row">
                    <span class="info-icon">💵</span>
                    <span class="info-label">최소 바이인:</span>
                    <span class="info-value">${room.min_buyin || '-'}</span>
                </div>
                <div class="info-row">
                    <span class="info-icon">👥</span>
                    <span class="info-label">인원:</span>
                    <span class="info-value">${room.current_players || 0} / ${room.max_players || 10} Playing</span>
                </div>
                <div class="info-row">
                    <span class="info-icon">⏰</span>
                    <span class="info-label">게임 시간:</span>
                    <span class="info-value">${room.game_time || '-'}</span>
                </div>
            </div>
            <div class="room-actions">
                <button class="btn primary">🎮 게임 참여하기</button>
                <button class="btn outline">💵 바인/아웃</button>
            </div>
        `;

        const [joinBtn, buyinBtn] = card.querySelectorAll("button");
        joinBtn.addEventListener("click", () => joinGame(room));
        buyinBtn.addEventListener("click", () => handleBuyIn(room));

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

function handleBuyIn(room) {
    // 바인/아웃 담당자 텔레그램으로 연결
    if (!room.contact_telegram) {
        const msg = `바인/아웃 담당자 정보가 없습니다.\n\n방: ${room.room_name}\n\n운영자에게 문의해 주세요.`;
        if (tg) {
            tg.showAlert(msg);
        } else {
            alert(msg);
        }
        return;
    }
    
    const telegramUrl = 'https://t.me/' + room.contact_telegram;
    
    console.log('[BUY_IN] 텔레그램 연결:', room.contact_telegram, telegramUrl);
    
    if (tg) {
        // Telegram WebApp에서 열기
        tg.openTelegramLink(telegramUrl);
    } else {
        // 일반 브라우저에서 새 탭으로 열기
        window.open(telegramUrl, '_blank');
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
    // 하단 네비게이션이 링크로 변경되어 JavaScript 이벤트 핸들러가 필요 없음
    // 프로필 모달은 더 이상 사용하지 않음 (별도 페이지로 이동)
    
    // 현재 페이지에 따라 active 클래스 설정
    const currentPath = window.location.pathname;
    const navItems = document.querySelectorAll('.nav-item');
    
    navItems.forEach(item => {
        const href = item.getAttribute('href');
        if (href === currentPath) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });
    
    // URL 파라미터를 프로필 링크에 유지
    const urlParams = new URLSearchParams(window.location.search);
    const profileNavLink = document.getElementById('navProfileLink');
    if (profileNavLink && urlParams.toString()) {
        const profileUrl = '/profile?' + urlParams.toString();
        profileNavLink.setAttribute('href', profileUrl);
        console.log('[main.js] 프로필 링크 업데이트:', profileUrl);
    }
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



