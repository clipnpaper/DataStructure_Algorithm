"""vis — 파이썬 코드로 그림(시각화)을 조종하는 작은 모듈.

사용법:
    import vis
    A = [5, 3, 8]
    vis.show(vis.array(A, hl={0: 'cmp'}), note="첫 칸을 비교")   # 한 장면(프레임) 추가

show()를 부를 때마다 장면이 하나씩 쌓이고, 실행이 끝나면 페이지가 그 장면들을 애니메이션으로 재생합니다.

색 이름: 'cmp'(비교·주황) 'swp'(교환·빨강) 'ok'(완료·초록) 'piv'(기준·보라) 'cur'(현재·파랑) 'dim'(흐리게)
"""
import json as _json
import sys as _sys
import builtins as _bi

_frames = []
MAX_FRAMES = 400
_src = []            # 사용자 코드 줄 (자동 설명용)
_fol = None          # follow 설정
CODE_FILE = '<code>'


def _s(v):
    if v is None:
        return ""
    if isinstance(v, float):
        if v == float('inf'):
            return "∞"
        if v == float('-inf'):
            return "-∞"
        return f"{v:g}"
    return str(v)


def _hl(hl):
    if not hl:
        return {}
    if isinstance(hl, dict):
        return {_s(k): str(c) for k, c in hl.items() if k is not None and c}
    return {_s(k): 'cmp' for k in hl if k is not None}


def reset():
    """지금까지 쌓인 장면과 follow 설정을 모두 지운다."""
    global _fol
    _frames.clear()
    _fol = None
    _sys.settrace(None)


def _code_line():
    f = _sys._getframe(1)
    while f is not None:
        if f.f_code.co_filename == CODE_FILE:
            return f.f_lineno
        f = f.f_back
    return 0


def show(*panels, note=""):
    """패널들을 모아 장면 하나를 추가한다."""
    if len(_frames) >= MAX_FRAMES:
        return
    _frames.append({"panels": [p for p in panels if p], "note": str(note), "line": _code_line()})


# ---------------------------------------------------------------- 자동 추적 (follow)
class _Scope(dict):
    """없는 이름은 None 으로 돌려주는 지역 이름공간."""
    def __init__(self, loc, glb):
        super().__init__(loc)
        self._g = glb

    def __missing__(self, k):
        if k in self._g:
            return self._g[k]
        if hasattr(_bi, k):
            return getattr(_bi, k)
        return None


_SIMPLE = (int, float, str, bool)


def _auto_vars(loc, want):
    out = {}
    for k, v in loc.items():
        if want is not True and k not in want:
            continue
        if k.startswith('_') or k == 'self':
            continue
        if isinstance(v, _SIMPLE) and not (isinstance(v, str) and len(v) > 24):
            out[k] = v
    if want is not True:
        out = {k: out[k] for k in want if k in out}
    return out


def follow(*exprs, note=None, vars=True, fn=None, every=False):
    """코드가 한 줄씩 실행될 때마다 exprs(문자열 식)를 계산해 그림이 바뀌면 장면으로 남긴다.
    예) vis.follow("vis.bars(A, hl={j: 'cmp', j + 1: 'cmp'})", fn="bubble_sort")
      - 식은 실행 중인 함수의 지역 변수로 계산된다. 아직 없는 변수는 None 이 된다.
      - vars=True 면 숫자/문자 지역 변수를 '변수' 카드로 함께 보여 준다. (리스트로 이름을 골라도 됨)
      - fn="함수이름" 을 주면 그 함수 안에서만 추적한다.
      - note="f'...'" 처럼 설명 식을 줄 수 있다. 없으면 방금 실행한 코드 줄이 설명이 된다."""
    global _fol
    _fol = {"exprs": [compile(e, '<follow>', 'eval') for e in exprs],
            "note": compile(note, '<note>', 'eval') if note else None,
            "vars": vars, "fn": fn, "every": every, "last": None, "prev": {}}
    _sys.settrace(_global_trace)


# ---------------------------------------------------------------- 무한 반복 방지
import time as _time
LIMIT_SEC = 12
_guard = {"t0": 0.0, "n": 0, "on": False}
_WATCH = ('<code>', '<viz>', '<테스트>')


class TooLong(Exception):
    pass


def _tick():
    _guard["n"] += 1
    if (_guard["n"] & 4095) == 0 and _time.perf_counter() - _guard["t0"] > LIMIT_SEC:
        _guard["on"] = False
        raise TooLong(f"{LIMIT_SEC}초 넘게 실행되어 멈췄습니다. 무한 반복(while 조건이 계속 참)이나 끝나지 않는 재귀가 없는지 확인하세요.")


def guard_start():
    _guard.update(t0=_time.perf_counter(), n=0, on=True)
    if _fol is None:
        _sys.settrace(_guard_global)


def guard_stop():
    _guard["on"] = False
    _sys.settrace(None)


def _guard_global(frame, event, arg):
    if not _guard["on"] or frame.f_code.co_filename not in _WATCH:
        return None
    return _guard_local


def _guard_local(frame, event, arg):
    if event == 'line' and _guard["on"]:
        _tick()
    return _guard_local


def _global_trace(frame, event, arg):
    if _guard["on"] and frame.f_code.co_filename in _WATCH and frame.f_code.co_filename != CODE_FILE:
        return _guard_local
    if _fol is None or frame.f_code.co_filename != CODE_FILE:
        return None
    if _fol["fn"] and frame.f_code.co_name not in (_fol["fn"] if isinstance(_fol["fn"], (list, tuple)) else (_fol["fn"],)):
        return None
    return _local_trace


def _local_trace(frame, event, arg):
    if _guard["on"] and event == 'line':
        _tick()
    if _fol is None:
        return None
    if event in ('line', 'return'):
        key = id(frame)
        prev = _fol["prev"].get(key)
        if prev is not None:
            _snap(frame, prev)
        _fol["prev"][key] = frame.f_lineno if event == 'line' else None
    return _local_trace


def _snap(frame, line):
    if len(_frames) >= MAX_FRAMES:
        return
    loc = frame.f_locals
    glb = dict(frame.f_globals)
    glb.update(loc)
    sc = _Scope(loc, glb)
    panels = []
    for e in _fol["exprs"]:
        try:
            p = eval(e, glb, sc)
        except Exception:
            return
        if isinstance(p, (list, tuple)):
            panels.extend(x for x in p if x)
        elif p:
            panels.append(p)
    if _fol["vars"]:
        vv = _auto_vars(loc, _fol["vars"])
        if vv:
            panels.append({"type": "vars", "name": "변수", "vars": {k: _s(v) for k, v in vv.items()}})
    sig = _json.dumps(panels, ensure_ascii=False, sort_keys=True)
    if sig == _fol["last"] and not _fol["every"]:
        return
    _fol["last"] = sig
    note = ''
    if _fol["note"] is not None:
        try:
            note = str(eval(_fol["note"], glb, sc))
        except Exception:
            note = ''
    if not note and 0 < line <= len(_src):
        note = f"{line}행 실행 → {_src[line - 1].strip()}"
    _frames.append({"panels": panels, "note": note, "line": line})
    if len(_frames) >= MAX_FRAMES:
        _frames[-1]["note"] += "  (장면이 너무 많아 여기서 멈춤)"


# ---------------------------------------------------------------- 패널들
def array(values, name="", hl=None, ptr=None, done=None, start=0):
    """칸이 나란한 배열. hl={인덱스: 색}, ptr={'low': 0, 'high': 5}, done=[정렬 완료 인덱스]"""
    return {"type": "array", "name": name, "values": [_s(v) for v in values], "hl": _hl(hl),
            "ptr": {str(k): int(v) for k, v in (ptr or {}).items() if v is not None},
            "done": [int(i) for i in (done or [])], "start": start}


def bars(values, name="", hl=None, done=None):
    """막대그래프 (정렬 시각화용)."""
    return {"type": "bars", "name": name, "values": [float(v) for v in values], "hl": _hl(hl),
            "done": [int(i) for i in (done or [])]}


def stack(values, name="스택", hl=None):
    """아래 → 위 순서의 리스트를 세로 스택으로."""
    return {"type": "stack", "name": name, "values": [_s(v) for v in values], "hl": _hl(hl)}


def queue(values, name="큐", hl=None):
    """앞(front) → 뒤(rear) 순서의 리스트를 가로 줄로."""
    return {"type": "queue", "name": name, "values": [_s(v) for v in values], "hl": _hl(hl)}


def cqueue(arr, front, rear, name="원형 큐"):
    """원형 큐 배열과 front, rear 인덱스."""
    return {"type": "cqueue", "name": name, "values": [_s(v) for v in arr], "front": int(front), "rear": int(rear)}


def _follow(node, circular=False, limit=40, text=None):
    out, seen = [], set()
    first = node
    while node is not None and len(out) < limit:
        if id(node) in seen:
            break
        seen.add(id(node))
        val = text(node) if text else _val(node)
        out.append((node, val))
        node = getattr(node, 'link', getattr(node, 'next', None))
        if circular and node is first:
            break
    return out


def linked(head, name="", hl=None, circular=False, doubly=False, labels=None, text=None):
    """연결 리스트: 노드의 .data 와 .link(또는 .next)를 따라가며 그린다.
    hl={위치: 색} (0부터), labels={위치: '글자'} (예: {0: 'head'}), circular=True 면 마지막이 처음으로 이어짐"""
    nodes = _follow(head, circular, text=text)
    return {"type": "linked", "name": name, "values": [_s(v) for _, v in nodes], "hl": _hl(hl),
            "circular": bool(circular), "doubly": bool(doubly),
            "labels": {str(k): str(v) for k, v in (labels or {}).items()}}


def _val(n):
    for a in ('data', 'key', 'value', 'freq', 'item', 'k'):
        v = getattr(n, a, None)
        if v is not None:
            return v
    return '?'


def _tree_conv(n, text=None, depth=0):
    if n is None or depth > 12:
        return None
    if isinstance(n, (tuple, list)):
        v, l, r = (list(n) + [None, None])[:3]
        return {"v": _s(v), "l": _tree_conv(l, text, depth + 1), "r": _tree_conv(r, text, depth + 1)}
    v = text(n) if text else _val(n)
    return {"v": _s(v), "l": _tree_conv(getattr(n, 'left', getattr(n, 'l', None)), text, depth + 1),
            "r": _tree_conv(getattr(n, 'right', getattr(n, 'r', None)), text, depth + 1)}


def tree(root, name="", hl=None, labels=None, text=None):
    """이진트리: 노드의 .data(또는 .key)와 .left, .right를 따라가며 그린다.
    (값, 왼쪽, 오른쪽) 튜플도 된다. hl={노드값: 색}, labels={노드값: '옆에 쓸 글자'}
    text=함수 를 주면 노드에 쓸 글자를 직접 정한다. 예: text=lambda n: f"{n.char}:{n.freq}" """
    return {"type": "tree", "name": name, "root": _tree_conv(root, text), "hl": _hl(hl),
            "labels": {_s(k): _s(v) for k, v in (labels or {}).items()}}


def heap(values, name="힙", hl=None, start=1):
    """배열로 저장된 완전 이진트리(힙). start=1이면 values[1]이 루트."""
    vals = list(values)[start:]
    def build(i):
        if i >= len(vals):
            return None
        return {"v": _s(vals[i]), "i": i + start, "l": build(2 * i + 1), "r": build(2 * i + 2)}
    return {"type": "tree", "name": name, "root": build(0), "hl": _hl(hl),
            "byIndex": True, "array": [_s(v) for v in vals], "start": start}


def graph(edges, name="", nodes=None, pos=None, hl=None, ehl=None, labels=None, directed=False, weighted=None):
    """그래프. edges = [(u, v)] 또는 [(u, v, 가중치)] 또는 {u: [이웃...]} 딕셔너리.
    hl={정점: 색}, ehl={(u, v): 색}, labels={정점: '거리 등'}, pos={정점: (x, y)} (0~1 비율)"""
    E = []
    if isinstance(edges, dict):
        seen = set()
        for u, vs in edges.items():
            for v in vs:
                if isinstance(v, (tuple, list)):
                    v, w = v[0], v[1]
                else:
                    w = None
                key = (u, v) if directed else tuple(sorted((str(u), str(v))))
                if key in seen:
                    continue
                seen.add(key)
                E.append([_s(u), _s(v), _s(w) if w is not None else ""])
        nodes = nodes or list(edges.keys())
    else:
        for e in edges:
            E.append([_s(e[0]), _s(e[1]), _s(e[2]) if len(e) > 2 else ""])
    if nodes is None:
        nodes = []
        for u, v, _ in E:
            for x in (u, v):
                if x not in nodes:
                    nodes.append(x)
    eh = {}
    for k, c in (ehl or {}).items():
        eh[_s(k[0]) + "|" + _s(k[1])] = c
        if not directed:
            eh[_s(k[1]) + "|" + _s(k[0])] = c
    return {"type": "graph", "name": name, "nodes": [_s(n) for n in nodes], "edges": E,
            "pos": {_s(k): [float(v[0]), float(v[1])] for k, v in (pos or {}).items()},
            "hl": _hl(hl), "ehl": eh, "labels": {_s(k): _s(v) for k, v in (labels or {}).items()},
            "directed": bool(directed)}


def grid(rows, name="", marks=None):
    """2차원 격자(미로 등). rows는 문자열 리스트나 2차원 리스트. marks={(r, c): 색 또는 '숫자'}"""
    cells = [[_s(x) for x in row] for row in rows]
    m = {}
    for (r, c), v in (marks or {}).items():
        m[f"{r},{c}"] = str(v)
    return {"type": "grid", "name": name, "cells": cells, "marks": m}


def hashtable(buckets, name="해시 테이블", hl=None):
    """버킷 리스트. 각 버킷은 값 하나(None 가능) 또는 리스트(체이닝)."""
    B = []
    for b in buckets:
        if b is None:
            B.append([])
        elif isinstance(b, (list, tuple)):
            B.append([_s(x) for x in b])
        else:
            B.append([_s(b)])
    return {"type": "hash", "name": name, "buckets": B, "hl": _hl(hl)}


def table(rows, header=None, name="", hl=None):
    """표. rows = [[...], ...], hl={행번호: 색}"""
    return {"type": "table", "name": name, "header": [_s(h) for h in (header or [])],
            "rows": [[_s(x) for x in r] for r in rows], "hl": _hl(hl)}


def vars(name="변수", **kw):
    """변수 이름과 값을 카드로 보여 준다. 예: vis.vars(i=3, total=10)"""
    return {"type": "vars", "name": name, "vars": {k: _s(v) for k, v in kw.items()}}


def text(msg, name=""):
    return {"type": "text", "name": name, "text": str(msg)}


def _dump():
    return _json.dumps(_frames, ensure_ascii=False)


# ---------------------------------------------------------------- 로컬 실행용 뷰어
# (원래 vis 모듈은 책 HTML 안의 Pyodide에서만 쓰도록 만들어졌고, 장면을 그리는 코드는
#  이 파일이 아니라 책 HTML 안의 자바스크립트에 있었다. VSCode 등 일반 파이썬에서도
#  똑같은 그림을 보려고, 그 자바스크립트/CSS를 그대로 옮겨 온 작은 HTML 플레이어를 아래에 담아
#  play()가 호출되면 띄운다.)
import os as _os
import html as _html
import tempfile as _tempfile
import webbrowser as _webbrowser

_VIEWER_HTML = r"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<title>__TITLE__</title>
<style>
:root{
  --bg:#f6f5f1; --card:#ffffff; --ink:#1f1f23; --muted:#66666e; --line:#e3e1db; --gray:#9a9a9a;
  --blue:#2f6fec; --blue-s:#e6eeff; --green:#16945f; --green-s:#e1f5ec;
  --orange:#dd7a12; --orange-s:#fdf0e1; --red:#d23f3a; --red-s:#fce8e7;
  --purple:#7050e0; --purple-s:#efeafe; --gray-s:#efeee9;
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:#16161a; --card:#1f1f25; --ink:#ececf0; --muted:#a0a0aa; --line:#33333b; --gray:#777;
    --blue:#6b9bff; --blue-s:#1f2a44; --green:#3ccb8c; --green-s:#173228;
    --orange:#f5a14a; --orange-s:#3a2a17; --red:#ff7a73; --red-s:#3d1f1e;
    --purple:#a58cff; --purple-s:#2a2342; --gray-s:#2a2a31;
  }
}
*{box-sizing:border-box}
body{margin:0;padding:24px;background:var(--bg);color:var(--ink);
  font-family:"Pretendard","Apple SD Gothic Neo","Malgun Gothic","Noto Sans KR",system-ui,sans-serif;
  font-size:16px}
h1{font-size:18px;margin:0 0 14px}
.vis{margin:0 0 18px;border:1.5px solid var(--blue);border-radius:14px;background:var(--card);overflow:hidden;max-width:980px}
.vis-h{display:flex;gap:8px;align-items:center;padding:8px 14px;background:var(--blue-s);font-size:13px;font-weight:800;color:var(--blue)}
.vis-h .vcount{margin-left:auto;color:var(--muted);font-weight:700}
.vis-stage{display:flex;flex-wrap:wrap;gap:14px 28px;align-items:flex-start;padding:16px 16px 6px;overflow-x:auto}
.vpanel{min-width:0;max-width:100%;overflow:visible}
.vpn{font-size:12.5px;font-weight:800;color:var(--muted);margin-bottom:6px}
.vis-note{padding:4px 16px 8px;font-weight:700;min-height:1.5em;font-size:15px;
  font-family:"D2Coding",ui-monospace,Consolas,"Malgun Gothic",monospace}
.vis-ctl{display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:8px 14px 12px;border-top:1px dashed var(--line)}
.vis-ctl button{font:inherit;font-size:13px;padding:4px 10px;border-radius:8px;border:1.5px solid var(--line);
  background:var(--card);color:var(--ink);cursor:pointer}
.vis-ctl button:hover{border-color:var(--blue);color:var(--blue)}
.vis-ctl button.pri{background:var(--blue);border-color:var(--blue);color:#fff}
.vis-ctl input[type=range]{flex:1;min-width:120px;accent-color:var(--blue)}
.vis-ctl select{font:inherit;font-size:13px;padding:3px 6px;border-radius:8px;border:1px solid var(--line);
  background:var(--card);color:var(--ink)}
.vempty{color:var(--muted);font-size:13.5px}
.h-cur{--c:var(--blue);--cs:var(--blue-s)}.h-cmp{--c:var(--orange);--cs:var(--orange-s)}.h-swp{--c:var(--red);--cs:var(--red-s)}
.h-ok{--c:var(--green);--cs:var(--green-s)}.h-piv{--c:var(--purple);--cs:var(--purple-s)}.h-dim{--c:var(--muted);--cs:transparent;opacity:.4}
.varr{display:flex;gap:4px;flex-wrap:nowrap;overflow-x:auto;padding-bottom:4px;padding-top:5px}
.varr.hasptr{padding-bottom:22px}
.vc{position:relative;min-width:42px;height:42px;border:2px solid var(--line);border-radius:9px;background:var(--gray-s);
  display:grid;place-items:center;flex:none;transition:background .2s,border-color .2s,transform .2s;padding:0 6px;box-sizing:border-box}
.vc[class*=" h-"]{background:var(--cs);border-color:var(--c);color:var(--c)}
.vc i{position:absolute;top:calc(100% + 2px);left:50%;transform:translateX(-50%);font-size:10.5px;color:var(--muted);font-style:normal}
.vc u{position:absolute;top:calc(100% + 16px);left:50%;transform:translateX(-50%);text-decoration:none;font-size:11.5px;font-weight:800;color:var(--blue);white-space:nowrap}
.varr .vc{margin-bottom:16px}
.vbars{display:flex;align-items:flex-end;gap:3px;height:170px;min-width:260px;padding-top:18px}
.vb{flex:1;min-width:12px;max-width:44px;background:color-mix(in srgb,var(--muted) 45%,transparent);
  border-radius:5px 5px 0 0;position:relative;transition:height .25s ease,background .2s}
.vb[class*=" h-"]{background:var(--c)}
.vb span{position:absolute;bottom:calc(100% + 4px);left:50%;transform:translateX(-50%);font-size:11px;font-weight:700;white-space:nowrap}
.vstk{display:flex;flex-direction:column;gap:4px;align-items:flex-start;min-width:120px;padding-top:4px}
.vstk .vc{min-width:80px}
.vstk .vc u{top:50%;left:calc(100% + 8px);transform:translateY(-50%)}
.vfloor{height:4px;width:100%;background:var(--line);border-radius:3px;margin-top:4px}
.vq{display:flex;align-items:center;gap:4px;padding:4px 0 20px;flex-wrap:nowrap;overflow-x:auto;padding-top:5px}
.vq .vend{font-size:12px;color:var(--muted);font-weight:700;white-space:nowrap}
.vsvg{display:block}
.vscroll{overflow-x:auto;max-width:100%}
.vsvg .vn circle,.vsvg .vn rect{fill:var(--gray-s);stroke:var(--line);stroke-width:2}
.vsvg .vn[class*=" h-"] circle,.vsvg .vn[class*=" h-"] rect{fill:var(--cs);stroke:var(--c)}
.vsvg .vn text{fill:var(--ink);font-size:13px;text-anchor:middle;font-weight:700}
.vsvg .vidx{font-size:11px;fill:var(--muted);font-weight:600}
.vsvg .vlab{font-size:12px;font-weight:800;fill:var(--blue)}
.vsvg .vnone{font-size:13px;fill:var(--muted)}
.vsvg .vsep{stroke:var(--muted);stroke-width:1.5}
.vsvg .varrow{stroke:var(--ink);stroke-width:2;fill:none}
.vsvg .varrow.back,.vsvg .varrow.circ{stroke:var(--blue)}
.vsvg .vedge{stroke:var(--muted);stroke-width:2;fill:none}
.vsvg .vedge[class*=" e-"]{stroke-width:4}
.vsvg .e-cur{stroke:var(--blue)}.vsvg .e-cmp{stroke:var(--orange)}.vsvg .e-swp{stroke:var(--red)}.vsvg .e-ok{stroke:var(--green)}.vsvg .e-piv{stroke:var(--purple)}.vsvg .e-dim{stroke:var(--line)}
.vsvg .vw rect{fill:var(--card);stroke:var(--line)}.vsvg .vw text{font-size:11px;text-anchor:middle;fill:var(--ink)}
.vsvg .vw.e-ok text{fill:var(--green)}.vsvg .vw.e-cmp text{fill:var(--orange)}.vsvg .vw.e-cur text{fill:var(--blue)}.vsvg .vw.e-swp text{fill:var(--red)}
.vsvg .vpill rect{fill:var(--blue)}.vsvg .vpill text{fill:#fff;font-size:12px}
.vsvg .vring{fill:none;stroke:var(--line);stroke-width:12}
.vgrid{display:grid;gap:2px}
.vg{min-width:18px;min-height:18px;display:grid;place-items:center;background:var(--gray-s);border-radius:3px;font-size:12px}
.vg.wall{background:var(--ink)}
.vg[class*=" h-"]{background:var(--cs);color:var(--c);font-weight:800}
.vg.h-num{background:var(--blue-s);color:var(--blue)}
.vhash{display:flex;flex-direction:column;gap:3px;min-width:200px}
.vhr{display:flex;align-items:center;gap:5px;padding:2px 6px;border-radius:8px}
.vhr[class*=" h-"]{background:var(--cs)}
.vhr .ix{width:26px;text-align:right;font-size:12px;color:var(--muted);font-weight:700;margin-right:4px}
.vhr .it{border:1.5px solid var(--line);background:var(--gray-s);border-radius:7px;padding:2px 9px;font-weight:700;font-size:14px}
.vhr[class*=" h-"] .it:last-child{border-color:var(--c);color:var(--c)}
.vhr .ar{color:var(--muted);font-size:12px}.vhr .nil{color:var(--line);font-weight:800}
.vtab{border-collapse:collapse;font-size:13.5px}
.vtab th,.vtab td{border:1px solid var(--line);padding:4px 10px;text-align:center}
.vtab th{background:var(--gray-s)}
.vtab tr[class*="h-"] td{background:var(--cs);color:var(--c);font-weight:800}
.vvars{display:flex;flex-wrap:wrap;gap:6px}
.vvars span{display:inline-flex;border:1.5px solid var(--line);border-radius:9px;overflow:hidden;font-size:14px}
.vvars i{font-style:normal;background:var(--gray-s);padding:3px 8px;color:var(--muted);font-weight:700}
.vvars b{padding:3px 10px;font-family:"D2Coding",ui-monospace,Consolas,monospace}
.vtext{font-size:14.5px;white-space:pre-wrap}
</style></head>
<body>
<h1>__TITLE__</h1>
<svg width="0" height="0" style="position:absolute">
  <defs>
    <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" style="fill:var(--ink)"/></marker>
    <marker id="arrb" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" style="fill:var(--blue)"/></marker>
    <marker id="arrr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" style="fill:var(--red)"/></marker>
    <marker id="arrg" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" style="fill:var(--green)"/></marker>
  </defs>
</svg>
<div class="vis" id="box">
  <div class="vis-h"><span>🎬 코드가 움직이는 모습</span><span class="vcount"></span></div>
  <div class="vis-stage"></div><div class="vis-note"></div>
  <div class="vis-ctl"><button data-a="first" title="처음">⏮</button><button data-a="prev">◀ 이전</button><button data-a="play" class="pri">▶ 재생</button><button data-a="next">다음 ▶</button><button data-a="last" title="끝">⏭</button>
  <input type="range" min="0" value="0" aria-label="장면 이동"><select aria-label="속도"><option value="1500">0.5배</option><option value="800" selected>보통</option><option value="400">2배</option><option value="150">5배</option></select></div>
</div>
<script>
const VK = ['cmp', 'swp', 'ok', 'piv', 'cur', 'dim'];
const hcls = c => c ? (VK.includes(c) ? ' h-' + c : ' h-cur') : '';
function escH(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
function vArray(p) {
  const ptr = {}; Object.entries(p.ptr || {}).forEach(([k, i]) => (ptr[i] = ptr[i] || []).push(k));
  const done = new Set(p.done || []);
  const cells = p.values.map((v, i) => `<div class="vc${hcls(p.hl[i]) || (done.has(i) ? ' h-ok' : '')}"><b>${escH(v)}</b><i>${i + (p.start || 0)}</i>${ptr[i] ? `<u>${ptr[i].map(escH).join(' · ')}</u>` : ''}</div>`).join('');
  return `<div class="varr${Object.keys(ptr).length ? ' hasptr' : ''}">${cells || '<span class="vempty">(비어 있음)</span>'}</div>`;
}
function vBars(p) {
  const mx = Math.max(1, ...p.values.map(Math.abs)); const done = new Set(p.done || []);
  return `<div class="vbars">${p.values.map((v, i) => `<div class="vb${hcls(p.hl[i]) || (done.has(i) ? ' h-ok' : '')}" style="height:${(Math.abs(v) / mx * 100).toFixed(1)}%"><span>${escH(+v.toFixed(2))}</span></div>`).join('')}</div>`;
}
function vStack(p) {
  const n = p.values.length;
  return `<div class="vstk">${p.values.map((v, i) => `<div class="vc${hcls(p.hl[i])}${i === n - 1 ? ' top' : ''}"><b>${escH(v)}</b>${i === n - 1 ? '<u>← top</u>' : ''}</div>`).reverse().join('') || '<span class="vempty">(빈 스택)</span>'}<div class="vfloor"></div></div>`;
}
function vQueue(p) {
  const n = p.values.length;
  return `<div class="vq"><span class="vend">front →</span>${p.values.map((v, i) => `<div class="vc${hcls(p.hl[i])}"><b>${escH(v)}</b>${i === 0 ? '<u>front</u>' : ''}${i === n - 1 && n > 1 ? '<u>rear</u>' : ''}</div>`).join('') || '<span class="vempty">(빈 큐)</span>'}<span class="vend">← rear</span></div>`;
}
function vCQueue(p) {
  const N = p.values.length, R = 78, cx = 120, cy = 110; let s = `<svg viewBox="0 0 240 220" class="vsvg" style="width:240px;max-width:100%"><circle cx="${cx}" cy="${cy}" r="${R}" class="vring"/>`;
  p.values.forEach((v, i) => {
    const a = -Math.PI / 2 + i * 2 * Math.PI / N, x = cx + R * Math.cos(a), y = cy + R * Math.sin(a);
    const c = i === p.front && i === p.rear ? 'cmp' : i === p.front ? 'cur' : i === p.rear ? 'cmp' : '';
    s += `<g class="vn${c ? ' h-' + c : ''}"><circle cx="${x}" cy="${y}" r="19"/><text x="${x}" y="${y + 5}">${escH(v)}</text></g>`;
    const lx = cx + (R - 34) * Math.cos(a), ly = cy + (R - 34) * Math.sin(a);
    s += `<text x="${lx}" y="${ly + 4}" class="vidx">${i}</text>`;
  });
  s += `<text x="${cx}" y="${cy - 4}" class="vlab" fill="var(--blue)">front=${p.front}</text><text x="${cx}" y="${cy + 14}" class="vlab" fill="var(--orange)">rear=${p.rear}</text></svg>`;
  return s;
}
function vLinked(p) {
  const n = p.values.length, W = 104, x0 = 16, y = 44, H = 36;
  const w = Math.max(200, x0 + n * W + 70), h = p.circular || p.doubly ? 120 : 96;
  let s = `<svg viewBox="0 0 ${w} ${h}" class="vsvg" style="width:${w}px;max-width:none">`;
  p.values.forEach((v, i) => {
    const x = x0 + i * W, c = p.hl[i];
    s += `<g class="vn${hcls(c)}"><rect x="${x}" y="${y}" width="${p.doubly ? 68 : 60}" height="${H}" rx="7"/>`;
    if (p.doubly) s += `<line x1="${x + 14}" y1="${y}" x2="${x + 14}" y2="${y + H}" class="vsep"/>`;
    s += `<line x1="${x + (p.doubly ? 54 : 42)}" y1="${y}" x2="${x + (p.doubly ? 54 : 42)}" y2="${y + H}" class="vsep"/><text x="${x + (p.doubly ? 34 : 21)}" y="${y + 23}">${escH(v)}</text></g>`;
    const lab = p.labels[i] !== undefined ? p.labels[i] : (i === 0 ? 'head' : '');
    if (lab) s += `<text x="${x + 30}" y="${y - 12}" class="vlab">${escH(lab)} ↓</text>`;
    if (i < n - 1) {
      s += `<line x1="${x + (p.doubly ? 61 : 51)}" y1="${y + (p.doubly ? 12 : 18)}" x2="${x + W - 3}" y2="${y + (p.doubly ? 12 : 18)}" class="varrow" marker-end="url(#arr)"/>`;
      if (p.doubly) s += `<line x1="${x + W + 7}" y1="${y + 26}" x2="${x + 64}" y2="${y + 26}" class="varrow back" marker-end="url(#arrb)"/>`;
    }
  });
  if (n && !p.circular) { const x = x0 + (n - 1) * W + (p.doubly ? 61 : 51); s += `<line x1="${x}" y1="${y + 18}" x2="${x + 26}" y2="${y + 18}" class="varrow"/><text x="${x + 30}" y="${y + 23}" class="vnone">None</text>`; }
  if (n && p.circular) { const xl = x0 + (n - 1) * W + 51, xf = x0 + 30; s += `<path d="M${xl} ${y + 18} H${xl + 22} V${y + H + 26} H${xf} V${y + H + 4}" class="varrow circ" marker-end="url(#arrb)"/>`; }
  if (!n) s += `<text x="20" y="${y + 23}" class="vnone" text-anchor="start">head → None (빈 리스트)</text>`;
  return `<div class="vscroll">${s}</svg></div>`;
}
function vTree(p) {
  if (!p.root) return '<span class="vempty">(빈 트리)</span>';
  let k = 0, depth = 0; const nodes = [];
  (function walk(n, d, par) { if (!n) return; const me = { n, d, par }; walk(n.l, d + 1, me); me.x = k++; nodes.push(me); depth = Math.max(depth, d); walk(n.r, d + 1, me); })(p.root, 0, null);
  const maxLab = Math.max(0, ...Object.values(p.labels || {}).map(x => String(x).length)), maxV = Math.max(1, ...nodes.map(m => String(m.n.v).length));
  const DX = Math.max(46, maxV * 9 + 14), DY = 62, w = Math.max(120, k * DX + 30 + (maxLab ? maxLab * 7 + 16 : 0)), h = (depth + 1) * DY + (p.byIndex ? 16 : 10);
  let s = `<svg viewBox="0 0 ${w} ${h}" class="vsvg" style="width:${w}px;max-width:none">`;
  const X = m => 15 + m.x * DX + DX / 2, Y = m => 28 + m.d * DY;
  nodes.forEach(m => { if (m.par) s += `<line x1="${X(m.par)}" y1="${Y(m.par)}" x2="${X(m)}" y2="${Y(m)}" class="vedge"/>`; });
  nodes.forEach(m => {
    const key = p.byIndex ? String(m.n.i) : m.n.v, c = p.hl[key];
    const tl = String(m.n.v).length; s += tl > 3 ? `<g class="vn${hcls(c)}"><rect x="${X(m) - tl * 4.6 - 8}" y="${Y(m) - 16}" width="${tl * 9.2 + 16}" height="32" rx="12"/><text x="${X(m)}" y="${Y(m) + 5}" style="font-size:13px">${escH(m.n.v)}</text></g>` : `<g class="vn${hcls(c)}"><circle cx="${X(m)}" cy="${Y(m)}" r="19"/><text x="${X(m)}" y="${Y(m) + 5}">${escH(m.n.v)}</text></g>`;
    if (p.byIndex) s += `<text x="${X(m)}" y="${Y(m) + 33}" class="vidx">[${m.n.i}]</text>`;
    const lab = p.labels && p.labels[m.n.v]; if (lab) s += `<text x="${X(m) + 23}" y="${Y(m) - 14}" class="vlab" text-anchor="start">${escH(lab)}</text>`;
  });
  s += '</svg>';
  let arr = '';
  if (p.byIndex) arr = vArray({ values: p.array, hl: Object.fromEntries(Object.entries(p.hl).map(([i, c]) => [i - p.start, c])), start: p.start, ptr: {}, done: [] });
  return `<div class="vscroll">${s}</div>${arr}`;
}
function vGraph(p) {
  const W = 480, H = 300, M = 34, N = p.nodes.length, P = {};
  p.nodes.forEach((v, i) => {
    const q = p.pos[v];
    if (q) P[v] = [M + q[0] * (W - 2 * M), M + q[1] * (H - 2 * M)];
    else { const a = -Math.PI / 2 + i * 2 * Math.PI / Math.max(1, N); P[v] = [W / 2 + (W / 2 - M) * Math.cos(a), H / 2 + (H / 2 - M) * Math.sin(a)]; }
  });
  const RAD = {}; p.nodes.forEach(v => { const L = String(v).length * (/[ㄱ-힣]/.test(v) ? 15 : 9); RAD[v] = L > 26 ? [L / 2 + 8, 16] : [18, 18]; });
  const rr = (v, ux, uy) => { const [a, b] = RAD[v] || [18, 18]; return Math.min(a / Math.max(Math.abs(ux), 1e-6), b / Math.max(Math.abs(uy), 1e-6)); };
  let x0 = 0, y0 = 0, x1 = W, y1 = H;
  p.nodes.forEach(v => { const [a] = RAD[v]; const [x, y] = P[v]; x0 = Math.min(x0, x - a - 6); x1 = Math.max(x1, x + a + 6 + (p.labels[v] ? String(p.labels[v]).length * 8 + 26 : 0)); y0 = Math.min(y0, y - 38); y1 = Math.max(y1, y + 24); });
  let s = `<svg viewBox="${x0} ${y0} ${x1 - x0} ${y1 - y0}" class="vsvg" style="width:${x1 - x0}px;max-width:100%">`;
  p.edges.forEach(([u, v, w]) => {
    if (!P[u] || !P[v]) return;
    const [x1, y1] = P[u], [x2, y2] = P[v], d = Math.hypot(x2 - x1, y2 - y1) || 1, ux = (x2 - x1) / d, uy = (y2 - y1) / d;
    const c = p.ehl[u + '|' + v] || (p.directed ? '' : p.ehl[v + '|' + u]);
    const r1 = rr(u, ux, uy), r2 = rr(v, ux, uy) + (p.directed ? 6 : 0);
    s += `<line x1="${x1 + ux * r1}" y1="${y1 + uy * r1}" x2="${x2 - ux * r2}" y2="${y2 - uy * r2}" class="vedge${c ? ' e-' + c : ''}"${p.directed ? ` marker-end="url(#${c === 'ok' ? 'arrg' : c === 'swp' ? 'arrr' : c ? 'arrb' : 'arr'})"` : ''}/>`;
    if (w !== '') { const mx = (x1 + x2) / 2 - uy * 11, my = (y1 + y2) / 2 + ux * 11; s += `<g class="vw${c ? ' e-' + c : ''}"><rect x="${mx - 13}" y="${my - 10}" width="26" height="19" rx="5"/><text x="${mx}" y="${my + 4}">${escH(w)}</text></g>`; }
  });
  p.nodes.forEach(v => {
    const [x, y] = P[v], c = p.hl[v];
    const kor = /[ㄱ-힣]/.test(v), L = String(v).length * (kor ? 15 : 9); s += L > 26 ? `<g class="vn${hcls(c)}"><rect x="${x - L / 2 - 8}" y="${y - 16}" width="${L + 16}" height="32" rx="14"/><text x="${x}" y="${y + 5}" style="font-size:14px">${escH(v)}</text></g>` : `<g class="vn${hcls(c)}"><circle cx="${x}" cy="${y}" r="18"/><text x="${x}" y="${y + 5}">${escH(v)}</text></g>`;
    const lab = p.labels[v]; if (lab !== undefined && lab !== '') s += `<g class="vpill"><rect x="${x + 12}" y="${y - 34}" width="${Math.max(22, String(lab).length * 8 + 10)}" height="18" rx="9"/><text x="${x + 12 + Math.max(22, String(lab).length * 8 + 10) / 2}" y="${y - 21}">${escH(lab)}</text></g>`;
  });
  return s + '</svg>';
}
function vGrid(p) {
  const C = Math.max(...p.cells.map(r => r.length), 1);
  let s = `<div class="vgrid" style="grid-template-columns:repeat(${C},minmax(18px,30px))">`;
  p.cells.forEach((row, r) => row.forEach((v, c) => {
    const mk = p.marks[r + ',' + c]; let cls = v === '#' ? ' wall' : '', t = v === '#' || v === '.' || v === '0' ? '' : v;
    if (mk !== undefined) { if (VK.includes(mk)) cls += ' h-' + mk; else { cls += ' h-num'; t = mk; } }
    s += `<div class="vg${cls}">${escH(t)}</div>`;
  }));
  return s + '</div>';
}
function vHash(p) {
  return `<div class="vhash">${p.buckets.map((b, i) => `<div class="vhr${hcls(p.hl[i])}"><span class="ix">${i}</span>${b.length ? b.map((x, j) => `${j ? '<span class="ar">→</span>' : ''}<span class="it">${escH(x)}</span>`).join('') : '<span class="nil">·</span>'}</div>`).join('')}</div>`;
}
function vTable(p) {
  return `<div class="vscroll"><table class="vtab">${p.header.length ? '<tr>' + p.header.map(h => `<th>${escH(h)}</th>`).join('') + '</tr>' : ''}${p.rows.map((r, i) => `<tr class="${p.hl[i] ? 'h-' + p.hl[i] : ''}">${r.map(x => `<td>${escH(x)}</td>`).join('')}</tr>`).join('')}</table></div>`;
}
function vVars(p) { return `<div class="vvars">${Object.entries(p.vars).map(([k, v]) => `<span><i>${escH(k)}</i><b>${escH(v)}</b></span>`).join('')}</div>`; }
const VR = { array: vArray, bars: vBars, stack: vStack, queue: vQueue, cqueue: vCQueue, linked: vLinked, tree: vTree, graph: vGraph, grid: vGrid, hash: vHash, table: vTable, vars: vVars, text: p => `<div class="vtext">${escH(p.text)}</div>` };
function vPanel(p) {
  let body; try { body = (VR[p.type] || (() => '?'))(p); } catch (e) { body = '<span class="vempty">그리기 오류: ' + escH(e) + '</span>'; }
  return `${p.name ? `<div class="vpn">${escH(p.name)}</div>` : ''}${body}`;
}
function visRender(stage, frame) {
  const ps = frame.panels || [];
  while (stage.children.length > ps.length) stage.lastChild.remove();
  ps.forEach((p, i) => {
    let box = stage.children[i];
    if (!box) { box = document.createElement('div'); box.className = 'vpanel'; stage.appendChild(box); }
    box.innerHTML = vPanel(p);
  });
}
function visPlayer(box, frames, autoplay) {
  const pl = { i: 0, frames, timer: null, stage: box.querySelector('.vis-stage'), note: box.querySelector('.vis-note'),
    cnt: box.querySelector('.vcount'), rng: box.querySelector('input'), sp: box.querySelector('select'), play: box.querySelector('[data-a=play]') };
  pl.show = i => { pl.i = Math.max(0, Math.min(pl.frames.length - 1, i)); const f = pl.frames[pl.i]; visRender(pl.stage, f); pl.note.innerHTML = f.note ? escH(f.note) : '&nbsp;'; pl.cnt.textContent = `${pl.i + 1} / ${pl.frames.length}`; pl.rng.value = pl.i; };
  pl.stop = () => { clearTimeout(pl.timer); pl.timer = null; pl.play.textContent = '▶ 재생'; };
  pl.go = () => { if (pl.timer) return pl.stop(); if (pl.i >= pl.frames.length - 1) pl.show(0); pl.play.textContent = '⏸ 멈춤'; const tick = () => { if (pl.i >= pl.frames.length - 1) return pl.stop(); pl.show(pl.i + 1); pl.timer = setTimeout(tick, +pl.sp.value); }; pl.timer = setTimeout(tick, +pl.sp.value); };
  box.querySelector('.vis-ctl').addEventListener('click', e => { const a = e.target.dataset && e.target.dataset.a; if (!a) return; if (a !== 'play') pl.stop(); ({ first: () => pl.show(0), prev: () => pl.show(pl.i - 1), next: () => pl.show(pl.i + 1), last: () => pl.show(pl.frames.length - 1), play: pl.go })[a](); });
  pl.rng.max = frames.length - 1;
  pl.rng.addEventListener('input', () => { pl.stop(); pl.show(+pl.rng.value); });
  pl.show(0);
  if (autoplay && frames.length > 1) pl.go();
}
const FRAMES = __FRAMES__;
if (!FRAMES.length) {
  document.getElementById('box').innerHTML = '<div style="padding:16px;color:var(--muted)">vis.show()로 남긴 장면이 없습니다.</div>';
} else {
  visPlayer(document.getElementById('box'), FRAMES, __AUTOPLAY__);
}
</script>
</body></html>
"""


def _build_doc(title, autoplay):
    data = _json.dumps(_frames, ensure_ascii=False).replace("</", "<\\/")
    return (_VIEWER_HTML
            .replace("__TITLE__", _html.escape(str(title)))
            .replace("__FRAMES__", data)
            .replace("__AUTOPLAY__", "true" if autoplay else "false"))


class _Inline:
    def __init__(self, doc, height):
        self._doc, self._h = doc, height

    def _repr_html_(self):
        return (f'<iframe srcdoc="{_html.escape(self._doc, quote=True)}" '
                f'style="width:100%;height:{self._h}px;border:0"></iframe>')


def inline(title="vis 결과", height=380, autoplay=False, clear=True):
    """주피터 노트북 셀의 마지막 줄에 vis.inline() 을 쓰면 장면 플레이어가 셀 출력으로 바로 나온다.
    clear=True 면 보여 준 뒤 장면을 비워서, 다음 셀은 새 장면부터 시작한다."""
    doc = _build_doc(title, autoplay)
    if clear:
        _frames.clear()
    return _Inline(doc, height)


def play(title="vis 결과", autoplay=True, open_browser=True, out=None):
    """지금까지 show()/follow()로 쌓은 장면들을 브라우저 창에 애니메이션으로 띄운다.
    책 HTML 안에서 보던 것과 같은 그림을, 일반 파이썬 실행 환경(VSCode 등)에서도 보기 위한 것.
    out에 경로(str)를 주면 임시파일 대신 그 자리에 결과 HTML을 저장한다."""
    doc = _build_doc(title, autoplay)
    if out:
        path = _os.path.abspath(out)
    else:
        fd, path = _tempfile.mkstemp(suffix=".html", prefix="vis_")
        _os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
    if open_browser:
        _webbrowser.open("file://" + path)
    return path
