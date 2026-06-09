<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>DMS Navi</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="https://cdn.socket.io/4.0.0/socket.io.min.js"></script>
    <script type="text/javascript"
        src="//dapi.kakao.com/v2/maps/sdk.js?appkey=5735c411c5a31661741adfbd0cd7857d&autoload=false&libraries=clusterer">
    </script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', sans-serif; background: #1a1a2e; color: white; height: 100vh; display: flex; flex-direction: column; }
        #topbar { display: flex; align-items: center; justify-content: space-between; padding: 12px 20px; background: #16213e; border-bottom: 2px solid #0f3460; z-index: 100; }
        #topbar .title { font-size: 18px; font-weight: bold; color: #e94560; letter-spacing: 2px; }
        #topbar-right { display: flex; align-items: center; gap: 12px; }
        #conn-icon { font-size: 20px; }
        #topbar .time { font-size: 16px; color: #aaa; }
        #map { flex: 1; width: 100%; position: relative; }
        #bottom-panel { background: #16213e; border-top: 2px solid #0f3460; padding: 12px 20px; display: flex; align-items: center; justify-content: space-between; gap: 16px; }
        #state-card { display: flex; align-items: center; gap: 12px; background: #0f3460; border-radius: 12px; padding: 10px 20px; flex: 1; transition: all 0.3s; }
        #state-icon { font-size: 32px; }
        #state-text { font-size: 14px; color: #aaa; }
        #state-label { font-size: 20px; font-weight: bold; }
        #event-card { background: #0f3460; border-radius: 12px; padding: 10px 16px; text-align: center; min-width: 80px; cursor: pointer; }
        #event-count { font-size: 28px; font-weight: bold; color: #e94560; }
        #event-text { font-size: 11px; color: #aaa; }
        #can-card { background: #0f3460; border-radius: 12px; padding: 10px 16px; text-align: center; min-width: 80px; cursor: pointer; }
        #can-label { font-size: 20px; font-weight: bold; color: #4ecca3; }
        #can-text { font-size: 11px; color: #aaa; }
        #gps-card { background: #0f3460; border-radius: 12px; padding: 10px 16px; text-align: center; min-width: 100px; }
        #gps-status { font-size: 13px; color: #4ecca3; }
        #gps-coords { font-size: 10px; color: #aaa; margin-top: 2px; }
        .state-normal { border-left: 4px solid #4ecca3; }
        .state-caution { border-left: 4px solid #f5a623; background: #1a1a00 !important; }
        .state-drowsy { border-left: 4px solid #e94560; background: #1a0000 !important; animation: pulse 1s infinite; }
        @keyframes pulse { 0%{opacity:1}50%{opacity:0.7}100%{opacity:1} }

        .my-location-wrap { position: relative; width: 60px; height: 60px; pointer-events: none !important; }
        .my-location-dot { width: 18px; height: 18px; background: #4ecca3; border: 3px solid white; border-radius: 50%; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); box-shadow: 0 0 12px rgba(78,204,163,0.9); pointer-events: none !important; }

        /* 졸음 빨간 오버레이 */
        #drowsy-overlay { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(233,69,96,0.35); z-index: 9999; pointer-events: none; }

        /* RPi 연결 끊김 배너 */
        #rpi-disconn-banner { display: none; position: absolute; top: 16px; left: 50%; transform: translateX(-50%); background: rgba(200,0,0,0.85); color: white; font-size: 16px; font-weight: bold; padding: 10px 28px; border-radius: 10px; z-index: 500; letter-spacing: 1px; white-space: nowrap; }

        /* 팝업 공통 */
        .popup-overlay { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); z-index: 1999; }
        .popup-box { display: none; position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); background: #16213e; border: 2px solid #e94560; border-radius: 16px; padding: 20px; z-index: 2000; width: 85vw; max-width: 400px; max-height: 70vh; overflow-y: auto; -webkit-overflow-scrolling: touch; }
        .popup-box h3 { color: #e94560; margin-bottom: 12px; font-size: 16px; position: sticky; top: 0; background: #16213e; padding-bottom: 8px; }
        .popup-close { background: #e94560; border: none; color: white; padding: 8px 20px; border-radius: 8px; cursor: pointer; width: 100%; margin-top: 10px; font-size: 14px; position: sticky; bottom: 0; }
        .event-item { background: #0f3460; border-radius: 8px; padding: 10px; margin-bottom: 8px; font-size: 13px; }
        .event-item .event-state { font-size: 16px; font-weight: bold; margin-bottom: 4px; }
        .event-item .event-detail { color: #aaa; font-size: 11px; }

        /* CAN 팝업 */
        #can-popup { border-color: #4ecca3; }
        #can-popup h3 { color: #4ecca3; }
        #can-log-list { font-family: monospace; font-size: 12px; }
        .can-log-item { background: #0a1628; border-radius: 6px; padding: 6px 10px; margin-bottom: 6px; color: #4ecca3; border-left: 3px solid #4ecca3; }
        #can-popup .popup-close { background: #4ecca3; color: #000; }
    </style>
</head>
<body>
    <div id="drowsy-overlay"></div>

    <div id="topbar">
        <div class="title">🚗 DMS NAVI</div>
        <div id="topbar-right">
            <div id="conn-icon" title="RPi5 연결 상태">📶</div>
            <div class="time" id="clock"></div>
        </div>
    </div>

    <div id="map" style="position:relative;">
        <div id="rpi-disconn-banner">⚠️ RPi5 연결이 끊겼습니다.</div>
    </div>

    <div id="bottom-panel">
        <div id="state-card" class="state-normal">
            <div id="state-icon">😊</div>
            <div>
                <div id="state-text">운전자 상태</div>
                <div id="state-label">정상</div>
            </div>
        </div>
        <div id="event-card" onclick="showEventList()">
            <div id="event-count">0</div>
            <div id="event-text">졸음 이벤트</div>
        </div>
        <div id="can-card" onclick="showCanLog()">
            <div id="can-label">CAN</div>
            <div id="can-text">로그 보기</div>
        </div>
        <div id="gps-card">
            <div id="gps-status">📡 GPS 연결중</div>
            <div id="gps-coords">--</div>
        </div>
    </div>

    <!-- 이벤트 팝업 -->
    <div class="popup-overlay" id="event-overlay" onclick="closeEventList()"></div>
    <div class="popup-box" id="event-popup">
        <h3>😴 졸음 이벤트 목록</h3>
        <div id="event-list"></div>
        <button class="popup-close" onclick="closeEventList()">닫기</button>
    </div>

    <!-- CAN 팝업 -->
    <div class="popup-overlay" id="can-overlay" onclick="closeCanLog()"></div>
    <div class="popup-box" id="can-popup">
        <h3>📡 CAN 수신 로그</h3>
        <div id="can-log-list"></div>
        <button class="popup-close" onclick="closeCanLog()">닫기</button>
    </div>

<script>
const REST_API_KEY = '10f085a36650f957f84ab9743a03e815';
var eventLog = [];
var canLogging = false;
var canLogBuffer = [];

// RPi 연결 상태 추적
var lastAliveTime = Date.now();
var rpiConnected = true;
var rpiDisconnTimer = null;

function updateClock() {
    const now = new Date();
    document.getElementById('clock').innerText =
        now.getHours().toString().padStart(2,'0') + ':' +
        now.getMinutes().toString().padStart(2,'0') + ':' +
        now.getSeconds().toString().padStart(2,'0');
}
setInterval(updateClock, 1000);
updateClock();

// RPi 연결 상태 체크 (1초마다)
setInterval(function() {
    var elapsed = Date.now() - lastAliveTime;
    if (elapsed >= 3000 && rpiConnected) {
        rpiConnected = false;
        document.getElementById('conn-icon').innerText = '📵';
        document.getElementById('rpi-disconn-banner').style.display = 'block';
    }
}, 1000);

// 졸음 빨간 깜빡임
var drowsyInterval = null;
function startDrowsyFlash() {
    if (drowsyInterval) return;
    var overlay = document.getElementById('drowsy-overlay');
    overlay.style.display = 'block';
    overlay.style.opacity = '1';
    drowsyInterval = setInterval(function() {
        overlay.style.opacity = (overlay.style.opacity === '0') ? '1' : '0';
    }, 500);
}
function stopDrowsyFlash() {
    if (drowsyInterval) { clearInterval(drowsyInterval); drowsyInterval = null; }
    var overlay = document.getElementById('drowsy-overlay');
    overlay.style.display = 'none';
    overlay.style.opacity = '1';
}

// 이벤트 팝업
function showEventList() {
    if (eventLog.length === 0) return;
    var list = document.getElementById('event-list');
    list.innerHTML = '';
    eventLog.slice().reverse().forEach(function(e) {
        list.innerHTML += '<div class="event-item"><div class="event-state">😴 졸음</div>' +
            '<div class="event-detail">🕐 ' + e.time + '</div>' +
            '<div class="event-detail">📍 ' + e.address + '</div></div>';
    });
    document.getElementById('event-overlay').style.display = 'block';
    document.getElementById('event-popup').style.display = 'block';
}
function closeEventList() {
    document.getElementById('event-overlay').style.display = 'none';
    document.getElementById('event-popup').style.display = 'none';
}

// CAN 팝업
function showCanLog() {
    canLogging = true;
    canLogBuffer = [];
    document.getElementById('can-log-list').innerHTML = '';
    document.getElementById('can-overlay').style.display = 'block';
    document.getElementById('can-popup').style.display = 'block';
}
function closeCanLog() {
    canLogging = false;
    canLogBuffer = [];
    document.getElementById('can-log-list').innerHTML = '';
    document.getElementById('can-overlay').style.display = 'none';
    document.getElementById('can-popup').style.display = 'none';
}
function appendCanLog(data) {
    if (!canLogging) return;
    var now = new Date();
    var ts = now.getHours().toString().padStart(2,'0') + ':' +
             now.getMinutes().toString().padStart(2,'0') + ':' +
             now.getSeconds().toString().padStart(2,'0') + '.' +
             now.getMilliseconds().toString().padStart(3,'0');
    var stateStr = data.state === 0 ? 'NORMAL' : data.state === 1 ? 'CAUTION' : 'DROWSY';
    var aliveStr = data.alive === 1 ? 'OK' : 'FAIL';
    var logEl = document.getElementById('can-log-list');
    var item = document.createElement('div');
    item.className = 'can-log-item';
    item.innerText = '[' + ts + '] ID:0x100  State:' + data.state +
                     '(' + stateStr + ')  Alive:' + aliveStr;
    logEl.insertBefore(item, logEl.firstChild);
    // 최대 100줄
    while (logEl.children.length > 100) {
        logEl.removeChild(logEl.lastChild);
    }
}

function showNearbyEvents(markerLat, markerLon) {
    var RADIUS = 50;
    var nearby = eventLog.filter(function(e) {
        var dLat = (e.lat - markerLat) * 111000;
        var dLon = (e.lon - markerLon) * 111000 * Math.cos(markerLat * Math.PI / 180);
        return Math.sqrt(dLat*dLat + dLon*dLon) <= RADIUS;
    });
    var list = document.getElementById('event-list');
    list.innerHTML = '';
    nearby.forEach(function(e) {
        list.innerHTML += '<div class="event-item"><div class="event-state">😴 졸음</div>' +
            '<div class="event-detail">🕐 ' + e.time + '</div>' +
            '<div class="event-detail">📍 ' + e.address + '</div></div>';
    });
    document.getElementById('event-overlay').style.display = 'block';
    document.getElementById('event-popup').style.display = 'block';
}

async function getAddress(lat, lon) {
    try {
        const res = await fetch(
            'https://dapi.kakao.com/v2/local/geo/coord2address.json?x=' + lon + '&y=' + lat,
            { headers: { 'Authorization': 'KakaoAK ' + REST_API_KEY } }
        );
        const data = await res.json();
        if (data.documents && data.documents.length > 0) {
            const addr = data.documents[0];
            return addr.road_address ? addr.road_address.address_name : addr.address.address_name;
        }
    } catch(e) {}
    return '주소 불명';
}

kakao.maps.load(function() {
    var map = new kakao.maps.Map(document.getElementById('map'), {
        center: new kakao.maps.LatLng(37.5665, 126.9780),
        level: 4
    });

    var myLocationContent = document.createElement('div');
    myLocationContent.className = 'my-location-wrap';
    myLocationContent.innerHTML = '<div class="my-location-dot"></div>';
    var myLocationOverlay = new kakao.maps.CustomOverlay({
        map: map, content: myLocationContent,
        zIndex: 1, clickable: false, yAnchor: 0.5, xAnchor: 0.5
    });

    var pathCoords = [];
    var polyline = new kakao.maps.Polyline({
        map: map, path: pathCoords,
        strokeWeight: 4, strokeColor: '#4ecca3',
        strokeOpacity: 0.8, strokeStyle: 'solid'
    });

    var clusterer = new kakao.maps.MarkerClusterer({
        map: map, averageCenter: true, minLevel: 3, disableClickZoom: true,
        styles: [{ width:'44px', height:'44px', background:'rgba(233,69,96,0.9)',
            borderRadius:'50%', color:'#fff', textAlign:'center',
            lineHeight:'44px', fontSize:'15px', fontWeight:'bold', border:'3px solid white' }]
    });

    kakao.maps.event.addListener(clusterer, 'clusterclick', function(cluster) {
        var markers = cluster.getMarkers();
        var list = document.getElementById('event-list');
        list.innerHTML = '';
        markers.forEach(function(m) {
            if (m._eventData) {
                var e = m._eventData;
                list.innerHTML += '<div class="event-item"><div class="event-state">😴 졸음</div>' +
                    '<div class="event-detail">🕐 ' + e.time + '</div>' +
                    '<div class="event-detail">📍 ' + e.address + '</div></div>';
            }
        });
        document.getElementById('event-overlay').style.display = 'block';
        document.getElementById('event-popup').style.display = 'block';
    });

    var eventCount = 0;
    var socket = io();

    socket.on('state_update', async function(data) {
        var state = data.state;
        var alive = data.alive !== undefined ? data.alive : 1;
        var lat = data.lat;
        var lon = data.lon;
        var heading = data.heading || 0;

        // RPi 연결 상태 갱신
        lastAliveTime = Date.now();
        if (!rpiConnected) {
            rpiConnected = true;
            document.getElementById('conn-icon').innerText = '📶';
            document.getElementById('rpi-disconn-banner').style.display = 'none';
        }

        // CAN 로그
        appendCanLog(data);

        // 운전자 상태 카드
        var card = document.getElementById('state-card');
        var icon = document.getElementById('state-icon');
        var labelEl = document.getElementById('state-label');

        if (state === 0) {
            icon.innerText = '😊'; labelEl.innerText = '정상';
            card.className = 'state-card state-normal';
            stopDrowsyFlash();
        } else if (state === 1) {
            icon.innerText = '⚠️'; labelEl.innerText = '주의';
            card.className = 'state-card state-caution';
            stopDrowsyFlash(); // 주의는 깜빡임 없음
        } else if (state === 2) {
            icon.innerText = '😴'; labelEl.innerText = '졸음 감지!';
            card.className = 'state-card state-drowsy';
            startDrowsyFlash(); // 졸음만 깜빡임
        }

        if (lat && lon) {
            document.getElementById('gps-status').innerText = '📡 GPS 연결됨';
            document.getElementById('gps-coords').innerText = lat.toFixed(4) + ', ' + lon.toFixed(4);

            var pos = new kakao.maps.LatLng(lat, lon);
            myLocationOverlay.setPosition(pos);
            myLocationContent.style.transform = 'rotate(' + heading + 'deg)';
            pathCoords.push(pos);
            polyline.setPath(pathCoords);
            map.setCenter(pos);

            // 졸음(state=2)일 때만 이벤트 기록 + 마커
            if (state === 2) {
                eventCount++;
                document.getElementById('event-count').innerText = eventCount;

                var address = await getAddress(lat, lon);
                var now = new Date();
                var timeStr = now.getHours().toString().padStart(2,'0') + ':' +
                              now.getMinutes().toString().padStart(2,'0') + ':' +
                              now.getSeconds().toString().padStart(2,'0');

                eventLog.push({ state: state, time: timeStr, address: address, lat: lat, lon: lon });

                var marker = new kakao.maps.Marker({ position: pos });
                marker._eventData = { state: state, time: timeStr, address: address };
                (function(mLat, mLon) {
                    kakao.maps.event.addListener(marker, 'click', function() {
                        showNearbyEvents(mLat, mLon);
                    });
                })(lat, lon);
                clusterer.addMarker(marker);
            }
        }
    });
});
</script>
</body>
</html>
