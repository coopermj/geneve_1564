#!/usr/bin/env python3
"""Unified edition generator. Seeds offline from existing caches.

Usage:
    python3 scripts/generate.py --edition esv|net|geneva|kjv|all
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from generate_esv import run_esv
from generate_bible import run_net
from generate_kjv import run_kjv

_CORRECTIONS = os.path.join(_ROOT, "data", "corrections_final.json")

def gen_esv():
    run_esv(os.path.join(_ROOT, "livres_esv"), os.path.join(_ROOT, "data", "esv_cache"))

def gen_net():
    run_net(os.path.join(_ROOT, "livres_net"), os.path.join(_ROOT, "data", "net_bible_cache"),
            annotated=False)

def gen_geneva():
    run_net(os.path.join(_ROOT, "livres_geneva"), os.path.join(_ROOT, "data", "net_bible_cache"),
            annotated=True, corrections_path=_CORRECTIONS, plan_markers=False)

def gen_kjv():
    run_kjv(os.path.join(_ROOT, "livres_kjv"), os.path.join(_ROOT, "data", "kjv_cache"))

def main():
    ap = argparse.ArgumentParser(description="Generate a Bible edition's book files (offline).")
    ap.add_argument("--edition", required=True, choices=["esv", "net", "geneva", "kjv", "all"])
    ed = ap.parse_args().edition
    if ed in ("esv", "all"):    gen_esv()
    if ed in ("net", "all"):    gen_net()
    if ed in ("geneva", "all"): gen_geneva()
    if ed in ("kjv", "all"):    gen_kjv()
    print("generate.py: done")

if __name__ == "__main__":
    main()
