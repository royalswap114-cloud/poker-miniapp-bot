// URL 파라미터를 모든 내부 링크에 자동으로 추가하는 스크립트

(function() {
    'use strict';
    
    // 현재 URL 파라미터 가져오기
    function getUrlParams() {
        const urlParams = new URLSearchParams(window.location.search);
        const paramsString = urlParams.toString();
        console.log('[URL_PARAMS] 현재 파라미터:', paramsString);
        return paramsString;
    }
    
    // 모든 내부 링크에 파라미터 추가
    function addParamsToLinks() {
        const paramsString = getUrlParams();
        
        if (!paramsString) {
            console.log('[URL_PARAMS] 파라미터 없음');
            return;
        }
        
        // 모든 상대 경로 링크 찾기
        const links = document.querySelectorAll('a[href^="/"]');
        
        links.forEach(link => {
            const href = link.getAttribute('href');
            
            // 이미 파라미터가 있으면 스킵
            if (href && href.includes('?')) {
                return;
            }
            
            // 파라미터 추가
            const newHref = href + '?' + paramsString;
            link.setAttribute('href', newHref);
            
            console.log('[URL_PARAMS] 링크 업데이트:', href, '→', newHref);
        });
    }
    
    // 페이지 로드 시 실행
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', addParamsToLinks);
    } else {
        addParamsToLinks();
    }
    
    // 동적으로 생성된 링크를 위한 MutationObserver
    const observer = new MutationObserver(function(mutations) {
        const paramsString = getUrlParams();
        
        if (!paramsString) return;
        
        mutations.forEach(function(mutation) {
            mutation.addedNodes.forEach(function(node) {
                if (node.nodeType === 1) {
                    // 새로 추가된 링크
                    if (node.tagName === 'A' && node.getAttribute('href')?.startsWith('/')) {
                        const href = node.getAttribute('href');
                        if (href && !href.includes('?')) {
                            node.setAttribute('href', href + '?' + paramsString);
                            console.log('[URL_PARAMS] 동적 링크 업데이트:', href, '→', href + '?' + paramsString);
                        }
                    }
                    
                    // 자식 요소의 링크
                    const links = node.querySelectorAll ? node.querySelectorAll('a[href^="/"]') : [];
                    links.forEach(link => {
                        const href = link.getAttribute('href');
                        if (href && !href.includes('?')) {
                            link.setAttribute('href', href + '?' + paramsString);
                            console.log('[URL_PARAMS] 자식 링크 업데이트:', href, '→', href + '?' + paramsString);
                        }
                    });
                }
            });
        });
    });
    
    // DOM이 준비되면 observer 시작
    if (document.body) {
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    } else {
        document.addEventListener('DOMContentLoaded', function() {
            observer.observe(document.body, {
                childList: true,
                subtree: true
            });
        });
    }
    
})();

