(() => {
  const data = window.TSUCHIURA_DATA;
  const [LON_UNIT, LAT_UNIT] = data.meshSize;
  const $ = (id) => document.getElementById(id);

  // メッシュ人口の累積和 (メッシュ抽選用)
  const cumulative = [];
  let total = 0;
  for (const m of data.meshes) {
    total += m.n;
    cumulative.push(total);
  }

  // 分布が不明なメッシュ用の市全体の年齢・性別分布
  const cityDist = data.ageClasses.map((_, i) =>
    [0, 1].map((s) => Object.values(data.dists).reduce((sum, d) => sum + d[i][s], 0)),
  );

  const randInt = (min, max) => min + Math.floor(Math.random() * (max - min + 1));
  const classIndexIsLast = (i) => i === data.ageClasses.length - 1;

  function pickMesh() {
    const r = Math.random() * total;
    let lo = 0;
    let hi = cumulative.length - 1;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (cumulative[mid] > r) hi = mid;
      else lo = mid + 1;
    }
    return data.meshes[lo];
  }

  // 階級×性別の人数に比例して1つ選ぶ
  function pickAgeSex(dist) {
    const sum = dist.reduce((s, [m, f]) => s + m + f, 0);
    let r = Math.random() * sum;
    for (let i = 0; i < dist.length; i++) {
      for (let s = 0; s < 2; s++) {
        r -= dist[i][s];
        if (r < 0) return { classIndex: i, sex: s };
      }
    }
    return { classIndex: dist.length - 1, sex: 1 };
  }

  function becomeSomeone() {
    const mesh = pickMesh();
    const lon = mesh.x + Math.random() * LON_UNIT;
    const lat = mesh.y + Math.random() * LAT_UNIT;

    const distKey = mesh.d === undefined ? mesh.c : mesh.d;
    const dist = distKey ? data.dists[distKey] : cityDist;
    const { classIndex, sex } = pickAgeSex(dist);
    const [ageMin, ageMax] = data.ageClasses[classIndex];
    const age = randInt(ageMin, ageMax);

    return { mesh, lon, lat, distKey, dist, classIndex, sex, age };
  }

  let mapType = 'm';
  let current = null;

  function mapUrl(p) {
    return `https://maps.google.com/maps?q=${p.lat},${p.lon}&z=17&t=${mapType}&hl=ja&output=embed`;
  }

  function render(p) {
    const [ageMin, ageMax] = data.ageClasses[p.classIndex];
    const classLabel = classIndexIsLast(p.classIndex) ? `${ageMin}歳以上` : `${ageMin}〜${ageMax}歳`;
    const sexLabel = p.sex === 0 ? '男性' : '女性';

    $('age').textContent = p.age;
    $('sex').textContent = sexLabel;
    $('coord').textContent = `${p.lat.toFixed(5)}, ${p.lon.toFixed(5)}`;
    $('mesh').textContent = p.mesh.c;
    $('mesh-pop').textContent = `${p.mesh.n.toLocaleString()}人`;
    $('peers').textContent = `${classLabel}の${sexLabel}: ${p.dist[p.classIndex][p.sex]}人`;

    const note = $('note');
    if (p.distKey !== p.mesh.c) {
      note.hidden = false;
      note.textContent = p.distKey
        ? `このメッシュは人口が少なく年齢別人口が秘匿されているため、合算先メッシュ ${p.distKey} の年齢・性別構成から選びました。`
        : 'このメッシュは年齢別人口が不明なため、市全体の年齢・性別構成から選びました。';
    } else {
      note.hidden = true;
    }

    $('map').src = mapUrl(p);
    $('gmap-link').href = `https://www.google.com/maps/search/?api=1&query=${p.lat},${p.lon}`;
  }


  function show() {
    current = becomeSomeone();
    render(current);
    $('intro').hidden = true;
    $('result').hidden = false;
    window.scrollTo({ top: 0 });
  }

  $('intro-total').textContent = total.toLocaleString();
  $('start').addEventListener('click', show);
  $('again').addEventListener('click', show);

  document.querySelectorAll('.toggle button').forEach((btn) => {
    btn.addEventListener('click', () => {
      mapType = btn.dataset.type;
      document.querySelectorAll('.toggle button').forEach((b) => b.setAttribute('aria-pressed', String(b === btn)));
      if (current) $('map').src = mapUrl(current);
    });
  });
})();
