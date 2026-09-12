"""Lightweight presentation helpers. All dashboard values are illustrative."""

from html import escape

import streamlit as st


def apply_styles():
    st.markdown(STYLES, unsafe_allow_html=True)


def heading(title, subtitle, label):
    st.markdown(f'<div class="page-heading"><div><h2>{escape(title)}</h2>'
                f'<p>{escape(subtitle)}</p></div><span class="sample-pill">{escape(label)}</span></div>',
                unsafe_allow_html=True)


def metrics(items):
    st.markdown('<div class="metric-grid">' + "".join(
        f'<div class="metric-card"><div class="metric-label">{escape(label)}</div>'
        f'<strong>{escape(value)}</strong><small>{escape(note)}</small></div>'
        for label, value, note in items) + '</div>', unsafe_allow_html=True)


def panel(title, subtitle, content):
    st.markdown(f'<section class="panel"><h3>{escape(title)}</h3><p class="panel-subtitle">'
                f'{escape(subtitle)}</p>{content}</section>', unsafe_allow_html=True)


def bars(items, unit="", maximum=100):
    return '<div class="bar-list">' + "".join(
        f'<div class="bar-item"><div><span>{escape(label)}</span><strong>{value}{unit}</strong></div>'
        f'<div class="bar-track"><i style="width:{min(100, max(0, value / maximum * 100))}%"></i></div></div>'
        for label, value in items) + '</div>'


STYLES = """
<style>
:root { --red:#FF3040; --text:#F7F7F8; --muted:#A1A1AA; --border:rgba(255,255,255,.08); }
.stApp { background:#070708; color:var(--text); color-scheme:dark; }
[data-testid="stHeader"] { background:transparent; }
[data-testid="stToolbar"] [data-testid="stBaseButton-header"],
[data-testid="stMainMenuButton"] { display:none; }
.block-container { max-width:1180px; padding:2rem 2.8rem 1.5rem; }
[data-testid="stMainBlockContainer"] { animation:arrive 420ms ease-out both; }
h1,h2,h3,p { overflow-wrap:break-word; }
h1,h2,h3 { color:var(--text); letter-spacing:-.035em; }
.eyebrow { font-size:.66rem; letter-spacing:.17em; color:var(--muted); font-weight:700; }
.muted { color:var(--muted); font-weight:400; }
[data-testid="stCaptionContainer"] { color:var(--muted); font-size:.75rem; }
[data-testid="stSidebar"] { background:#0D0D10; border-right:1px solid var(--border); min-width:240px; }
[data-testid="stSidebarUserContent"] { padding:1.5rem 1.3rem; }
.brand { margin:0 0 2.2rem; }
.brand-mark { font-size:2.45rem; line-height:1.1; font-weight:850; letter-spacing:-.09em; margin-bottom:1rem; }
.brand-mark span { color:var(--red); }
.brand strong { font-size:1.02rem; letter-spacing:-.02em; }
.brand p { font-size:.72rem; color:var(--muted); margin-top:.4rem; }
.nav-label { margin-bottom:.6rem; }
[data-testid="stSidebar"] [data-testid="stButton"] button {
    position:relative; justify-content:flex-start; padding:.8rem 1rem; border:1px solid transparent;
    border-radius:9px; color:var(--muted); background:transparent; font-weight:550;
    transition:background 200ms,color 200ms,border-color 200ms; }
[data-testid="stSidebar"] [data-testid="stButton"] button:hover { background:#17171C; color:var(--text); }
[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"] {
    color:var(--text); background:rgba(139,16,26,.2); border-color:rgba(255,48,64,.16); }
[data-testid="stSidebar"] button[kind="primary"]::before {
    content:""; position:absolute; left:0; top:24%; height:52%; width:3px; border-radius:3px;
    background:var(--red); animation:indicator 380ms ease-out; }
.sidebar-note { margin-top:3.5rem; border:1px solid var(--border); border-radius:12px;
    padding:1rem; font-size:.62rem; letter-spacing:.09em; color:#D4D4D8; }
.sidebar-note p { margin:.7rem 0 0; font-size:.75rem; letter-spacing:0; line-height:1.7; color:var(--muted); }
.live-dot { display:inline-block; width:6px; height:6px; background:var(--red); border-radius:50%; margin-right:6px; }
.sidebar-footer { margin-top:2rem; font-size:.59rem; letter-spacing:.12em; color:var(--muted); line-height:2; }
.sidebar-footer span { letter-spacing:0; }
.hero { position:relative; padding:0 0 1.7rem; margin-bottom:.8rem; border-bottom:1px solid var(--border);
    background:radial-gradient(ellipse at 90% 0%,rgba(139,16,26,.13),transparent 55%); }
.hero::after { content:""; position:absolute; bottom:-1px; left:0; width:64px; height:2px; background:var(--red); }
.hero .eyebrow { color:#D4D4D8; }
.hero h1 { margin:.7rem 0 .6rem; padding:0; font-size:clamp(1.65rem,2.6vw,2.35rem); font-weight:700; line-height:1.18; }
.hero h1 span { color:var(--muted); font-weight:450; }
.hero p { font-size:.8rem; color:var(--muted); margin:0; }
.exam-top,.page-heading { display:flex; align-items:center; justify-content:space-between; gap:1rem; }
.exam-top h2 { font-size:1.35rem; padding:.3rem 0 0; margin:0; font-weight:500; }
.exam-top h2 b { font-weight:650; }
.difficulty { color:#D4D4D8; font-size:.78rem; white-space:nowrap; }
.difficulty i { display:inline-block; width:6px; height:6px; border-radius:50%; background:var(--red); margin-right:6px; }
[data-testid="stProgress"] p { font-size:.68rem; color:var(--muted); }
[data-testid="stProgressBarTrack"] { height:4px; background:#242429; }
[data-testid="stProgressBarTrack"] > div {
    background:linear-gradient(100deg,#8B101A,#FF3040,#FF4655,#FF3040); background-size:200% 100%;
    animation:shimmer 5s ease-in-out infinite; }
.st-key-question_card { background:#121216; border:1px solid var(--border); border-radius:16px; padding:1.5rem !important; }
.st-key-question_card > div { border:none !important; }
.badges { display:flex; flex-wrap:wrap; gap:.45rem; }
.badges span,.tag { border:1px solid var(--border); background:#17171C; color:#C5C5CC; border-radius:5px;
    padding:.3rem .55rem; font-size:.59rem; font-weight:600; letter-spacing:.06em; }
.badges span:first-child { color:#FF8791; border-color:rgba(255,48,64,.2); background:rgba(139,16,26,.12); }
.question-text { font-size:clamp(1.15rem,1.9vw,1.6rem); line-height:1.45; padding:1.1rem 0 .5rem; max-width:800px; }
.question-hint { margin:0; color:var(--muted); font-size:.78rem; }
[data-testid="stMain"] [data-testid="stElementContainer"]:has(> [data-testid="stRadio"]),
[data-testid="stMain"] [data-testid="stRadio"],
[data-testid="stMain"] [data-testid="stRadioGroup"] { width:100%; }
[data-testid="stMain"] [data-testid="stRadio"] [role="radiogroup"] { gap:.55rem; }
[data-testid="stMain"] [data-testid="stRadio"] label[data-testid="stRadioOption"] {
    width:100%; box-sizing:border-box; margin:0; padding:.8rem 1rem; min-height:60px; border-radius:10px;
    background:#17171C; border:1px solid var(--border); cursor:pointer;
    transition:transform 200ms,border-color 200ms,background 200ms,box-shadow 200ms; }
/* Keep real radio inputs and keyboard semantics; hide only the painted circle. */
[data-testid="stMain"] label[data-testid="stRadioOption"] > div > div > div:first-child { display:none; }
[data-testid="stMain"] label[data-testid="stRadioOption"] > div:last-child { margin-left:0; width:100%; }
[data-testid="stMain"] label[data-testid="stRadioOption"] p { display:flex; align-items:center; gap:1rem; margin:0; }
[data-testid="stMain"] label[data-testid="stRadioOption"] strong { display:inline-flex; align-items:center; justify-content:center;
    width:30px; height:30px; background:#232329; border:1px solid var(--border); border-radius:6px; font-size:.78rem; color:#BEBEC7; }
[data-testid="stMain"] label[data-testid="stRadioOption"] code { background:none; padding:0; color:var(--text); font-size:1.05rem; }
[data-testid="stMain"] label[data-testid="stRadioOption"]:has(input:checked) { background:rgba(139,16,26,.14); border-color:var(--red); }
[data-testid="stMain"] label[data-testid="stRadioOption"]:has(input:checked) strong { background:#8B101A; color:white; border-color:#FF3040; }
button:focus-visible,[data-testid="stMain"] label[data-testid="stRadioOption"]:has(input:focus-visible) {
    outline:2px solid #FF8791 !important; outline-offset:3px; }
.control-divider { height:1px; background:var(--border); margin:.5rem 0; }
.control-status { text-align:center; font-size:.7rem; color:var(--muted); }
.control-status span { color:var(--red); margin:0 .35rem; }
[data-testid="stMain"] [data-testid="stButton"] button { border-radius:8px; min-height:42px;
    transition:transform 200ms,box-shadow 200ms,background 200ms; }
[data-testid="stMain"] button[kind="primary"] { background:#FF3040; border:1px solid #FF4655; color:#070708; font-weight:750; }
[data-testid="stMain"] button[kind="primary"]:disabled { background:#FF3040; color:#070708; opacity:.65; }
[data-testid="stMain"] button[kind="secondary"] { background:#17171C; border:1px solid var(--border); }
.page-heading { margin:.1rem 0 .65rem; }
.page-heading h2 { margin:0; padding:0; font-size:1.5rem; }
.page-heading p { margin:.4rem 0 0; color:var(--muted); font-size:.78rem; }
.sample-pill { font-size:.59rem; letter-spacing:.07em; text-transform:uppercase; color:#B7B7C0;
    border:1px solid var(--border); border-radius:5px; padding:.4rem .6rem; white-space:nowrap; }
.metric-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:14px; margin-bottom:1rem; }
.metric-card,.panel,.score-panel { background:#121216; border:1px solid var(--border); border-radius:12px;
    transition:transform 200ms,border-color 200ms,box-shadow 200ms; }
.metric-card { padding:1.1rem 1.2rem; }
.metric-label { font-size:.73rem; color:#BEBEC7; }
.metric-card strong { display:block; font-size:1.8rem; line-height:1.2; letter-spacing:-.045em; margin:.65rem 0 .4rem; }
.metric-card:nth-child(2) strong { color:#FF4655; }
.metric-card small { color:var(--muted); font-size:.63rem; }
.panel { padding:1.3rem 1.4rem; margin-bottom:1rem; }
.panel h3 { font-size:.95rem; margin:0; padding:0; letter-spacing:-.02em; }
.panel-subtitle { font-size:.65rem; color:var(--muted); margin:.4rem 0 1.2rem; }
.bar-list { display:grid; gap:1rem; }
.bar-item > div:first-child { display:flex; justify-content:space-between; gap:1rem; font-size:.72rem; color:#C6C6CE; margin-bottom:.45rem; }
.bar-item strong { font-size:.7rem; color:#E7E7EC; }
.bar-track { height:6px; border-radius:3px; overflow:hidden; background:#25252D; }
.bar-track i { display:block; height:100%; background:linear-gradient(90deg,#8B101A,#FF4655); border-radius:3px; }
.chart-columns { display:flex; justify-content:space-around; align-items:flex-end; height:161px; gap:10px;
    border-bottom:1px solid var(--border); background:repeating-linear-gradient(to top,transparent 0,transparent 39px,rgba(255,255,255,.035) 40px); }
.chart-column { display:flex; flex-direction:column; align-items:center; justify-content:flex-end; width:15%; height:100%; }
.chart-column i { display:block; width:100%; max-width:44px; background:linear-gradient(0deg,#8B101A,#FF4655); border-radius:4px 4px 0 0; }
.chart-column span,.chart-column small { color:#BEBEC7; font-size:.65rem; padding:.35rem 0; }
.chart-foot { display:flex; justify-content:space-between; gap:1rem; font-size:.58rem; color:var(--muted); padding-top:.8rem; }
.score-panel { display:flex; align-items:center; gap:2rem; padding:1.4rem 1.8rem; margin-bottom:1rem; }
.score-panel > .sample-pill { margin-left:auto; align-self:flex-start; }
.score-ring { width:132px; height:132px; flex-shrink:0; padding:6px; border-radius:50%; background:conic-gradient(#FF3040 80%,#292930 0); }
.score-ring > div { height:100%; border-radius:50%; background:#121216; display:flex; align-items:center; justify-content:center; flex-direction:column; }
.score-ring strong { font-size:2rem; letter-spacing:-.05em; }
.score-ring strong span { font-size:1rem; color:var(--muted); }
.score-ring small { color:var(--muted); font-size:.53rem; letter-spacing:.12em; }
.score-number { font-size:2.6rem; font-weight:700; letter-spacing:-.06em; line-height:1.3; }
.score-number span { color:var(--muted); font-size:1.5rem; font-weight:450; }
.score-panel p { font-size:.73rem; color:var(--muted); margin:.2rem 0 0; line-height:1.7; }
.topic-title { font-size:1.15rem; font-weight:650; letter-spacing:-.025em; }
.body-copy { font-size:.77rem; color:var(--muted); line-height:1.7; margin:.6rem 0 1rem; }
.tag { display:inline-block; letter-spacing:0; }
.tag.accent { color:#FF8791; background:rgba(139,16,26,.15); border-color:rgba(255,48,64,.2); }
.insight-row { display:flex; align-items:center; gap:.8rem; padding:.7rem 0; border-top:1px solid var(--border); }
.index { color:#FF8791; font-size:.65rem; background:rgba(139,16,26,.15); padding:.5rem; border-radius:6px; }
.insight-row strong { font-size:.76rem; font-weight:550; }
.insight-row p { font-size:.68rem; color:var(--muted); margin:.2rem 0 0; }
.app-footer { display:flex; justify-content:space-between; gap:1rem; padding:1.4rem 0 .3rem; border-top:1px solid var(--border);
    margin-top:.7rem; font-size:.59rem; color:var(--muted); }
.app-footer > span:first-child { letter-spacing:.1em; white-space:nowrap; }
@media (hover:hover) {
    .metric-card:hover,.panel:hover,.score-panel:hover,[data-testid="stMain"] label[data-testid="stRadioOption"]:hover {
        transform:translateY(-2px); border-color:rgba(255,48,64,.3); box-shadow:0 5px 22px rgba(139,16,26,.08); }
    [data-testid="stMain"] button[kind="primary"]:hover:not(:disabled) {
        transform:translateY(-1px); background:#FF4655; box-shadow:0 4px 20px rgba(255,48,64,.18); }
}
@keyframes arrive { from { opacity:0; transform:translateY(7px); } to { opacity:1; transform:translateY(0); } }
@keyframes indicator { from { opacity:0; transform:scaleY(.3); } to { opacity:1; transform:scaleY(1); } }
@keyframes shimmer { 0%,100% { background-position:0% 50%; } 50% { background-position:100% 50%; } }
@media (max-width:1100px) { .block-container { padding:1.5rem 1.6rem; } .metric-card { padding:1rem; } }
@media (max-width:700px) {
    .block-container { padding:1.2rem 1rem; } .hero { padding-bottom:1.2rem; }
    .metric-grid { grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }
    .page-heading,.score-panel { flex-wrap:wrap; } .score-panel { gap:1rem; padding:1.2rem; }
    .score-panel > .sample-pill { margin-left:0; } .score-ring { width:110px; height:110px; }
    .st-key-question_card { padding:1rem !important; } .exam-top { flex-wrap:wrap; gap:.5rem; }
    .app-footer { flex-direction:column; } .control-status { text-align:left; }
}
@media (prefers-reduced-motion:reduce) {
    *,*::before,*::after { animation:none !important; transition:none !important; scroll-behavior:auto !important; }
    .metric-card:hover,.panel:hover,.score-panel:hover,[data-testid="stMain"] label[data-testid="stRadioOption"]:hover,
    [data-testid="stMain"] button:hover { transform:none !important; }
}
</style>
"""
