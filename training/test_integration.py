"""
Test script to verify neural network integration
Tests both the training pipeline and backend integration
"""

import os
import sys
from pathlib import Path

def print_header(text):
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)

def check_file(path, description):
    """Check if a file exists"""
    if os.path.exists(path):
        size = os.path.getsize(path)
        print(f"✅ {description}: {path} ({size:,} bytes)")
        return True
    else:
        print(f"❌ {description}: {path} NOT FOUND")
        return False

def check_imports():
    """Check if required packages are installed"""
    print_header("Checking Python Dependencies")
    
    required_packages = [
        ('torch', 'PyTorch'),
        ('torchvision', 'TorchVision'),
        ('PIL', 'Pillow'),
        ('rich', 'Rich'),
        ('onnx', 'ONNX'),
        ('onnxruntime', 'ONNX Runtime')
    ]
    
    all_ok = True
    for package, name in required_packages:
        try:
            __import__(package)
            print(f"✅ {name}")
        except ImportError:
            print(f"❌ {name} - Not installed")
            all_ok = False
    
    return all_ok

def check_training_files():
    """Check if training files exist"""
    print_header("Checking Training Files")
    
    files = [
        ('train_tui.py', 'Training TUI'),
        ('train.py', 'Training Script'),
        ('dataset.py', 'Dataset Module'),
        ('download_data.py', 'Data Download Script'),
        ('requirements.txt', 'Requirements File')
    ]
    
    all_ok = True
    for file, desc in files:
        if not check_file(file, desc):
            all_ok = False
    
    return all_ok

def check_backend_integration():
    """Check backend integration files"""
    print_header("Checking Backend Integration")
    
    backend_root = Path('../backend')
    
    files = [
        (backend_root / 'src/utils/modelService.js', 'Model Service'),
        (backend_root / 'src/utils/visionService.js', 'Vision Service'),
        (backend_root / 'models/.gitkeep', 'Models Directory'),
        (backend_root / 'package.json', 'Package.json')
    ]
    
    all_ok = True
    for file, desc in files:
        if not check_file(str(file), desc):
            all_ok = False
    
    # Check if onnxruntime-node is in package.json
    if os.path.exists(backend_root / 'package.json'):
        with open(backend_root / 'package.json') as f:
            content = f.read()
            if 'onnxruntime-node' in content:
                print("✅ onnxruntime-node in dependencies")
            else:
                print("❌ onnxruntime-node NOT in dependencies")
                all_ok = False
    
    return all_ok

def check_model_files():
    """Check if trained model files exist"""
    print_header("Checking Trained Model Files")
    
    model_dir = Path('./models')
    backend_model_dir = Path('../backend/models')
    
    print("\n📁 Training Directory:")
    training_ok = True
    if os.path.exists(model_dir):
        files = list(model_dir.glob('*'))
        if files:
            for file in files:
                if file.is_file():
                    size = file.stat().st_size
                    print(f"  ✅ {file.name} ({size:,} bytes)")
        else:
            print("  ⚠️  No model files (train model first)")
            training_ok = False
    else:
        print("  ⚠️  models/ directory doesn't exist")
        training_ok = False
    
    print("\n📁 Backend Directory:")
    backend_ok = True
    required_files = ['caifan_model.onnx', 'classes.json']
    for file in required_files:
        file_path = backend_model_dir / file
        if os.path.exists(file_path):
            size = file_path.stat().st_size
            print(f"  ✅ {file} ({size:,} bytes)")
        else:
            print(f"  ❌ {file} NOT FOUND")
            backend_ok = False
    
    return training_ok, backend_ok

def check_dataset():
    """Check if dataset is downloaded"""
    print_header("Checking Dataset")
    
    data_dirs = [
        ('data/organized', 'Food-101 Dataset'),
        ('data/sample', 'Sample Dataset'),
        ('data/food-101', 'Raw Food-101')
    ]
    
    found = False
    for dir_path, desc in data_dirs:
        if os.path.exists(dir_path):
            if os.path.isdir(dir_path):
                items = len(list(Path(dir_path).iterdir()))
                print(f"✅ {desc}: {dir_path} ({items} items)")
                found = True
        else:
            print(f"⚠️  {desc}: {dir_path} not found")
    
    return found

def main():
    print("""
    ╔════════════════════════════════════════════════════════╗
    ║   🍱 Cai Fan Neural Network Integration Test          ║
    ╚════════════════════════════════════════════════════════╝
    """)
    
    # Change to training directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    results = {}
    
    # Run checks
    results['imports'] = check_imports()
    results['training_files'] = check_training_files()
    results['backend'] = check_backend_integration()
    training_ok, backend_ok = check_model_files()
    results['trained_model'] = training_ok
    results['backend_model'] = backend_ok
    results['dataset'] = check_dataset()
    
    # Summary
    print_header("Summary")
    
    status = {
        'imports': 'Python Dependencies',
        'training_files': 'Training Files',
        'backend': 'Backend Integration',
        'trained_model': 'Trained Model (optional)',
        'backend_model': 'Backend Model (for inference)',
        'dataset': 'Dataset (optional)'
    }
    
    for key, desc in status.items():
        icon = "✅" if results[key] else "❌"
        print(f"{icon} {desc}")
    
    # Final verdict
    critical = ['imports', 'training_files', 'backend']
    all_critical = all(results[k] for k in critical)
    
    print("\n" + "=" * 60)
    if all_critical:
        print("🎉 INTEGRATION COMPLETE!")
        print("\nNext steps:")
        if not results['dataset']:
            print("  1. Download dataset: python download_data.py")
        if not results['trained_model']:
            print("  2. Train model: python train_tui.py")
        if not results['backend_model']:
            print("  3. Copy model to backend:")
            print("     cp models/caifan_model.onnx ../backend/models/")
            print("     cp models/classes.json ../backend/models/")
        if results['backend_model']:
            print("  ✅ Ready to run! Start backend with: cd ../backend && npm run dev")
    else:
        print("❌ SETUP INCOMPLETE")
        print("\nPlease fix the issues above.")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
