#!/usr/bin/env python3
"""
PyInstaller Build Script for SoulLink Tracker Portable Edition

This script builds the portable executable using PyInstaller.
It handles cross-platform builds and resource bundling.
"""

import sys
import os
import platform
import shutil
import subprocess
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PyInstallerBuilder:
    """Handles PyInstaller build process for SoulLink Tracker."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.dist_dir = self.project_root / "dist"
        self.build_dir = self.project_root / "build" / "pyinstaller_temp"
        self.spec_file = self.project_root / "build" / "soullink_tracker.spec"
        
        # Platform detection
        self.platform = platform.system().lower()
        self.arch = platform.machine().lower()
        
        logger.info(f"Building for platform: {self.platform}-{self.arch}")
        
    def clean_build_dirs(self):
        """Clean previous build artifacts."""
        logger.info("Cleaning build directories...")
        
        for dir_path in [self.dist_dir, self.build_dir]:
            if dir_path.exists():
                shutil.rmtree(dir_path)
                logger.info(f"Removed {dir_path}")
                
        if self.spec_file.exists():
            self.spec_file.unlink()
            logger.info(f"Removed {self.spec_file}")
            
    def check_dependencies(self):
        """Check if PyInstaller and required dependencies are available."""
        try:
            import PyInstaller
            logger.info(f"PyInstaller version: {PyInstaller.__version__}")
        except ImportError:
            logger.error("PyInstaller not found. Install with: pip install pyinstaller")
            return False
            
        # Check if the entry point exists
        entry_point = self.project_root / "soullink_portable.py"
        if not entry_point.exists():
            logger.error(f"Entry point not found: {entry_point}")
            return False
            
        return True
        
    def get_data_files(self):
        """Get list of data files to bundle."""
        data_files = []
        
        # Web assets
        web_dir = self.project_root / "web"
        if web_dir.exists():
            data_files.append(f"{web_dir};web")
            
        # Lua scripts
        lua_dir = self.project_root / "client" / "lua"
        if lua_dir.exists():
            data_files.append(f"{lua_dir};client/lua")
            
        # Data files
        data_dir = self.project_root / "data"
        if data_dir.exists():
            data_files.append(f"{data_dir};data")
            
        # License and README
        for filename in ["LICENSE", "README.md"]:
            file_path = self.project_root / filename
            if file_path.exists():
                data_files.append(f"{file_path};.")
                
        return data_files
        
    def get_hidden_imports(self):
        """Get list of hidden imports needed for PyInstaller."""
        return [
            'uvicorn',
            'uvicorn.lifespan.on',
            'uvicorn.lifespan.off',
            'uvicorn.protocols.websockets.auto',
            'uvicorn.protocols.http.auto',
            'uvicorn.protocols.http.h11_impl',
            'uvicorn.protocols.http.httptools_impl',
            'uvicorn.protocols.websockets.wsproto_impl',
            'uvicorn.protocols.websockets.websockets_impl',
            'fastapi',
            'sqlalchemy.dialects.sqlite',
            'alembic.runtime.migration',
            'cryptography',
            'pydantic',
            'websockets',
            'aiosqlite',
        ]
        
    def get_platform_specific_options(self):
        """Get platform-specific PyInstaller options."""
        options = []
        
        if self.platform == "windows":
            options.extend([
                "--windowed",  # Hide console window
                "--icon=build/icon.ico" if (self.project_root / "build" / "icon.ico").exists() else None,
                "--version-file=build/version_info.txt" if (self.project_root / "build" / "version_info.txt").exists() else None,
            ])
        elif self.platform == "darwin":  # macOS
            options.extend([
                "--windowed",
                "--icon=build/icon.icns" if (self.project_root / "build" / "icon.icns").exists() else None,
                "--osx-bundle-identifier=com.soullink.tracker",
            ])
        elif self.platform == "linux":
            options.extend([
                "--strip",  # Strip debug symbols to reduce size
            ])
            
        # Filter out None values
        return [opt for opt in options if opt is not None]
        
    def create_spec_file(self):
        """Create PyInstaller spec file for customization."""
        entry_point = self.project_root / "soullink_portable.py"
        data_files = self.get_data_files()
        hidden_imports = self.get_hidden_imports()
        platform_options = self.get_platform_specific_options()
        
        # Determine executable name
        exe_name = "soullink-tracker"
        if self.platform == "windows":
            exe_name += ".exe"
        elif self.platform == "darwin":
            exe_name = "SoulLink Tracker"
            
        spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for SoulLink Tracker Portable Edition
# Generated automatically by build_pyinstaller.py

block_cipher = None

a = Analysis(
    ['{entry_point}'],
    pathex=['{self.project_root}'],
    binaries=[],
    datas={data_files!r},
    hiddenimports={hidden_imports!r},
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='{exe_name}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # Compress with UPX if available
    upx_exclude=[],
    runtime_tmpdir=None,
    console={'True' if self.platform == 'linux' else 'False'},
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)'''

        if self.platform == "darwin":
            # Add macOS app bundle
            spec_content += f'''

app = BUNDLE(
    exe,
    name='{exe_name}.app',
    icon='build/icon.icns' if Path('build/icon.icns').exists() else None,
    bundle_identifier='com.soullink.tracker',
    info_plist={{
        'CFBundleDisplayName': 'SoulLink Tracker',
        'CFBundleVersion': '2.0.0',
        'CFBundleShortVersionString': '2.0.0',
        'NSHighResolutionCapable': 'True',
    }},
)'''

        with open(self.spec_file, 'w') as f:
            f.write(spec_content)
            
        logger.info(f"Created spec file: {self.spec_file}")
        
    def run_pyinstaller(self):
        """Run PyInstaller with the generated spec file."""
        logger.info("Starting PyInstaller build...")
        
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--clean",
            "--noconfirm",
            str(self.spec_file)
        ]
        
        logger.info(f"Running command: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=True
            )
            
            logger.info("PyInstaller build completed successfully")
            if result.stdout:
                logger.debug(f"PyInstaller stdout: {result.stdout}")
                
        except subprocess.CalledProcessError as e:
            logger.error(f"PyInstaller build failed with return code {e.returncode}")
            logger.error(f"Error output: {e.stderr}")
            if e.stdout:
                logger.error(f"Standard output: {e.stdout}")
            raise
            
    def optimize_build(self):
        """Optimize the built executable."""
        logger.info("Optimizing build...")
        
        # Find the executable
        if self.platform == "darwin":
            exe_path = self.dist_dir / "SoulLink Tracker.app"
        else:
            exe_name = "soullink-tracker.exe" if self.platform == "windows" else "soullink-tracker"
            exe_path = self.dist_dir / exe_name
            
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            logger.info(f"Executable size: {size_mb:.1f} MB")
            
            # TODO: Add UPX compression if available
            # TODO: Add code signing for Windows/macOS
            
        else:
            logger.warning(f"Executable not found at {exe_path}")
            
    def create_distribution_package(self):
        """Create final distribution package."""
        logger.info("Creating distribution package...")
        
        # Determine package name
        package_name = f"soullink-tracker-v2.0.0-{self.platform}-{self.arch}"
        package_dir = self.dist_dir / package_name
        
        # Create package directory
        package_dir.mkdir(exist_ok=True)
        
        # Copy executable
        if self.platform == "darwin":
            exe_source = self.dist_dir / "SoulLink Tracker.app"
            exe_dest = package_dir / "SoulLink Tracker.app"
            if exe_source.exists():
                shutil.copytree(exe_source, exe_dest)
        else:
            exe_name = "soullink-tracker.exe" if self.platform == "windows" else "soullink-tracker"
            exe_source = self.dist_dir / exe_name
            exe_dest = package_dir / exe_name
            if exe_source.exists():
                shutil.copy2(exe_source, exe_dest)
                
        # Copy documentation
        for filename in ["README.md", "LICENSE"]:
            source = self.project_root / filename
            if source.exists():
                shutil.copy2(source, package_dir / filename)
                
        # Create quick start guide
        quick_start = package_dir / "QUICK_START.txt"
        with open(quick_start, 'w') as f:
            f.write(f"""SoulLink Tracker Portable Edition v2.0.0
{'='*50}

Quick Start:
1. Extract this package to any folder
2. Run {'soullink-tracker.exe' if self.platform == 'windows' else './soullink-tracker'}
3. Your browser will open automatically
4. Follow the setup wizard

Features:
- Zero installation required
- Automatic browser launching
- Built-in setup wizard
- Cross-platform support

For more information, see README.md

Enjoy your SoulLink run! 🔗
""")

        # Create archive
        archive_name = f"{package_name}.zip"
        archive_path = self.dist_dir / archive_name
        
        logger.info(f"Creating archive: {archive_path}")
        shutil.make_archive(
            str(archive_path.with_suffix('')),
            'zip',
            self.dist_dir,
            package_name
        )
        
        logger.info(f"Distribution package created: {archive_path}")
        return archive_path
        
    def build(self):
        """Main build process."""
        try:
            logger.info("Starting SoulLink Tracker portable build process...")
            
            # Check dependencies
            if not self.check_dependencies():
                return False
                
            # Clean previous builds
            self.clean_build_dirs()
            
            # Create spec file
            self.create_spec_file()
            
            # Run PyInstaller
            self.run_pyinstaller()
            
            # Optimize build
            self.optimize_build()
            
            # Create distribution package
            package_path = self.create_distribution_package()
            
            logger.info(f"✅ Build completed successfully!")
            logger.info(f"📦 Package: {package_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Build failed: {e}")
            return False


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Build SoulLink Tracker portable executable")
    parser.add_argument("--clean-only", action="store_true", help="Only clean build directories")
    parser.add_argument("--spec-only", action="store_true", help="Only create spec file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        
    builder = PyInstallerBuilder()
    
    if args.clean_only:
        builder.clean_build_dirs()
        logger.info("Clean completed")
        return 0
        
    if args.spec_only:
        if builder.check_dependencies():
            builder.create_spec_file()
            logger.info("Spec file created")
            return 0
        else:
            return 1
            
    # Full build
    success = builder.build()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())