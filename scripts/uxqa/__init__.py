"""Reusable Chromium acceptance building blocks for scripts/ux_qa.py.

UX-R07 (#126) splits the former single-file browser suite by responsibility so
the traceable §13 scenario gate stays reviewable: helpers (`support`), offline
Demo journeys (`demo`), authenticated Server journeys (`server`), accessibility
and console/network gates (`accessibility`), deliberate-regression probes
(`probes`), the normative coverage registry (`coverage`) and report rendering
(`report`). `scripts/ux_qa.py` remains the CLI and the only entry point.
"""
