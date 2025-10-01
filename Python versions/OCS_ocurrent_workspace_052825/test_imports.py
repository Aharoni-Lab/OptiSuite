#!/usr/bin/env python3
"""
Test script to verify all imports work correctly
"""

print("Testing imports...")

try:
    import sys
    print(f"✓ Python version: {sys.version}")
except ImportError as e:
    print(f"✗ sys import failed: {e}")

try:
    import os
    print("✓ os imported successfully")
except ImportError as e:
    print(f"✗ os import failed: {e}")

try:
    import clr
    print("✓ clr (pythonnet) imported successfully")
except ImportError as e:
    print(f"✗ clr import failed: {e}")

try:
    import cv2
    print(f"✓ cv2 (OpenCV) imported successfully - version: {cv2.__version__}")
except ImportError as e:
    print(f"✗ cv2 import failed: {e}")

try:
    import numpy as np
    print(f"✓ numpy imported successfully - version: {np.__version__}")
except ImportError as e:
    print(f"✗ numpy import failed: {e}")

try:
    import gxipy as gx
    print("✓ gxipy imported successfully")
except ImportError as e:
    print(f"✗ gxipy import failed: {e}")

try:
    from PyQt5.QtWidgets import QApplication
    print("✓ PyQt5 imported successfully")
except ImportError as e:
    print(f"✗ PyQt5 import failed: {e}")

# Test SC3U DLL loading
try:
    import clr
    import os
    
    cwd_path = os.path.join(os.getcwd(), 'SC3U.dll')
    if os.path.exists(cwd_path):
        clr.AddReference(os.path.abspath(cwd_path))
        from SC3Us import SC3U
        print("✓ SC3U.dll loaded successfully")
    else:
        print("✗ SC3U.dll not found in current directory")
except Exception as e:
    print(f"✗ SC3U.dll loading failed: {e}")

print("\nImport test completed!")
