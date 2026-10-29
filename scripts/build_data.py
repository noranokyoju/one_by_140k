"""土浦市にかかる250mメッシュを抽出し、Webアプリ用の人口データを生成する。

入力 (gisdata/):
  ibaraki_gyoseikai.geojson  茨城県の行政界 (国土数値情報 N03)
  MESH05440.json             1次メッシュ5440の250mメッシュ境界
  population.csv             令和2年国勢調査 250mメッシュ 5歳階級別人口 (cp932)

出力:
  web/data/tsuchiura.js  (file:// でも読めるよう window.TSUCHIURA_DATA に代入する)

使い方:
  python3 scripts/build_data.py
"""

import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GIS = ROOT / "gisdata"
OUT = ROOT / "web" / "data" / "tsuchiura.js"

CITY_CODE = "08203"  # 土浦市 (団体コード 082031 の先頭5桁)
CITY_NAME = "土浦市"

# 250mメッシュ1つあたりの大きさ (度)
LAT_UNIT = 1 / 480  # 7.5秒
LON_UNIT = 1 / 320  # 11.25秒

# 5歳階級 (0〜4歳 … 95歳以上) の年齢範囲。95歳以上は上限を設けて一様に選ぶ。
AGE_CLASSES = [(i * 5, i * 5 + 4) for i in range(20)]
AGE_CLASSES[-1] = (95, 104)


def mesh_code(lon, lat):
    """メッシュ南西端の座標から10桁の250mメッシュコードを求める。"""
    iy = round(lat / LAT_UNIT)
    ix = round(lon / LON_UNIT)
    p, ry = divmod(iy, 320)  # 1次: 緯度40分
    u, rx = divmod(ix, 320)  # 1次: 経度1度
    q, ry = divmod(ry, 40)  # 2次: 8分割
    v, rx = divmod(rx, 40)
    r, ry = divmod(ry, 4)  # 3次: 10分割
    w, rx = divmod(rx, 4)
    half = 1 + (rx // 2) + 2 * (ry // 2)  # 4次(1/2): 1=南西 2=南東 3=北西 4=北東
    quarter = 1 + (rx % 2) + 2 * (ry % 2)  # 5次(1/4)
    return f"{p:02d}{u - 100:02d}{q}{v}{r}{w}{half}{quarter}"


def load_city_rings():
    gj = json.loads((GIS / "ibaraki_gyoseikai.geojson").read_text(encoding="utf-8"))
    rings = []
    for f in gj["features"]:
        if f["properties"]["N03_007"] != CITY_CODE:
            continue
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            rings.extend(poly)  # 外周・穴とも偶奇判定で扱う
    if not rings:
        raise SystemExit(f"{CITY_CODE} の行政界が見つかりません")
    return rings


def point_in_rings(x, y, rings):
    inside = False
    for ring in rings:
        for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
            if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                inside = not inside
    return inside


def segment_hits_rect(x1, y1, x2, y2, xmin, ymin, xmax, ymax):
    """線分が矩形の内部を通るか (Liang-Barsky)。"""
    dx, dy = x2 - x1, y2 - y1
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x1 - xmin), (dx, xmax - x1), (-dy, y1 - ymin), (dy, ymax - y1)):
        if p == 0:
            if q < 0:
                return False
        else:
            t = q / p
            if p < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
            if t0 > t1:
                return False
    return True


def extract_meshes(rings):
    """行政界と面積を持って重なる250mメッシュの南西端格子座標を返す。"""
    meshes = json.loads((GIS / "MESH05440.json").read_text())["geometries"]
    grid = {}
    for g in meshes:
        xs = [c[0] for c in g["coordinates"][0]]
        ys = [c[1] for c in g["coordinates"][0]]
        grid[(round(min(xs) / LON_UNIT), round(min(ys) / LAT_UNIT))] = (min(xs), min(ys))

    eps = 1e-9  # 境界線で接するだけのメッシュは除外する
    hit = set()
    # 1) 行政界の辺が通過するメッシュ
    for ring in rings:
        for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
            for ix in range(math.floor(min(x1, x2) / LON_UNIT), math.floor(max(x1, x2) / LON_UNIT) + 1):
                for iy in range(math.floor(min(y1, y2) / LAT_UNIT), math.floor(max(y1, y2) / LAT_UNIT) + 1):
                    if (ix, iy) in hit or (ix, iy) not in grid:
                        continue
                    if segment_hits_rect(
                        x1, y1, x2, y2,
                        ix * LON_UNIT + eps, iy * LAT_UNIT + eps,
                        (ix + 1) * LON_UNIT - eps, (iy + 1) * LAT_UNIT - eps,
                    ):
                        hit.add((ix, iy))
    # 2) 辺が通過しないメッシュは完全に内側か外側なので中心点で判定する
    xs = [x for ring in rings for x, _ in ring]
    ys = [y for ring in rings for _, y in ring]
    for ix in range(math.floor(min(xs) / LON_UNIT), math.floor(max(xs) / LON_UNIT) + 1):
        for iy in range(math.floor(min(ys) / LAT_UNIT), math.floor(max(ys) / LAT_UNIT) + 1):
            if (ix, iy) in hit or (ix, iy) not in grid:
                continue
            if point_in_rings((ix + 0.5) * LON_UNIT, (iy + 0.5) * LAT_UNIT, rings):
                hit.add((ix, iy))
    return {mesh_code(*grid[k]): grid[k] for k in hit}


def to_int(s):
    """欠損値 (*, 空欄など) は0として扱う。"""
    return int(s) if s.strip().isdigit() else 0


def load_population():
    with open(GIS / "population.csv", encoding="cp932", newline="") as f:
        rows = list(csv.reader(f))[2:]  # 先頭2行はタイトル行
    pop = {}
    for r in rows:
        total = to_int(r[4])
        # 階級ごとの [男, 女]。列は (総数, 男, 女) の繰り返しで7列目から始まる
        classes = [[to_int(r[7 + 3 * i + 1]), to_int(r[7 + 3 * i + 2])] for i in range(20)]
        pop[r[0]] = {"total": total, "classes": classes, "htksyori": r[1], "htksaki": r[2]}
    return pop


def main():
    rings = load_city_rings()
    meshes = extract_meshes(rings)
    pop = load_population()

    out_meshes = []
    dists = {}  # 年齢・性別の分布を持つメッシュ (秘匿メッシュの合算先を含む)
    secret = 0
    for code in sorted(meshes):
        p = pop.get(code)
        if not p or p["total"] == 0:
            continue
        lon, lat = meshes[code]
        entry = {"c": code, "x": round(lon, 7), "y": round(lat, 7), "n": p["total"]}
        src = code
        # 秘匿メッシュは年齢別人口が合算先に足し上げられているので、合算先の分布を使う
        seen = set()
        while sum(map(sum, pop[src]["classes"])) == 0 and pop[src]["htksaki"] and src not in seen:
            seen.add(src)
            src = pop[src]["htksaki"]
            if src not in pop:
                break
        if src != code:
            entry["d"] = src
            secret += 1
        if src in pop and sum(map(sum, pop[src]["classes"])) > 0:
            dists[src] = pop[src]["classes"]
        else:
            entry["d"] = None  # 分布不明 → アプリ側で市全体の分布を使う
        out_meshes.append(entry)

    data = {
        "city": CITY_NAME,
        "census": "令和2年国勢調査",
        "meshSize": [LON_UNIT, LAT_UNIT],
        "ageClasses": AGE_CLASSES,
        "meshes": out_meshes,
        "dists": dists,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    OUT.write_text(f"window.TSUCHIURA_DATA={body};\n", encoding="utf-8")

    total = sum(m["n"] for m in out_meshes)
    print(f"抽出メッシュ数: {len(meshes)} (人口あり {len(out_meshes)}, うち秘匿 {secret})")
    print(f"分布不明: {sum(1 for m in out_meshes if m.get('d', 0) is None)}")
    print(f"人口合計: {total:,}")
    print(f"出力: {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
