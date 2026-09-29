"""Swappable UI themes for Bandz Terminal.

Each theme is a self-contained <style> block covering the same CSS class
set (the HTML in web.py doesn't change). The sidebar radio switches
themes; the choice persists in marketpulse/theme.json (gitignored).
"""

import json
import os

THEME_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "theme.json")

THEMES = {
    "cyber": "Cyber",
    "gold": "Gold",
    "retro": "Retro CRT",
    "space": "Space",
}

CYBER_CSS = """
<style>
/* PRO TERMINAL -- refined dark, restrained cyan accent */
.block-container { padding-top: 1rem; max-width: 1100px; }
.up { color: #34d399; } .down { color: #f87171; }
.flat { color: #8b98a5; } .gold { color: #22d3ee; }

.stApp { background-color: #07090c; }
[data-testid="stSidebar"] { background-color: #0a0d12; }

/* command strip */
.bz-strip { display: flex; align-items: center; gap: 10px;
  background: #0c1015; border: 1px solid #1b232d; border-radius: 10px;
  padding: 10px 14px; margin-bottom: 8px; }
.bz-title { font-size: 15px; font-weight: 700; letter-spacing: 1.5px;
  color: #e6edf3; white-space: nowrap; }
.bz-badge { font-size: 10px; font-weight: 600; letter-spacing: 1px;
  padding: 4px 10px; border-radius: 20px; white-space: nowrap;
  display: inline-flex; align-items: center; gap: 6px; }
.bz-badge .dot { width: 7px; height: 7px; border-radius: 50%; flex: none; }
.bz-badge.open { color: #34d399; background: rgba(52,211,153,.08); }
.bz-badge.open .dot { background: #34d399; }
.bz-badge.shut { color: #f87171; background: rgba(248,113,113,.08); }
.bz-badge.shut .dot { background: #f87171; }
.bz-disc { color: #8b98a5; font-size: 11px; margin: 0 0 10px 2px; }

/* index strip */
.bz-idx { display: grid; grid-template-columns: repeat(4, 1fr);
  gap: 8px; margin: 0 0 10px 0; }
.bz-idxc { background: #0c1015; border: 1px solid #1b232d;
  border-radius: 10px; padding: 10px 6px; text-align: center; }
.bz-idxc .s { font-size: 10px; font-weight: 600; color: #8b98a5;
  letter-spacing: 1.5px; }
.bz-idxc .p { font-family: monospace; font-size: 15px; font-weight: 600;
  margin-top: 4px; font-variant-numeric: tabular-nums; color: #e6edf3; }
.bz-idxc .c { font-family: monospace; font-size: 11px; font-weight: 600;
  margin-top: 2px; }

/* ticker tape: snap-scroll strip, see SHARED_CSS (.tape-strip) */

/* sections */
.bz-sec { display: flex; align-items: baseline; gap: 10px; margin: 24px 0 2px;
  border-bottom: 1px solid #1b232d; padding-bottom: 8px; }
.bz-num { font-family: monospace; font-size: 11px; color: #5b6773;
  font-weight: 600; flex: none; }
.bz-sec h2 { margin: 0; font-size: 16px; font-weight: 650; color: #e6edf3; }
.bz-sub { color: #8b98a5; font-size: 12px; margin: 6px 0 12px 0; }

/* watch cards */
.bz-card { background: #0c1015; border: 1px solid #1b232d;
  border-radius: 12px; padding: 14px 16px; margin-bottom: 10px; }
.bz-top { display: flex; justify-content: space-between; align-items: center; }
.bz-sym { font-family: monospace; font-size: 15px; font-weight: 700;
  letter-spacing: .5px; color: #e6edf3; }
.bz-chip { font-size: 9px; font-weight: 600; color: #8b98a5;
  border: 1px solid #232d38; padding: 3px 8px; margin-left: 8px;
  border-radius: 4px; text-transform: uppercase; letter-spacing: 1px;
  vertical-align: 2px; background: #10151b; }
.bz-chg { font-family: monospace; font-size: 14px; font-weight: 700;
  padding: 5px 10px; border-radius: 6px; }
.bz-chg.up { color: #34d399; background: rgba(52,211,153,.10); }
.bz-chg.down { color: #f87171; background: rgba(248,113,113,.10); }
.bz-chg.flat { color: #8b98a5; background: rgba(139,152,165,.10); }
.bz-price { font-family: monospace; font-size: 30px; font-weight: 700;
  letter-spacing: -.5px; margin-top: 8px; color: #f2f5f8;
  font-variant-numeric: tabular-nums; }
.bz-spark { width: 100%; height: 56px; margin-top: 8px; display: block; }
.bz-label { display: block; color: #5b6773; font-size: 10px; font-weight: 600;
  letter-spacing: 1.5px; margin-top: 12px; text-transform: uppercase; }
.bz-bar { height: 5px; background: #161c24; border-radius: 3px;
  margin-top: 6px; overflow: hidden; }
.bz-bar > div { height: 100%; border-radius: 3px; }
.bz-meta { color: #8b98a5; font-size: 12px; margin-top: 10px; line-height: 1.6; }
.bz-news { margin-top: 12px; border-top: 1px solid #1b232d; padding-top: 10px; }
.bz-news .bz-item { margin-bottom: 8px; }
.bz-news a { color: #dbe4ec; font-size: 13px; line-height: 1.5;
  text-decoration: none; }
.bz-news a:hover { color: #22d3ee; }
.bz-src { display: block; color: #5b6773; font-size: 10px; margin-top: 3px; }

/* news wire */
.bz-wire { border: 1px solid #1b232d; border-radius: 12px;
  background: #0c1015; overflow: hidden; }
.bz-witem { display: grid; grid-template-columns: 56px 1fr; gap: 10px;
  padding: 11px 14px; border-bottom: 1px solid #141a22; }
.bz-witem:last-child { border-bottom: 0; }
.bz-wsym { color: #22d3ee; font-family: monospace; font-size: 11px;
  font-weight: 700; line-height: 1.5; }
.bz-witem p { margin: 0; font-size: 13px; line-height: 1.45; color: #dbe4ec; }
.bz-witem p a { color: #dbe4ec; text-decoration: none; }
.bz-witem p a:hover { color: #22d3ee; }
.bz-witem small { color: #5b6773; font-size: 10px; }

/* heatmap */
.heat { display: grid; grid-template-columns: repeat(auto-fill, minmax(88px, 1fr));
  gap: 6px; margin: 8px 0 16px 0; }
.tile { padding: 9px 4px; text-align: center; font-family: monospace;
  border-radius: 8px; }
.tile b { display: block; font-size: 13px; color: #e6edf3; }
.tile span { font-size: 11px; }
.heat-label { font-size: 11px; color: #8b98a5; margin: 12px 0 2px 0;
  letter-spacing: 1.5px; text-transform: uppercase; font-weight: 600; }

/* streamlit controls */
[data-testid="stBaseButton-primary"] { background: #22d3ee !important;
  color: #062026 !important; font-weight: 700 !important;
  border: none !important; border-radius: 8px !important; }
[data-testid="stBaseButton-secondary"] { background: transparent !important;
  color: #dbe4ec !important; border: 1px solid #232d38 !important;
  border-radius: 8px !important; }
[data-testid="stExpander"] { border: 1px solid #1b232d !important;
  background: #0c1015 !important; border-radius: 10px !important; }
[data-testid="stTabs"] button { color: #8b98a5 !important; }
[data-testid="stTabs"] button[aria-selected="true"] { color: #f2f5f8 !important; }
a { color: #22d3ee !important; }
</style>
"""

GOLD_CSS = """
<style>
/* Gold on charcoal -- Stackz blotter theme */
.block-container { padding-top: 1rem; max-width: 1100px; }
.up { color: #48d597; } .down { color: #ff6b63; }
.flat { color: #aaa69a; } .gold { color: #d4af37; }

/* command strip */
.bz-strip { display: flex; align-items: center; gap: 10px;
  background: #1c1c1e; border: 1px solid #49453b; border-radius: 8px;
  padding: 10px 14px; margin-bottom: 10px; }
.bz-title { font-size: 19px; font-weight: 800; letter-spacing: -0.5px; }
.bz-badge { font-family: monospace; font-size: 10px; font-weight: 700;
  letter-spacing: 1px; padding: 4px 10px; border-radius: 20px; }
.bz-badge.open { color: #48d597; background: #123b2c; }
.bz-badge.shut { color: #ff6b63; background: #421f1d; }
.bz-disc { color: #aaa69a; font-size: 11px; margin: 0 0 10px 2px; }

/* index strip */
.bz-idx { display: grid; grid-template-columns: repeat(4, 1fr);
  gap: 8px; margin: 0 0 10px 0; }
.bz-idxc { background: #1c1c1e; border: 1px solid #49453b;
  border-radius: 8px; padding: 8px 6px; text-align: center; }
.bz-idxc .s { font-family: monospace; font-size: 10px; font-weight: 700;
  color: #aaa69a; letter-spacing: 1px; }
.bz-idxc .p { font-family: monospace; font-size: 15px; font-weight: 700;
  margin-top: 4px; font-variant-numeric: tabular-nums; }
.bz-idxc .c { font-family: monospace; font-size: 11px; font-weight: 700;
  margin-top: 2px; }

/* ticker tape: snap-scroll strip, see SHARED_CSS (.tape-strip) */

/* numbered sections */
.bz-sec { display: flex; align-items: center; gap: 12px; margin: 26px 0 4px; }
.bz-num { display: grid; place-items: center; width: 28px; height: 28px;
  border-radius: 50%; background: #d4af37; color: #1a1a1c;
  font-family: monospace; font-size: 11px; font-weight: 800; flex: none; }
.bz-sec h2 { margin: 0; font-size: 19px; letter-spacing: -0.5px; }
.bz-sub { color: #aaa69a; font-size: 12px; margin: 4px 0 14px 40px; }

/* watch cards */
.bz-card { background: linear-gradient(180deg, #202024, #1a1a1c);
  border: 1px solid #49453b; border-radius: 14px; padding: 16px;
  margin-bottom: 12px; box-shadow: 0 2px 14px rgba(0,0,0,0.35); }
.bz-top { display: flex; justify-content: space-between; align-items: center; }
.bz-sym { font-family: monospace; font-size: 16px; font-weight: 800;
  letter-spacing: 0.5px; }
.bz-chip { font-family: monospace; font-size: 9px; font-weight: 700;
  color: #aaa69a; border: 1px solid #49453b; border-radius: 10px;
  padding: 3px 8px; margin-left: 8px; text-transform: uppercase;
  letter-spacing: 0.5px; vertical-align: 2px; }
.bz-chg { font-family: monospace; font-size: 15px; font-weight: 800;
  padding: 5px 10px; border-radius: 9px; }
.bz-chg.up { color: #48d597; background: rgba(72,213,151,0.10); }
.bz-chg.down { color: #ff6b63; background: rgba(255,107,99,0.10); }
.bz-chg.flat { color: #aaa69a; background: rgba(170,166,154,0.10); }
.bz-price { font-family: monospace; font-size: 32px; font-weight: 800;
  letter-spacing: -1px; margin-top: 10px; font-variant-numeric: tabular-nums; }
.bz-spark { width: 100%; height: 60px; margin-top: 10px;
  background: rgba(36,36,38,0.6); border-radius: 8px; display: block; }
.bz-label { display: block; color: #aaa69a; font-family: monospace;
  font-size: 9px; font-weight: 700; letter-spacing: 1.5px; margin-top: 12px; }
.bz-bar { height: 6px; background: #2c2c2e; border-radius: 3px;
  margin-top: 6px; overflow: hidden; }
.bz-bar > div { height: 100%; border-radius: 3px; }
.bz-meta { color: #aaa69a; font-family: monospace; font-size: 11px;
  margin-top: 10px; line-height: 1.7; }
.bz-news { margin-top: 12px; border-top: 1px solid #34322d; padding-top: 10px; }
.bz-news .bz-item { margin-bottom: 8px; }
.bz-news a { color: #f6f4ee; font-size: 13px; line-height: 1.5;
  text-decoration: none; }
.bz-news a:hover { color: #d4af37; }
.bz-src { display: block; color: #aaa69a; font-family: monospace;
  font-size: 10px; font-weight: 600; margin-top: 3px; }

/* news wire */
.bz-wire { border: 1px solid #49453b; border-radius: 12px;
  background: #1c1c1e; overflow: hidden; }
.bz-witem { display: grid; grid-template-columns: 60px 1fr; gap: 10px;
  padding: 12px 14px; border-bottom: 1px solid #34322d; }
.bz-witem:last-child { border-bottom: 0; }
.bz-witem:hover { background: rgba(212,175,55,0.04); }
.bz-wsym { color: #d4af37; font-family: monospace; font-size: 11px;
  font-weight: 800; line-height: 1.5; }
.bz-witem p { margin: 0; font-size: 12.5px; line-height: 1.45; }
.bz-witem p a { color: #f6f4ee; text-decoration: none; }
.bz-witem p a:hover { color: #d4af37; }
.bz-witem small { color: #aaa69a; font-family: monospace; font-size: 10px;
  font-weight: 600; }

/* heatmap */
.heat { display: grid; grid-template-columns: repeat(auto-fill, minmax(92px, 1fr));
  gap: 6px; margin: 8px 0 16px 0; }
.tile { border-radius: 8px; padding: 10px 4px; text-align: center;
  font-family: monospace; }
.tile b { display: block; font-size: 14px; color: #f6f4ee; }
.tile span { font-size: 12px; }
.heat-label { font-family: monospace; font-size: 11px; color: #aaa69a;
  margin: 12px 0 2px 0; letter-spacing: 2px; text-transform: uppercase; }
</style>
"""

RETRO_CSS = """
<style>
/* RETRO CRT theme -- amber/green phosphor, scanlines, chunky monospace */
.block-container { padding-top: 1rem; max-width: 1100px; }
.up { color: #33ff33; } .down { color: #ff3333; }
.flat { color: #8a7a55; } .gold { color: #ffb000; }

.stApp { background-color: #050302;
  background-image: repeating-linear-gradient(0deg,
    rgba(255,176,0,0.035) 0 1px, transparent 1px 3px); }
[data-testid="stSidebar"] { background-color: #0a0703; }

.bz-strip { display: flex; align-items: center; gap: 10px;
  background: #0a0703; border: 2px solid #ffb000; border-radius: 0;
  padding: 10px 14px; margin-bottom: 10px;
  box-shadow: 0 0 16px rgba(255,176,0,0.25); }
.bz-title { font-family: monospace; font-size: 18px; font-weight: 800;
  letter-spacing: 2px; color: #ffb000; white-space: nowrap;
  text-shadow: 0 0 10px rgba(255,176,0,0.8); }
.bz-badge { font-family: monospace; font-size: 10px; font-weight: 700;
  letter-spacing: 1px; padding: 4px 10px; border-radius: 0;
  white-space: nowrap; border: 1px solid currentColor; }
.bz-badge.open { color: #33ff33; background: #021202; }
.bz-badge.shut { color: #ff3333; background: #160202; }
.bz-disc { color: #8a7a55; font-size: 11px; margin: 0 0 10px 2px;
  font-family: monospace; }

.bz-idx { display: grid; grid-template-columns: repeat(4, 1fr);
  gap: 8px; margin: 0 0 10px 0; }
.bz-idxc { background: #0a0703; border: 1px solid #6b5200; border-radius: 0;
  padding: 8px 6px; text-align: center; }
.bz-idxc .s { font-family: monospace; font-size: 10px; font-weight: 700;
  color: #8a7a55; letter-spacing: 1px; }
.bz-idxc .p { font-family: monospace; font-size: 15px; font-weight: 700;
  margin-top: 4px; color: #ffb000;
  text-shadow: 0 0 8px rgba(255,176,0,0.6); }
.bz-idxc .c { font-family: monospace; font-size: 11px; font-weight: 700;
  margin-top: 2px; }

/* ticker tape: snap-scroll strip, see SHARED_CSS (.tape-strip) */

.bz-sec { display: flex; align-items: center; gap: 12px; margin: 26px 0 4px; }
.bz-num { display: grid; place-items: center; width: 28px; height: 28px;
  border-radius: 0; background: #ffb000; color: #0a0703;
  font-family: monospace; font-size: 11px; font-weight: 800; flex: none; }
.bz-sec h2 { margin: 0; font-size: 19px; letter-spacing: 1px;
  font-family: monospace; color: #ffb000;
  text-shadow: 0 0 10px rgba(255,176,0,0.7); }
.bz-sub { color: #8a7a55; font-size: 12px; margin: 4px 0 14px 40px;
  font-family: monospace; }

.bz-card { background: #070503; border: 1px solid #6b5200; border-radius: 0;
  padding: 16px; margin-bottom: 12px;
  box-shadow: inset 0 0 30px rgba(255,176,0,0.05); }
.bz-top { display: flex; justify-content: space-between; align-items: center; }
.bz-sym { font-family: monospace; font-size: 16px; font-weight: 800;
  letter-spacing: 1px; color: #ffb000;
  text-shadow: 0 0 8px rgba(255,176,0,0.7); }
.bz-chip { font-family: monospace; font-size: 9px; font-weight: 700;
  color: #33ff33; border: 1px solid #1d5c1d; padding: 3px 8px; margin-left: 8px;
  text-transform: uppercase; letter-spacing: 1px; vertical-align: 2px; }
.bz-chg { font-family: monospace; font-size: 15px; font-weight: 800;
  padding: 5px 10px; border-radius: 0; }
.bz-chg.up { color: #33ff33; background: #021202; border: 1px solid #1d5c1d; }
.bz-chg.down { color: #ff3333; background: #160202; border: 1px solid #5c1d1d; }
.bz-chg.flat { color: #8a7a55; background: #0a0703; border: 1px solid #6b5200; }
.bz-price { font-family: monospace; font-size: 32px; font-weight: 800;
  letter-spacing: -1px; margin-top: 10px; color: #ffe9c4;
  text-shadow: 0 0 12px rgba(255,176,0,0.6); }
.bz-spark { width: 100%; height: 60px; margin-top: 10px; background: #030201;
  border: 1px solid #3a2d00; display: block; }
.bz-label { display: block; color: #8a7a55; font-family: monospace;
  font-size: 9px; font-weight: 700; letter-spacing: 2px; margin-top: 12px; }
.bz-bar { height: 6px; background: #140e02; border-radius: 0; margin-top: 6px;
  overflow: hidden; border: 1px solid #3a2d00; }
.bz-bar > div { height: 100%; border-radius: 0; }
.bz-meta { color: #8a7a55; font-family: monospace; font-size: 11px;
  margin-top: 10px; line-height: 1.7; }
.bz-news { margin-top: 12px; border-top: 1px dashed #6b5200; padding-top: 10px; }
.bz-news .bz-item { margin-bottom: 8px; }
.bz-news a { color: #ffe9c4; font-size: 13px; line-height: 1.5;
  text-decoration: none; font-family: monospace; }
.bz-news a:hover { color: #ffb000; }
.bz-src { display: block; color: #8a7a55; font-family: monospace;
  font-size: 10px; font-weight: 600; margin-top: 3px; }

.bz-wire { border: 1px solid #6b5200; background: #070503; overflow: hidden; }
.bz-witem { display: grid; grid-template-columns: 60px 1fr; gap: 10px;
  padding: 12px 14px; border-bottom: 1px solid #2a2005; }
.bz-witem:last-child { border-bottom: 0; }
.bz-witem:hover { background: #0d0903; }
.bz-wsym { color: #ffb000; font-family: monospace; font-size: 11px;
  font-weight: 800; line-height: 1.5; }
.bz-witem p { margin: 0; font-size: 12.5px; line-height: 1.45; color: #ffe9c4;
  font-family: monospace; }
.bz-witem p a { color: #ffe9c4; text-decoration: none; }
.bz-witem p a:hover { color: #ffb000; }
.bz-witem small { color: #8a7a55; font-family: monospace; font-size: 10px;
  font-weight: 600; }

.heat { display: grid; grid-template-columns: repeat(auto-fill, minmax(92px, 1fr));
  gap: 6px; margin: 8px 0 16px 0; }
.tile { padding: 10px 4px; text-align: center; font-family: monospace;
  border: 1px solid #3a2d00; border-radius: 0; }
.tile b { display: block; font-size: 14px; color: #ffe9c4; }
.tile span { font-size: 12px; }
.heat-label { font-family: monospace; font-size: 11px; color: #ffb000;
  margin: 12px 0 2px 0; letter-spacing: 2px; text-transform: uppercase; }

[data-testid="stBaseButton-primary"] { background: #ffb000 !important;
  color: #0a0703 !important; font-weight: 800 !important;
  border: none !important; border-radius: 0 !important;
  font-family: monospace !important; }
[data-testid="stBaseButton-secondary"] { background: transparent !important;
  color: #ffb000 !important; border: 1px solid #6b5200 !important;
  border-radius: 0 !important; font-family: monospace !important; }
[data-testid="stExpander"] { border: 1px solid #6b5200 !important;
  background: #070503 !important; border-radius: 0 !important; }
[data-testid="stTabs"] button[aria-selected="true"] { color: #ffb000 !important; }
a { color: #ffb000 !important; }
</style>

"""

SPACE_CSS = """
<style>
/* SPACE theme -- nebula backdrop, glassmorphic cards, cyan/violet glow */
.block-container { padding-top: 1rem; max-width: 1100px; }
.up { color: #4ade80; } .down { color: #fb7185; }
.flat { color: #8b93b8; } .gold { color: #22d3ee; }

.stApp { background-color: #040412;
  background-image:
    radial-gradient(ellipse 60% 40% at 15% 10%, rgba(124,58,237,0.16), transparent),
    radial-gradient(ellipse 50% 35% at 85% 25%, rgba(34,211,238,0.12), transparent),
    radial-gradient(ellipse 55% 45% at 50% 90%, rgba(168,85,247,0.10), transparent); }
[data-testid="stSidebar"] { background-color: rgba(8,8,24,0.9); }

.bz-strip { display: flex; align-items: center; gap: 10px;
  background: rgba(20,16,48,0.55); border: 1px solid rgba(167,139,250,0.4);
  border-radius: 16px; padding: 10px 16px; margin-bottom: 10px;
  backdrop-filter: blur(12px);
  box-shadow: 0 0 24px rgba(139,92,246,0.25); }
.bz-title { font-size: 18px; font-weight: 800; letter-spacing: 3px;
  color: #e9d5ff; white-space: nowrap;
  text-shadow: 0 0 16px rgba(167,139,250,0.9); }
.bz-badge { font-size: 10px; font-weight: 700; letter-spacing: 1px;
  padding: 4px 12px; border-radius: 20px; white-space: nowrap;
  font-family: monospace; }
.bz-badge.open { color: #4ade80; background: rgba(74,222,128,0.12);
  border: 1px solid rgba(74,222,128,0.5);
  box-shadow: 0 0 12px rgba(74,222,128,0.3); }
.bz-badge.shut { color: #fb7185; background: rgba(251,113,133,0.12);
  border: 1px solid rgba(251,113,133,0.5);
  box-shadow: 0 0 12px rgba(251,113,133,0.3); }
.bz-disc { color: #8b93b8; font-size: 11px; margin: 0 0 10px 2px; }

.bz-idx { display: grid; grid-template-columns: repeat(4, 1fr);
  gap: 8px; margin: 0 0 10px 0; }
.bz-idxc { background: rgba(24,20,54,0.55);
  border: 1px solid rgba(139,92,246,0.35); border-radius: 14px;
  padding: 8px 6px; text-align: center; backdrop-filter: blur(10px);
  box-shadow: 0 0 16px rgba(139,92,246,0.15); }
.bz-idxc .s { font-size: 10px; font-weight: 700; color: #8b93b8;
  letter-spacing: 2px; font-family: monospace; }
.bz-idxc .p { font-size: 15px; font-weight: 700; margin-top: 4px;
  color: #f1f5ff; }
.bz-idxc .c { font-size: 11px; font-weight: 700; margin-top: 2px;
  font-family: monospace; }

/* ticker tape: snap-scroll strip, see SHARED_CSS (.tape-strip) */

.bz-sec { display: flex; align-items: center; gap: 12px; margin: 26px 0 4px; }
.bz-num { display: grid; place-items: center; width: 30px; height: 30px;
  border-radius: 50%; background: linear-gradient(135deg, #7c3aed, #22d3ee);
  color: #fff; font-family: monospace; font-size: 11px; font-weight: 800;
  flex: none; box-shadow: 0 0 14px rgba(139,92,246,0.6); }
.bz-sec h2 { margin: 0; font-size: 19px; letter-spacing: 1px; color: #ede9fe;
  text-shadow: 0 0 12px rgba(167,139,250,0.5); }
.bz-sub { color: #8b93b8; font-size: 12px; margin: 4px 0 14px 42px; }

.bz-card { background: rgba(22,18,52,0.55);
  border: 1px solid rgba(139,92,246,0.35); border-radius: 18px;
  padding: 16px; margin-bottom: 12px; backdrop-filter: blur(12px);
  box-shadow: 0 0 24px rgba(139,92,246,0.18); }
.bz-top { display: flex; justify-content: space-between; align-items: center; }
.bz-sym { font-size: 16px; font-weight: 800; letter-spacing: 1px;
  color: #f1f5ff; font-family: monospace;
  text-shadow: 0 0 10px rgba(34,211,238,0.5); }
.bz-chip { font-size: 9px; font-weight: 700; color: #a5f3fc;
  border: 1px solid rgba(34,211,238,0.45); background: rgba(34,211,238,0.08);
  padding: 3px 10px; border-radius: 20px; margin-left: 8px;
  text-transform: uppercase; letter-spacing: 1px; vertical-align: 2px; }
.bz-chg { font-family: monospace; font-size: 15px; font-weight: 800;
  padding: 5px 12px; border-radius: 20px; }
.bz-chg.up { color: #4ade80; background: rgba(74,222,128,0.12);
  border: 1px solid rgba(74,222,128,0.5);
  box-shadow: 0 0 12px rgba(74,222,128,0.25); }
.bz-chg.down { color: #fb7185; background: rgba(251,113,133,0.12);
  border: 1px solid rgba(251,113,133,0.5);
  box-shadow: 0 0 12px rgba(251,113,133,0.25); }
.bz-chg.flat { color: #8b93b8; background: rgba(139,147,184,0.10);
  border: 1px solid rgba(139,147,184,0.4); }
.bz-price { font-size: 32px; font-weight: 800; letter-spacing: -1px;
  margin-top: 10px; color: #ffffff;
  text-shadow: 0 0 18px rgba(34,211,238,0.5); font-family: monospace; }
.bz-spark { width: 100%; height: 60px; margin-top: 10px;
  background: rgba(4,4,18,0.6); border: 1px solid rgba(139,92,246,0.25);
  border-radius: 10px; display: block; }
.bz-label { display: block; color: #8b93b8; font-family: monospace;
  font-size: 9px; font-weight: 700; letter-spacing: 2px; margin-top: 12px; }
.bz-bar { height: 6px; background: rgba(139,92,246,0.12); border-radius: 3px;
  margin-top: 6px; overflow: hidden; }
.bz-bar > div { height: 100%; border-radius: 3px;
  box-shadow: 0 0 10px rgba(34,211,238,0.8); }
.bz-meta { color: #8b93b8; font-family: monospace; font-size: 11px;
  margin-top: 10px; line-height: 1.7; }
.bz-news { margin-top: 12px; border-top: 1px solid rgba(139,92,246,0.3);
  padding-top: 10px; }
.bz-news .bz-item { margin-bottom: 8px; }
.bz-news a { color: #ede9fe; font-size: 13px; line-height: 1.5;
  text-decoration: none; }
.bz-news a:hover { color: #22d3ee; }
.bz-src { display: block; color: #8b93b8; font-family: monospace;
  font-size: 10px; font-weight: 600; margin-top: 3px; }

.bz-wire { border: 1px solid rgba(139,92,246,0.3);
  background: rgba(22,18,52,0.55); border-radius: 14px; overflow: hidden;
  backdrop-filter: blur(10px); }
.bz-witem { display: grid; grid-template-columns: 60px 1fr; gap: 10px;
  padding: 12px 14px; border-bottom: 1px solid rgba(139,92,246,0.15); }
.bz-witem:last-child { border-bottom: 0; }
.bz-witem:hover { background: rgba(139,92,246,0.08); }
.bz-wsym { color: #a5f3fc; font-family: monospace; font-size: 11px;
  font-weight: 800; line-height: 1.5;
  text-shadow: 0 0 8px rgba(34,211,238,0.6); }
.bz-witem p { margin: 0; font-size: 12.5px; line-height: 1.45; color: #ede9fe; }
.bz-witem p a { color: #ede9fe; text-decoration: none; }
.bz-witem p a:hover { color: #22d3ee; }
.bz-witem small { color: #8b93b8; font-family: monospace; font-size: 10px;
  font-weight: 600; }

.heat { display: grid; grid-template-columns: repeat(auto-fill, minmax(92px, 1fr));
  gap: 6px; margin: 8px 0 16px 0; }
.tile { padding: 10px 4px; text-align: center; font-family: monospace;
  border: 1px solid rgba(139,92,246,0.25); border-radius: 10px; }
.tile b { display: block; font-size: 14px; color: #f1f5ff; }
.tile span { font-size: 12px; }
.heat-label { font-family: monospace; font-size: 11px; color: #a5f3fc;
  margin: 12px 0 2px 0; letter-spacing: 2px; text-transform: uppercase; }

[data-testid="stBaseButton-primary"] {
  background: linear-gradient(135deg, #7c3aed, #22d3ee) !important;
  color: #fff !important; font-weight: 800 !important; border: none !important;
  border-radius: 12px !important;
  box-shadow: 0 0 18px rgba(139,92,246,0.5) !important; }
[data-testid="stBaseButton-secondary"] { background: transparent !important;
  color: #a5f3fc !important; border: 1px solid rgba(34,211,238,0.5) !important;
  border-radius: 12px !important; }
[data-testid="stExpander"] { border: 1px solid rgba(139,92,246,0.3) !important;
  background: rgba(22,18,52,0.55) !important; border-radius: 12px !important; }
[data-testid="stTabs"] button[aria-selected="true"] { color: #a5f3fc !important;
  text-shadow: 0 0 10px rgba(34,211,238,0.7); }
a { color: #22d3ee !important; }
</style>

"""

THEME_CSS = {
    "cyber": CYBER_CSS,
    "gold": GOLD_CSS,
    "retro": RETRO_CSS,
    "space": SPACE_CSS,
}

#: Shared structural stylesheet, injected after the theme. Theme-agnostic:
#: motion policy, the snap-scroll ticker strip, card rhythm, and phone
#: layout. Colors stay in the themes; this only tunes structure.
SHARED_CSS = """
<style>
/* ===== Bandz shared: motion, ticker strip, card rhythm, phones ===== */

/* Ticker strip: native horizontal scroll, zero animation cost.
   Replaces the old infinite marquee (a constant GPU drain on phones). */
.tape-strip { display: flex; gap: 8px; overflow-x: auto;
  padding: 10px 2px; margin: 0 0 12px 0;
  scroll-snap-type: x proximity; -webkit-overflow-scrolling: touch;
  scrollbar-width: none; -ms-overflow-style: none; }
.tape-strip::-webkit-scrollbar { display: none; }
.tape-chip { scroll-snap-align: start; flex: none;
  display: inline-flex; align-items: baseline; gap: 8px;
  border: 1px solid rgba(255,255,255,.10); border-radius: 9px;
  padding: 8px 13px; background: rgba(255,255,255,.035);
  font-family: monospace; font-size: 12px; color: #c2ccd6; }
.tape-chip b { font-weight: 700; color: #f2f6fa; letter-spacing: .5px; }
.tape-hint { color: #5b6773; font-size: 10px; font-weight: 600;
  letter-spacing: 1.5px; text-transform: uppercase; margin: 16px 0 0 2px; }

/* Card rhythm: roomier, calmer */
.bz-card { padding: 18px; border-radius: 14px; }
.bz-price { font-size: 34px; letter-spacing: -1px; }
.bz-sec { margin: 30px 0 4px; }

/* Phones: tighter gutters, slimmer header, readable type */
@media (max-width: 640px) {
  .block-container { padding-left: 12px; padding-right: 12px; }
  .bz-title { font-size: 13px; letter-spacing: 1px; }
  .bz-strip { padding: 8px 12px; }
  .bz-card { padding: 14px; border-radius: 12px; }
  .bz-price { font-size: 30px; }
  .bz-sec h2 { font-size: 15px; }
}

/* Respect reduced-motion: kill all animation */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important;
    transition: none !important; }
}
</style>
"""


def load_theme():
    """Theme key from disk, defaulting to cyber."""
    try:
        with open(THEME_FILE) as f:
            key = json.load(f).get("theme", "cyber")
    except (FileNotFoundError, json.JSONDecodeError):
        return "cyber"
    return key if key in THEME_CSS else "cyber"


def save_theme(key):
    """Persist the theme choice. Best-effort, never raises."""
    if key not in THEME_CSS:
        return
    try:
        with open(THEME_FILE, "w") as f:
            json.dump({"theme": key}, f)
    except OSError:
        pass
