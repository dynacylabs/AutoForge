#!/usr/bin/env python3
"""
Diagnostic script to check MPS (Metal Performance Shaders) availability on macOS.
"""
import sys
import os
import platform
import torch

print("=" * 60)
print("MPS Diagnostic Information")
print("=" * 60)
print()

# System information
print("System Information:")
print(f"  OS: {platform.system()} {platform.release()}")
print(f"  Machine: {platform.machine()}")
print(f"  Python: {sys.version}")
print()

# PyTorch information
print("PyTorch Information:")
print(f"  Version: {torch.__version__}")
print(f"  MPS built: {torch.backends.mps.is_built()}")
print(f"  MPS available: {torch.backends.mps.is_available()}")
print()

# Environment variables
print("Relevant Environment Variables:")
mps_vars = [k for k in os.environ.keys() if 'MPS' in k.upper() or 'PYTORCH' in k.upper()]
if mps_vars:
    for var in mps_vars:
        print(f"  {var}={os.environ[var]}")
else:
    print("  (none found)")
print()

# Try to create a tensor on MPS
print("Testing MPS Device:")
if torch.backends.mps.is_built():
    try:
        device = torch.device("mps")
        test_tensor = torch.zeros(10, 10, device=device)
        result = test_tensor + 1
        print(f"  ✓ Successfully created and operated on MPS tensor")
        print(f"  ✓ MPS is working!")
    except Exception as e:
        print(f"  ✗ Failed to use MPS: {e}")
        print(f"  Traceback:")
        import traceback
        traceback.print_exc()
else:
    print("  ✗ MPS is not built into this PyTorch installation")

print()
print("=" * 60)

# Recommendations
print("\nRecommendations:")
if not torch.backends.mps.is_built():
    print("  1. Install PyTorch with MPS support:")
    print("     pip3 install --upgrade torch torchvision")
elif not torch.backends.mps.is_available():
    print("  Possible issues:")
    print("  1. Check macOS version (requires 12.3+):")
    print("     sw_vers")
    print("  2. Unset PYTORCH_ENABLE_MPS_FALLBACK if set:")
    print("     unset PYTORCH_ENABLE_MPS_FALLBACK")
    print("  3. Try forcing MPS anyway (will be attempted in updated code)")
else:
    print("  ✓ MPS should work! Use --mps flag with autoforge")
