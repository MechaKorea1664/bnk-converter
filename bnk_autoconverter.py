#!/usr/bin/env python3
import os
import shutil
import subprocess
import sys
import time
import threading
from pathlib import Path

class ProgressSpinner:
    """ASCII spinner for visual feedback"""
    def __init__(self):
        self.spinner_chars = ['-', '\\', '|', '/']
        self.spinning = False
        self.spinner_thread = None
        self.idx = 0
    
    def start(self, message="Processing"):
        self.spinning = True
        self.idx = 0
        def spin():
            while self.spinning:
                print(f"\r{message} {self.spinner_chars[self.idx % 4]}", end='', flush=True)
                self.idx += 1
                time.sleep(0.1)
        self.spinner_thread = threading.Thread(target=spin)
        self.spinner_thread.start()
    
    def stop(self):
        self.spinning = False
        if self.spinner_thread:
            self.spinner_thread.join()
        print("\r" + " " * 80 + "\r", end='', flush=True)

spinner = ProgressSpinner()

def get_resource_path(relative_path):
    """Get bundled resource path for PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = Path(__file__).parent if hasattr(Path(__file__), 'parent') else Path(os.getcwd())
    return os.path.join(base_path, relative_path)

def get_executable_dir():
    """Get directory where executable/script is located"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent if hasattr(Path(__file__), 'parent') else Path(os.getcwd())

def run_command(cmd, verbosity=1):
    """Execute shell command with verbosity control"""
    try:
        if verbosity == 3:
            result = subprocess.run(cmd, shell=True, text=True)
        else:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0
    except Exception as e:
        if verbosity > 1:
            print(f"Error running command: {e}")
        return False

def get_file_size(filepath):
    """Get file size in bytes"""
    try:
        return os.path.getsize(filepath)
    except:
        return 0

def get_choice(prompt, options, validator=None):
    """Generic choice input with validation"""
    print(prompt)
    for k, v in options.items():
        print(f"{k}. {v}")
    
    while True:
        choice = input("Enter choice: ").strip()
        if validator:
            result = validator(choice)
            if result is not None:
                return result
        elif choice in options:
            return choice
        print("Invalid choice.")

def get_format():
    """Get output format choice"""
    formats = {'1': 'wav', '2': 'mp3', '3': 'ogg', '4': 'flac', '5': 'm4a'}
    choice = get_choice("Select output format:", {k: v.upper() for k, v in formats.items()})
    return formats[choice]

def get_verbosity():
    """Get verbosity level"""
    levels = {'1': 'Minimal output', '2': 'Standard output', '3': 'Full output'}
    choice = get_choice("\nOutput verbosity:", levels)
    return int(choice)

def get_cleanup_settings():
    """Get cleanup preferences"""
    cleanup_wem = get_choice("\nClean up .wem files after conversion?", 
                            {'1': 'Keep .wem files', '2': 'Delete .wem files'}) == '2'
    
    delete_small = get_choice("\nDelete small output files?\nNote: Files smaller than 4844 bytes are usually empty/silent audio.", 
                             {'1': 'Keep all output files', '2': 'Delete files smaller than specified size'}) == '2'
    
    min_file_size = 0
    if delete_small:
        size_input = input("\nEnter minimum file size in bytes (default: 4844): ").strip()
        try:
            min_file_size = int(size_input) if size_input else 4844
        except ValueError:
            min_file_size = 4844
    
    remove_duplicates = get_choice("\nRemove duplicate files by size?\nWARNING: This may remove unique files that happen to have the same size!", 
                                  {'1': 'Keep all files', '2': 'Remove files with identical file sizes'}) == '2'
    
    return cleanup_wem, delete_small, min_file_size, remove_duplicates

def find_bnk_files():
    """Locate and validate .bnk files"""
    script_dir = get_executable_dir()
    input_dir = script_dir / "input"
    
    if not input_dir.exists():
        print(f"\n[ERROR] Input directory '{input_dir}' not found!")
        print(f"Please create an 'input' folder in {script_dir} and place your .bnk files there.")
        input("Press Enter to exit...")
        sys.exit(1)
    
    bnk_files = list(input_dir.glob("*.bnk"))
    if not bnk_files:
        print(f"[ERROR] No .bnk files found in {input_dir}!")
        input("Press Enter to exit...")
        sys.exit(1)
    
    return bnk_files, script_dir / "output"

def select_files(bnk_files):
    """Handle file selection logic"""
    print(f"\n[*] Scanning for .bnk files...")
    for i, bnk_file in enumerate(bnk_files, 1):
        print(f"     {i}. {bnk_file.name}")
    
    print("\nSelect .bnk files to process:")
    print("A. Process ALL files")
    print("M. Select MULTIPLE files")
    for i, bnk_file in enumerate(bnk_files, 1):
        print(f"{i}. Process only {bnk_file.name}")
    
    selection = input("Enter your choice: ").strip().upper()
    
    if selection == 'A':
        return bnk_files
    elif selection == 'M':
        print("\nEnter file numbers separated by spaces (e.g., 1 3 5):")
        numbers = input().strip().split()
        try:
            indices = [int(n) - 1 for n in numbers if n.isdigit()]
            return [bnk_files[i] for i in indices if 0 <= i < len(bnk_files)]
        except (ValueError, IndexError):
            return []
    else:
        try:
            index = int(selection) - 1
            return [bnk_files[index]] if 0 <= index < len(bnk_files) else []
        except ValueError:
            return []

def extract_bnk(bnk_file, temp_dir, bnkextr_path, verbosity):
    """Extract .bnk file to .wem files"""
    temp_bnk = temp_dir / bnk_file.name
    shutil.copy2(bnk_file, temp_bnk)
    
    spinner.start(f"[*] Extracting {bnk_file.name}")
    
    original_dir = os.getcwd()
    os.chdir(temp_dir)
    
    extract_cmd = f'"{bnkextr_path}" "{bnk_file.name}"'
    success = run_command(extract_cmd, verbosity)
    
    if temp_bnk.exists():
        temp_bnk.unlink()
    os.chdir(original_dir)
    spinner.stop()
    
    return success

def should_delete_file(output_file, file_size, delete_small, min_file_size, remove_duplicates, file_sizes):
    """Determine if file should be deleted based on settings"""
    if delete_small and file_size < min_file_size:
        return True, "small"
    elif remove_duplicates and file_size in file_sizes:
        return True, "duplicate"
    elif remove_duplicates:
        file_sizes[file_size] = output_file.name
    return False, None

def convert_wem_files(temp_dir, output_dir, ext, vgmstream_path, verbosity, delete_small, min_file_size, remove_duplicates):
    """Convert all .wem files to target format"""
    wem_files = list(temp_dir.glob("*.wem"))
    if not wem_files:
        return False
    
    file_sizes = {}
    
    # Verbosity 1: Spinner only
    if verbosity == 1:
        spinner.start("[*] Converting files")
    
    for count, wem_file in enumerate(wem_files, 1):
        output_file = output_dir / f"{wem_file.stem}.{ext}"
        
        # Verbosity 2: Progress counter only (in-place updates)
        if verbosity == 2:
            print(f"\rProcessing file {count}/{len(wem_files)}", end='', flush=True)
        
        # Verbosity 3: Individual file names only
        elif verbosity == 3:
            print(f"Processing file {count}/{len(wem_files)}: {wem_file.name}")
        
        convert_cmd = f'"{vgmstream_path}" -o "{output_file}" "{wem_file}"'
        convert_success = run_command(convert_cmd, verbosity)
        
        if convert_success:
            file_size = get_file_size(output_file)
            should_delete, reason = should_delete_file(output_file, file_size, delete_small, min_file_size, remove_duplicates, file_sizes)
            
            if should_delete:
                if verbosity == 3:
                    print(f"     Deleting {reason} file: {output_file.name} ({file_size} bytes)")
                try:
                    output_file.unlink()
                except:
                    pass
        elif verbosity == 3:
            print(f"     Failed to convert {wem_file.name}")
    
    # Clean up output for verbosity 2
    if verbosity == 2:
        print()  # New line after progress counter
    elif verbosity == 1:
        spinner.stop()
    
    return True

def cleanup_temp_dir(temp_dir, output_dir, cleanup_wem, verbosity):
    """Handle temp directory cleanup"""
    if cleanup_wem:
        if verbosity >= 2:
            print("[*] Cleaning up temporary files...")
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
    else:
        if verbosity >= 2:
            print("[*] Moving .wem files to output directory...")
        for wem_file in temp_dir.glob("*.wem"):
            try:
                shutil.move(str(wem_file), str(output_dir))
            except:
                pass
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

def process_bnk_file(bnk_file, output_base_dir, ext, bnkextr_path, vgmstream_path, verbosity, cleanup_wem, delete_small, min_file_size, remove_duplicates):
    """Process single .bnk file through complete pipeline"""
    basename = bnk_file.stem
    
    print("\n" + "=" * 40)
    print(f"[*] Processing: {bnk_file.name}")
    print("=" * 40)
    
    temp_dir = Path(f"temp_{basename}")
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir()
    
    file_output_dir = output_base_dir / basename
    file_output_dir.mkdir(exist_ok=True)
    
    try:
        if not extract_bnk(bnk_file, temp_dir, bnkextr_path, verbosity):
            print(f"[ERROR] Failed to extract {bnk_file.name}")
            return False
        
        if not convert_wem_files(temp_dir, file_output_dir, ext, vgmstream_path, verbosity, delete_small, min_file_size, remove_duplicates):
            print(f"[ERROR] No .wem files found after extraction of {bnk_file.name}")
            return False
        
        cleanup_temp_dir(temp_dir, file_output_dir, cleanup_wem, verbosity)
        return True
        
    except Exception as e:
        spinner.stop()
        print(f"[ERROR] Exception processing {bnk_file.name}: {e}")
        return False
    finally:
        if temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
            except:
                pass

def validate_tools():
    """Check if required tools exist"""
    bnkextr_path = get_resource_path("bnkextr.exe")
    vgmstream_path = get_resource_path("vgmstream-cli/vgmstream-cli.exe")
    
    for tool_path, tool_name in [(bnkextr_path, "bnkextr.exe"), (vgmstream_path, "vgmstream-cli.exe")]:
        if not os.path.exists(tool_path):
            print(f"[ERROR] {tool_name} not found at {tool_path}")
            input("Press Enter to exit...")
            sys.exit(1)
    
    return bnkextr_path, vgmstream_path

def main():
    print("=" * 40)
    print("    BNK Audio Extractor and Converter")
    print("=" * 40)
    print()
    
    ext = get_format()
    verbosity = get_verbosity()
    cleanup_wem, delete_small, min_file_size, remove_duplicates = get_cleanup_settings()
    
    bnk_files, output_dir = find_bnk_files()
    files_to_process = select_files(bnk_files)
    
    if not files_to_process:
        print("No files selected for processing.")
        return
    
    print("\n[*] Creating main output directory...")
    output_dir.mkdir(exist_ok=True)
    
    bnkextr_path, vgmstream_path = validate_tools()
    
    processed_files = [bnk_file for bnk_file in files_to_process 
                      if process_bnk_file(bnk_file, output_dir, ext, bnkextr_path, vgmstream_path, 
                                         verbosity, cleanup_wem, delete_small, min_file_size, remove_duplicates)]
    
    print("\n" + "=" * 40)
    print("[*] All conversions completed!")
    for bnk_file in processed_files:
        print(f"[*] Output saved to: {output_dir}/{bnk_file.stem}/")
    print("=" * 40)
    input("Press Enter to exit...")

if __name__ == "__main__":
    main()