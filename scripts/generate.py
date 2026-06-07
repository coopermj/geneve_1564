#!/usr/bin/env python3
"""Unified edition generator. Seeds offline from existing caches.

Usage:
    python3 scripts/generate.py --edition esv|net|geneva|all
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from generate_esv import run_esv
from generate_bible import run_net

_CORRECTIONS = os.path.join(_ROOT, "data", "corrections_final.json")

def gen_esv():
    run_esv(os.path.join(_ROOT, "livres_esv"), os.path.join(_ROOT, "data", "esv_cache"))

def gen_net():
    run_net(os.path.join(_ROOT, "livres_net"), os.path.join(_ROOT, "data", "net_bible_cache"),
            annotated=False)

def gen_geneva():
    run_net(os.path.join(_ROOT, "livres_geneva"), os.path.join(_ROOT, "data", "net_bible_cache"),
            annotated=True, corrections_path=_CORRECTIONS)

def main():
    ap = argparse.ArgumentParser(description="Generate a Bible edition's book files (offline).")
    ap.add_argument("--edition", required=True, choices=["esv", "net", "geneva", "all"])
    ed = ap.parse_args().edition
    if ed in ("esv", "all"):    gen_esv()
    if ed in ("net", "all"):    gen_net()
    if ed in ("geneva", "all"): gen_geneva()
    print("generate.py: done")

if __name__ == "__main__":
    main()
