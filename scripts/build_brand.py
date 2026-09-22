#!/usr/bin/env python3
"""Regenerate outlined brand SVGs. Requires fonttools and original Archivo/Spectral TTFs.
Usage: python scripts/build_brand.py /path/to/Archivo.ttf /path/to/Spectral.ttf
Raster exports are rendered from these SVGs (512/180 px icons; 1200x630 OG).
"""
from pathlib import Path
import math
import sys
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / 'web'
INK, STOCK, BLUE = '#0E2320', '#DCE5E2', '#2438C9'
archivo, spectral = (TTFont(p) for p in sys.argv[1:3])

def lettering(text, font, x, y, size, tracking=0, fill=INK):
    glyphs, cmap = font.getGlyphSet(), font.getBestCmap()
    scale = size / font['head'].unitsPerEm
    parts = []
    for c in text:
        name = cmap[ord(c)]
        pen = SVGPathPen(glyphs)
        glyphs[name].draw(TransformPen(pen, (scale, 0, 0, -scale, x, y)))
        parts.append(pen.getCommands())
        x += glyphs[name].width * scale + tracking
    return f'<path fill="{fill}" d="{" ".join(parts)}"/>'

def mark(x=0, y=0, scale=1):
    return f'<g transform="translate({x} {y}) scale({scale})"><path fill="{INK}" d="M4 4h8v3H7v18h5v3H4zm24 0h-8v3h5v18h-5v3h8z"/><path fill="{BLUE}" d="M12 12h8v8h-8z"/></g>'

def svg(body, w, h, title):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{title}"><title>{title}</title>{body}</svg>\n'

(WEB/'logo.svg').write_text(svg(mark(),32,32,'Retainer — value held until acceptance'))
# Pixel-aligned two-pixel clasp strokes at 16px, so the small tab icon stays crisp.
favicon = f'<path fill="{STOCK}" d="M0 0h32v32H0z"/><path fill="{INK}" d="M4 4h8v4H8v16h4v4H4zm24 0h-8v4h4v16h-4v4h8z"/><path fill="{BLUE}" d="M12 12h8v8h-8z"/>'
(WEB/'favicon.svg').write_text(svg(favicon,32,32,'Retainer'))
(WEB/'logo-wordmark.svg').write_text(svg(mark(0,0,2)+lettering('Retainer',archivo,79,48,46,-1.3),310,64,'Retainer'))
(WEB/'logo-square.svg').write_text(svg(f'<path fill="{STOCK}" d="M0 0h512v512H0z"/>'+mark(48,48,13),512,512,'Retainer'))
body = f'<path fill="{STOCK}" d="M0 0h1200v630H0z"/>'
# Security-paper linework is confined to the seal area, away from reading.
for i in range(16):
    pts=[]
    for j in range(361):
        t=j*math.pi/180
        r=148+i*3.3+9*math.sin(12*t+i*.19)
        pts.append(f'{945+r*math.cos(t):.2f},{294+r*math.sin(t):.2f}')
    body+=f'<polygon points="{" ".join(pts)}" fill="none" stroke="#B9C7C2" stroke-width=".7"/>'
body += '<path d="M64 126H1136M64 534H1136" stroke="#99ACA4" stroke-dasharray="2 6"/>'
body += mark(58,41,1.45)
body += lettering('Retainer',archivo,121,80,32,-.8)
body += lettering('Built on GenLayer',archivo,862,78,20,-.2)
body += lettering('Retainer',archivo,60,271,118,-4)
body += lettering('Acceptance',spectral,65,360,56,-1)
body += lettering('before payment.',spectral,65,424,56,-1)
body += mark(797,146,9.25)
body += lettering('Agent work. Escrow. Consensus.',archivo,65,580,21,-.3)
body += lettering('Bradbury testnet',archivo,915,580,20,-.25)
(WEB/'og.svg').write_text(svg(body,1200,630,'Retainer — Acceptance before payment. Built on GenLayer. Bradbury testnet.'))
