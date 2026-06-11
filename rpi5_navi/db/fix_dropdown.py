with open('/home/pi/projects/dms/rpi5_navi/flask_server/templates/control_center.html', 'r') as f:
    c = f.read()

old = '''  // 날짜별 그룹화
  const dateGroups = {};
  sessionKeys.forEach(k => {
    const date = k.slice(0,8); // 20260610
    const time = k.slice(9,13); // 0830
    const dateLabel = date.replace(/(\d{4})(\d{2})(\d{2})/, '$1-$2-$3');
    const timeLabel = time.slice(0,2) + ':' + time.slice(2,4);
    if (!dateGroups[date]) dateGroups[date] = [];
    dateGroups[date].push({ key: k, dateLabel, timeLabel });
  });

  const sessionOptions = Object.entries(dateGroups).map(([date, sessions]) => {
    if (sessions.length === 1) {
      return `<option value="${sessions[0].key}">${sessions[0].dateLabel}</option>`;
    } else {
      return sessions.map((s, i) =>
        `<option value="${s.key}">${s.dateLabel} ${s.timeLabel} (${i+1}회차)</option>`
      ).join('');
    }
  }).join('');'''

new = '''  // 날짜별 그룹화
  const dateGroups = {};
  sessionKeys.forEach(k => {
    const date = k.slice(0,8);
    const timePart = k.slice(9);
    const hh = timePart.slice(0,2);
    const mm = timePart.slice(2,4);
    const dateLabel = date.replace(/(\d{4})(\d{2})(\d{2})/, '$1-$2-$3');
    const timeLabel = hh + ':' + mm;
    if (!dateGroups[date]) dateGroups[date] = [];
    dateGroups[date].push({ key: k, dateLabel, timeLabel });
  });

  const sessionOptions = Object.entries(dateGroups).map(([date, sessions]) => {
    if (sessions.length === 1) {
      return `<option value="${sessions[0].key}">${sessions[0].dateLabel} ${sessions[0].timeLabel}</option>`;
    } else {
      return sessions.map((s, i) =>
        `<option value="${s.key}">${s.dateLabel} ${s.timeLabel} (${i+1}회차)</option>`
      ).join('');
    }
  }).join('');'''

if old in c:
    c = c.replace(old, new)
    print("드롭다운 교체 성공")
else:
    print("못 찾음")

with open('/home/pi/projects/dms/rpi5_navi/flask_server/templates/control_center.html', 'w') as f:
    f.write(c)
